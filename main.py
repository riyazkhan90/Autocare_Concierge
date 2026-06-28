"""FastAPI application — text and voice channels sharing one agent core."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import re
import wave
from contextlib import asynccontextmanager
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from groq import Groq
from pydantic import BaseModel

from agent.context import set_thread_context
from agent.customers import DEMO_PHONE, get_customer_by_phone, format_profile_greeting
from agent.graph import run_agent
from metrics.store import (
    aggregate_metrics,
    calc_llm_cost,
    calc_stt_cost,
    calc_tts_cost,
    detect_intent,
    ensure_variant,
    get_admin_dashboard,
    init_db,
    list_agent_routes,
    log_feedback,
    log_intent,
    upsert_conversation,
)

load_dotenv()

logger = logging.getLogger(__name__)

TTS_MODEL = "canopylabs/orpheus-v1-english"
TTS_VOICE = "austin"
TTS_MAX_CHARS = 120
STT_MODEL = "whisper-large-v3-turbo"
SKIP_TTS = os.getenv("SKIP_TTS", "").lower() in ("1", "true", "yes")
CHAT_REQUEST_TIMEOUT = float(os.getenv("CHAT_REQUEST_TIMEOUT", "120"))
GROQ_CLIENT_TIMEOUT = float(os.getenv("GROQ_REQUEST_TIMEOUT", "90"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if os.getenv("GROQ_API_KEY"):
        logger.info("Startup complete — GROQ_API_KEY is configured")
    else:
        logger.warning("Startup complete — GROQ_API_KEY is missing")
    yield


app = FastAPI(title="Al Futtaim Automotive Concierge", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


def _groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured")
    return Groq(api_key=api_key, timeout=GROQ_CLIENT_TIMEOUT)


class TextChatRequest(BaseModel):
    message: str
    thread_id: str
    entry_mode: Literal["free_text", "guided", "voice"] = "free_text"
    customer_phone: str | None = None


class TextChatResponse(BaseModel):
    reply: str
    thread_id: str
    cost_breakdown: dict
    routed_agent: str = "general"
    agent_label: str = "General Agent"
    route_reason: str = ""
    variant: str = "A"
    customer_greeting: str | None = None


class FeedbackRequest(BaseModel):
    thread_id: str
    rating: Literal["up", "down"]


class VoiceChatResponse(BaseModel):
    transcript: str
    reply_text: str
    audio_base64: str = ""
    thread_id: str
    cost_breakdown: dict
    tts_error: str | None = None
    use_browser_tts: bool = False
    routed_agent: str = "general"
    agent_label: str = "General Agent"
    route_reason: str = ""
    variant: str = "A"


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/admin")
async def admin():
    return RedirectResponse(url="/static/admin.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
    }


@app.get("/metrics")
async def metrics():
    return aggregate_metrics()


@app.get("/admin/routes")
async def admin_routes(limit: int = 50):
    return {"routes": list_agent_routes(limit=min(limit, 200))}


@app.get("/admin/dashboard")
async def admin_dashboard():
    return get_admin_dashboard()


@app.get("/customer/{phone}")
async def customer_profile(phone: str):
    profile = get_customer_by_phone(phone)
    if not profile:
        raise HTTPException(status_code=404, detail="Customer not found")
    return profile


@app.get("/customer/demo/sara")
async def demo_customer():
    profile = get_customer_by_phone(DEMO_PHONE)
    return profile or {}


@app.post("/feedback")
async def feedback(body: FeedbackRequest):
    log_feedback(body.thread_id, body.rating)
    return {"status": "recorded", "thread_id": body.thread_id, "rating": body.rating}


def _run_turn(
    message: str,
    thread_id: str,
    channel: str,
    *,
    extra_cost: float = 0.0,
    record: bool = True,
    entry_mode: str = "free_text",
    customer_phone: str | None = None,
) -> tuple:
    ensure_variant(thread_id)
    if customer_phone:
        set_thread_context(thread_id, customer_phone=customer_phone)
        profile = get_customer_by_phone(customer_phone)
        if profile and profile.get("vehicles"):
            v = profile["vehicles"][0]
            set_thread_context(
                thread_id,
                vehicle=f"{v['year']} {v['make']} {v['model']}",
            )
    vehicle_match = re.search(
        r"for my (\d{4})\s+([A-Za-z]+)\s+([A-Za-z0-9-]+)",
        message,
        re.IGNORECASE,
    )
    if vehicle_match:
        y, mk, md = vehicle_match.groups()
        set_thread_context(thread_id, vehicle=f"{y} {mk} {md}")
    intent = detect_intent(message)
    if intent:
        log_intent(thread_id, intent, entry_mode)

    result = run_agent(message, thread_id)
    llm_cost = calc_llm_cost(result.input_tokens, result.output_tokens)
    total_cost = llm_cost + extra_cost

    if record:
        upsert_conversation(
            thread_id,
            channel=channel,
            cost_delta=total_cost,
            resolved=not result.escalated,
            escalated=result.escalated,
            last_agent=result.routed_agent,
            customer_phone=customer_phone,
            entry_mode=entry_mode,
        )

    cost_breakdown = {
        "llm_input_tokens": result.input_tokens,
        "llm_output_tokens": result.output_tokens,
        "llm_cost_usd": round(llm_cost, 6),
        "extra_cost_usd": round(extra_cost, 6),
        "total_cost_usd": round(total_cost, 6),
        "escalated": result.escalated,
        "routed_agent": result.routed_agent,
        "route_reason": result.route_reason,
        "variant": result.variant,
    }
    return result, cost_breakdown


@app.post("/chat/text", response_model=TextChatResponse)
async def chat_text(body: TextChatRequest):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")
    if not body.thread_id.strip():
        raise HTTPException(status_code=400, detail="thread_id must not be empty")

    customer_greeting = None
    if body.customer_phone:
        profile = get_customer_by_phone(body.customer_phone)
        if profile:
            customer_greeting = format_profile_greeting(profile)

    try:
        logger.info("chat/text start thread_id=%s", body.thread_id)
        result, cost_breakdown = await asyncio.wait_for(
            asyncio.to_thread(
                _run_turn,
                body.message,
                body.thread_id,
                "text",
                entry_mode=body.entry_mode,
                customer_phone=body.customer_phone,
            ),
            timeout=CHAT_REQUEST_TIMEOUT,
        )
        logger.info(
            "chat/text done thread_id=%s agent=%s",
            body.thread_id,
            result.routed_agent,
        )
    except asyncio.TimeoutError as e:
        raise HTTPException(
            status_code=504,
            detail="Agent request timed out. Please try again.",
        ) from e
    except Exception as e:
        logger.exception("chat/text failed thread_id=%s", body.thread_id)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return TextChatResponse(
        reply=result.reply,
        thread_id=body.thread_id,
        cost_breakdown=cost_breakdown,
        routed_agent=result.routed_agent,
        agent_label=result.agent_label,
        route_reason=result.route_reason,
        variant=result.variant,
        customer_greeting=customer_greeting,
    )


def _synthesize_speech(client: Groq, text: str) -> bytes:
    """Synthesize speech, chunking at TTS_MAX_CHARS for Orpheus limit."""
    chunks = [text[i : i + TTS_MAX_CHARS] for i in range(0, max(len(text), 1), TTS_MAX_CHARS)]
    if not chunks:
        chunks = [" "]

    audio_segments: list[bytes] = []
    for chunk in chunks:
        response = client.audio.speech.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=chunk,
            response_format="wav",
        )
        audio_segments.append(response.read())

    if len(audio_segments) == 1:
        return audio_segments[0]

    # Concatenate PCM frames; do not use setparams() — it copies nframes from the
    # first chunk only, which overflows the WAV header when more audio is written.
    combined = io.BytesIO()
    params = None
    frames: list[bytes] = []
    for seg in audio_segments:
        with wave.open(io.BytesIO(seg), "rb") as wf:
            if params is None:
                params = wf.getparams()
            frames.append(wf.readframes(wf.getnframes()))

    with wave.open(combined, "wb") as out:
        out.setnchannels(params.nchannels)
        out.setsampwidth(params.sampwidth)
        out.setframerate(params.framerate)
        out.setcomptype(params.comptype, params.compname)
        out.writeframes(b"".join(frames))
    return combined.getvalue()


@app.post("/chat/voice", response_model=VoiceChatResponse)
async def chat_voice(
    audio: UploadFile = File(...),
    thread_id: str = Form(...),
    duration_seconds: float = Form(...),
):
    if not thread_id.strip():
        raise HTTPException(status_code=400, detail="thread_id must not be empty")

    try:
        client = _groq_client()
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Audio recording is empty — hold the mic button a bit longer")

        transcription = await asyncio.to_thread(
            client.audio.transcriptions.create,
            file=(audio.filename or "audio.webm", audio_bytes),
            model=STT_MODEL,
        )
        transcript = (transcription.text or "").strip()
        if not transcript:
            raise HTTPException(
                status_code=400,
                detail="Could not detect speech in the recording — try speaking closer to the mic",
            )

        stt_cost = calc_stt_cost(duration_seconds)
        result, cost_breakdown = await asyncio.wait_for(
            asyncio.to_thread(
                _run_turn,
                transcript,
                thread_id,
                "voice",
                extra_cost=stt_cost,
                record=False,
                entry_mode="voice",
            ),
            timeout=CHAT_REQUEST_TIMEOUT,
        )
        cost_breakdown["stt_duration_seconds"] = duration_seconds
        cost_breakdown["stt_cost_usd"] = round(stt_cost, 6)

        tts_text = result.reply[:TTS_MAX_CHARS]
        audio_b64 = ""
        tts_error = None
        use_browser_tts = False
        tts_cost = 0.0

        if SKIP_TTS:
            use_browser_tts = True
        else:
            try:
                speech_bytes = await asyncio.to_thread(_synthesize_speech, client, tts_text)
                tts_cost = calc_tts_cost(len(tts_text))
                audio_b64 = base64.b64encode(speech_bytes).decode("ascii")
            except Exception as tts_exc:
                err = str(tts_exc)
                if "model_terms_required" in err:
                    tts_error = (
                        "TTS unavailable: accept Orpheus terms at "
                        "https://console.groq.com/playground?model=canopylabs%2Forpheus-v1-english "
                        "(one-time, free). Using browser voice instead."
                    )
                    use_browser_tts = True
                elif "rate_limit" in err or "429" in err:
                    use_browser_tts = True
                else:
                    tts_error = err
                    use_browser_tts = True

        cost_breakdown["tts_characters"] = len(tts_text)
        cost_breakdown["tts_cost_usd"] = round(tts_cost, 6)
        total_cost = cost_breakdown["total_cost_usd"] + tts_cost
        cost_breakdown["total_cost_usd"] = round(total_cost, 6)

        upsert_conversation(
            thread_id,
            channel="voice",
            cost_delta=total_cost,
            resolved=not result.escalated,
            escalated=result.escalated,
            last_agent=result.routed_agent,
            entry_mode="voice",
        )

        return VoiceChatResponse(
            transcript=transcript,
            reply_text=result.reply,
            audio_base64=audio_b64,
            thread_id=thread_id,
            cost_breakdown=cost_breakdown,
            tts_error=tts_error,
            use_browser_tts=use_browser_tts,
            routed_agent=result.routed_agent,
            agent_label=result.agent_label,
            route_reason=result.route_reason,
            variant=result.variant,
        )
    except HTTPException:
        raise
    except asyncio.TimeoutError as e:
        raise HTTPException(
            status_code=504,
            detail="Agent request timed out. Please try again.",
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
