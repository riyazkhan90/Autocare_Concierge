"""Intent router for multi-agent orchestration."""

from __future__ import annotations

import os
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from agent.prompts import ROUTER_PROMPT
from metrics.store import get_last_agent, set_last_agent

GROQ_TIMEOUT = float(os.getenv("GROQ_REQUEST_TIMEOUT", "90"))

VALID_AGENTS = frozenset({"service", "sales", "recall", "handover", "general"})

_SERVICE_KEYWORDS = (
    "book", "appointment", "service", "oil change", "brake", "maintenance",
    "workshop", "minor service", "major service", "interim service", "ac service",
    "صيانة", "حجز", "موعد",
)
_SALES_KEYWORDS = (
    "trade-in", "trade in", "tradein", "valuation", "worth", "sell my car",
    "test drive", "buy a car", "new car", "استبدال", "تقييم", "تجربة قيادة",
)
_RECALL_KEYWORDS = (
    "recall", "safety recall", "campaign", "استدعاء", "استدعاءات",
)
_HANDOVER_KEYWORDS = (
    "speak to", "talk to", "human", "real person", "service advisor",
    "frustrated", "angry", "complaint", "manager", "مستشار", "شخص",
)


def _keyword_route(message: str) -> tuple[str, str] | None:
    lower = message.lower()
    if any(k in lower for k in _HANDOVER_KEYWORDS):
        return "handover", "keyword_handover"
    if any(k in lower for k in _RECALL_KEYWORDS):
        return "recall", "keyword_recall"
    if any(k in lower for k in _SALES_KEYWORDS):
        return "sales", "keyword_sales"
    if any(k in lower for k in _SERVICE_KEYWORDS):
        return "service", "keyword_service"
    return None


def _is_short_follow_up(message: str) -> bool:
    text = message.strip()
    if not text:
        return False
    words = text.split()
    if len(words) <= 5:
        return True
    if re.match(r"^\d{4}$", text):
        return True
    if re.match(r"^\d{1,2}:\d{2}$", text):
        return True
    return False


def _llm_route(message: str, api_key: str) -> tuple[str, str]:
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0,
        max_tokens=16,
        api_key=api_key,
        timeout=GROQ_TIMEOUT,
        max_retries=1,
    )
    response = llm.invoke(
        [
            SystemMessage(content=ROUTER_PROMPT),
            HumanMessage(content=message),
        ]
    )
    raw = (response.content or "general").strip().lower()
    for token in raw.replace(",", " ").split():
        token = token.strip(".")
        if token in VALID_AGENTS:
            return token, "llm_router"
    return "general", "llm_router_fallback"


def route_message(message: str, thread_id: str, *, api_key: str | None = None) -> tuple[str, str]:
    """Return (agent_name, route_reason)."""
    text = message.strip()
    if not text:
        return "general", "empty_message"

    keyword = _keyword_route(text)
    if keyword:
        agent, reason = keyword
        set_last_agent(thread_id, agent)
        return agent, reason

    if _is_short_follow_up(text):
        last = get_last_agent(thread_id)
        if last:
            return last, "sticky_follow_up"

    if api_key:
        try:
            agent, reason = _llm_route(text, api_key)
            set_last_agent(thread_id, agent)
            return agent, reason
        except Exception:
            pass

    last = get_last_agent(thread_id)
    if last:
        return last, "sticky_last_agent"

    set_last_agent(thread_id, "general")
    return "general", "default"
