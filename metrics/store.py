"""SQLite-backed conversation metrics, conversions, and ops data."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from agent.experiments import assign_variant

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "alfuttaim.db"

LLM_INPUT_PER_M = 0.15
LLM_OUTPUT_PER_M = 0.60
STT_PER_HOUR = 0.04
TTS_PER_M_CHARS = 22.0

CONVERSION_TOOLS = frozenset({
    "book_appointment",
    "lookup_vehicle_recall",
    "get_trade_in_quote",
    "request_test_drive",
})

INTENT_KEYWORDS = {
    "booking": ("book", "appointment", "service", "oil change", "maintenance", "workshop", "حجز", "صيانة"),
    "recall": ("recall", "safety recall", "استدعاء"),
    "tradein": ("trade-in", "trade in", "tradein", "valuation", "worth", "استبدال"),
    "sales": ("test drive", "buy a car", "new car", "تجربة قيادة"),
}


def calc_llm_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * LLM_INPUT_PER_M + output_tokens * LLM_OUTPUT_PER_M) / 1_000_000


def calc_stt_cost(duration_seconds: float) -> float:
    return (duration_seconds / 3600) * STT_PER_HOUR


def calc_tts_cost(char_count: int) -> float:
    return (char_count / 1_000_000) * TTS_PER_M_CHARS


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                thread_id TEXT PRIMARY KEY,
                channel TEXT NOT NULL DEFAULT 'text',
                resolved INTEGER NOT NULL DEFAULT 0,
                escalated INTEGER NOT NULL DEFAULT 0,
                total_cost_usd REAL NOT NULL DEFAULT 0,
                turns INTEGER NOT NULL DEFAULT 0,
                last_agent TEXT,
                variant TEXT DEFAULT 'A',
                primary_intent TEXT,
                entry_mode TEXT DEFAULT 'free_text',
                customer_phone TEXT,
                cx_score REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                route_reason TEXT NOT NULL,
                message_preview TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT,
                confirmation_code TEXT NOT NULL,
                service_type TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                vehicle_model TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS escalations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                conversation_summary TEXT NOT NULL,
                ticket_id TEXT,
                handover_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                rating TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS intent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                intent TEXT NOT NULL,
                entry_mode TEXT NOT NULL DEFAULT 'free_text',
                converted INTEGER NOT NULL DEFAULT 0,
                conversion_tool TEXT,
                created_at TEXT NOT NULL,
                converted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS tool_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    conv_cols = {r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()}
    for col, typedef in [
        ("last_agent", "TEXT"),
        ("variant", "TEXT DEFAULT 'A'"),
        ("primary_intent", "TEXT"),
        ("entry_mode", "TEXT DEFAULT 'free_text'"),
        ("customer_phone", "TEXT"),
        ("cx_score", "REAL"),
    ]:
        if conv_cols and col not in conv_cols:
            conn.execute(f"ALTER TABLE conversations ADD COLUMN {col} {typedef}")

    esc_cols = {r[1] for r in conn.execute("PRAGMA table_info(escalations)").fetchall()}
    for col, typedef in [("ticket_id", "TEXT"), ("handover_json", "TEXT")]:
        if esc_cols and col not in esc_cols:
            conn.execute(f"ALTER TABLE escalations ADD COLUMN {col} {typedef}")

    book_cols = {r[1] for r in conn.execute("PRAGMA table_info(bookings)").fetchall()}
    if book_cols and "thread_id" not in book_cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN thread_id TEXT")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_intent(message: str) -> str | None:
    lower = message.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(k in lower for k in keywords):
            return intent
    return None


def ensure_variant(thread_id: str) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT variant FROM conversations WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        if row and row["variant"]:
            return row["variant"]
    variant = assign_variant(thread_id)
    now = _now()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT thread_id FROM conversations WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE conversations SET variant = ?, updated_at = ? WHERE thread_id = ?",
                (variant, now, thread_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO conversations
                    (thread_id, channel, resolved, escalated, total_cost_usd, turns, variant, created_at, updated_at)
                VALUES (?, 'text', 0, 0, 0, 0, ?, ?, ?)
                """,
                (thread_id, variant, now, now),
            )
    return variant


def log_intent(thread_id: str, intent: str, entry_mode: str = "free_text") -> None:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM intent_events WHERE thread_id = ? AND intent = ?",
            (thread_id, intent),
        ).fetchone()
        if existing:
            return
        conn.execute(
            """
            INSERT INTO intent_events (thread_id, intent, entry_mode, converted, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (thread_id, intent, entry_mode, _now()),
        )
        conn.execute(
            "UPDATE conversations SET primary_intent = ?, entry_mode = ?, updated_at = ? WHERE thread_id = ?",
            (intent, entry_mode, _now(), thread_id),
        )


def log_tool_event(thread_id: str, tool_name: str) -> None:
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tool_events (thread_id, tool_name, created_at) VALUES (?, ?, ?)",
            (thread_id, tool_name, now),
        )
        if tool_name in CONVERSION_TOOLS:
            intent_map = {
                "book_appointment": "booking",
                "lookup_vehicle_recall": "recall",
                "get_trade_in_quote": "tradein",
                "request_test_drive": "sales",
            }
            intent = intent_map.get(tool_name)
            if intent:
                existing = conn.execute(
                    "SELECT id FROM intent_events WHERE thread_id = ? AND intent = ?",
                    (thread_id, intent),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE intent_events
                        SET converted = 1, conversion_tool = ?, converted_at = ?
                        WHERE thread_id = ? AND intent = ?
                        """,
                        (tool_name, now, thread_id, intent),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO intent_events
                            (thread_id, intent, entry_mode, converted, conversion_tool, created_at, converted_at)
                        VALUES (?, ?, 'free_text', 1, ?, ?, ?)
                        """,
                        (thread_id, intent, tool_name, now, now),
                    )


def _infer_sentiment(reason: str, summary: str) -> str:
    text = f"{reason} {summary}".lower()
    if any(w in text for w in ("frustrated", "angry", "upset", "complaint", "unhappy")):
        return "frustrated"
    if any(w in text for w in ("urgent", "asap", "immediately")):
        return "urgent"
    return "neutral"


def build_handover_package(
    thread_id: str,
    reason: str,
    conversation_summary: str,
    *,
    customer: dict | None = None,
    routed_agent: str | None = None,
) -> dict:
    ticket_id = f"AF-TICKET-{uuid.uuid4().hex[:6].upper()}"
    with get_conn() as conn:
        conv = conn.execute(
            "SELECT primary_intent, last_agent, customer_phone, variant FROM conversations WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
    intent = conv["primary_intent"] if conv else None
    agent = routed_agent or (conv["last_agent"] if conv else None)
    sentiment = _infer_sentiment(reason, conversation_summary)
    vehicle = {}
    if customer and customer.get("vehicles"):
        vehicle = customer["vehicles"][0]
    return {
        "programme": "800-AF",
        "division": "Automotive",
        "ticket_id": ticket_id,
        "thread_id": thread_id,
        "intent": intent or "general",
        "routed_agent": agent or "handover",
        "variant": conv["variant"] if conv else "A",
        "reason": reason,
        "summary": conversation_summary,
        "sentiment": sentiment,
        "recommended_action": (
            "Priority callback within 2 hours"
            if sentiment in ("frustrated", "urgent")
            else "Advisor follow-up within 1 business day"
        ),
        "customer": customer or {},
        "vehicle": vehicle,
        "created_at": _now(),
    }


def upsert_conversation(
    thread_id: str,
    *,
    channel: str = "text",
    cost_delta: float = 0.0,
    resolved: bool | None = None,
    escalated: bool | None = None,
    last_agent: str | None = None,
    customer_phone: str | None = None,
    entry_mode: str | None = None,
) -> None:
    ensure_variant(thread_id)
    now = _now()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO conversations
                    (thread_id, channel, resolved, escalated, total_cost_usd, turns,
                     last_agent, entry_mode, customer_phone, variant, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread_id,
                    channel,
                    int(resolved or False),
                    int(escalated or False),
                    cost_delta,
                    last_agent,
                    entry_mode or "free_text",
                    customer_phone,
                    assign_variant_safe(thread_id),
                    now,
                    now,
                ),
            )
        else:
            new_resolved = int(resolved) if resolved is not None else row["resolved"]
            new_escalated = int(escalated) if escalated is not None else row["escalated"]
            new_agent = last_agent if last_agent is not None else row["last_agent"]
            new_phone = customer_phone if customer_phone is not None else row["customer_phone"]
            new_mode = entry_mode if entry_mode is not None else row["entry_mode"]
            conn.execute(
                """
                UPDATE conversations
                SET channel = ?, resolved = ?, escalated = ?,
                    total_cost_usd = total_cost_usd + ?, turns = turns + 1,
                    last_agent = ?, customer_phone = COALESCE(?, customer_phone),
                    entry_mode = COALESCE(?, entry_mode), updated_at = ?
                WHERE thread_id = ?
                """,
                (channel, new_resolved, new_escalated, cost_delta, new_agent, new_phone, new_mode, now, thread_id),
            )
    _update_cx_score(thread_id)


def assign_variant_safe(thread_id: str) -> str:
    return assign_variant(thread_id)


def _update_cx_score(thread_id: str) -> None:
    with get_conn() as conn:
        conv = conn.execute(
            "SELECT resolved, escalated, turns FROM conversations WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        if not conv:
            return
        fb = conn.execute(
            "SELECT rating FROM feedback WHERE thread_id = ? ORDER BY id DESC LIMIT 1",
            (thread_id,),
        ).fetchone()
        score = 0.0
        if conv["resolved"] and not conv["escalated"]:
            score += 40
        if conv["turns"] and conv["turns"] <= 6:
            score += 20
        if fb and fb["rating"] == "up":
            score += 25
        elif fb and fb["rating"] == "down":
            score += 0
        else:
            score += 10
        if not conv["escalated"]:
            score += 15
        conn.execute(
            "UPDATE conversations SET cx_score = ? WHERE thread_id = ?",
            (min(100.0, score), thread_id),
        )


def log_booking(
    confirmation_code: str,
    service_type: str,
    date: str,
    time: str,
    customer_name: str,
    vehicle_model: str,
    thread_id: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO bookings
                (thread_id, confirmation_code, service_type, date, time, customer_name, vehicle_model, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (thread_id, confirmation_code, service_type, date, time, customer_name, vehicle_model, _now()),
        )


def log_escalation(
    thread_id: str,
    reason: str,
    conversation_summary: str,
    *,
    handover_package: dict | None = None,
) -> int:
    package = handover_package or build_handover_package(thread_id, reason, conversation_summary)
    ticket_id = package["ticket_id"]
    handover_json = json.dumps(package, ensure_ascii=False)
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO escalations (thread_id, reason, conversation_summary, ticket_id, handover_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (thread_id, reason, conversation_summary, ticket_id, handover_json, _now()),
        )
        return cur.lastrowid or 0


def log_feedback(thread_id: str, rating: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO feedback (thread_id, rating, created_at) VALUES (?, ?, ?)",
            (thread_id, rating, _now()),
        )
    _update_cx_score(thread_id)


def log_agent_route(thread_id: str, agent: str, route_reason: str, message: str) -> None:
    preview = message.strip().replace("\n", " ")[:120]
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO agent_routes (thread_id, agent, route_reason, message_preview, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (thread_id, agent, route_reason, preview, _now()),
        )


def set_last_agent(thread_id: str, agent: str) -> None:
    now = _now()
    ensure_variant(thread_id)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT thread_id FROM conversations WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO conversations
                    (thread_id, channel, resolved, escalated, total_cost_usd, turns, last_agent, variant, created_at, updated_at)
                VALUES (?, 'text', 0, 0, 0, 0, ?, ?, ?, ?)
                """,
                (thread_id, agent, assign_variant_safe(thread_id), now, now),
            )
        else:
            conn.execute(
                "UPDATE conversations SET last_agent = ?, updated_at = ? WHERE thread_id = ?",
                (agent, now, thread_id),
            )


def get_last_agent(thread_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_agent FROM conversations WHERE thread_id = ?", (thread_id,)
        ).fetchone()
    if row and row["last_agent"]:
        return row["last_agent"]
    return None


def list_agent_routes(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT thread_id, agent, route_reason, message_preview, created_at
            FROM agent_routes ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def _conversion_rate(converted: int, total: int) -> float:
    return round(converted / total, 4) if total else 0.0


def aggregate_metrics() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS conversation_count,
                COALESCE(SUM(resolved), 0) AS resolved_count,
                COALESCE(SUM(escalated), 0) AS escalated_count,
                COALESCE(SUM(total_cost_usd), 0) AS total_cost_usd,
                COALESCE(AVG(cx_score), 0) AS avg_cx_score
            FROM conversations
            """
        ).fetchone()

        route_rows = conn.execute(
            "SELECT agent, COUNT(*) AS cnt FROM agent_routes GROUP BY agent ORDER BY cnt DESC"
        ).fetchall()

        booking_count = conn.execute("SELECT COUNT(*) AS c FROM bookings").fetchone()["c"]
        intent_rows = conn.execute(
            """
            SELECT intent, entry_mode,
                   COUNT(*) AS starts,
                   COALESCE(SUM(converted), 0) AS converted
            FROM intent_events GROUP BY intent, entry_mode
            """
        ).fetchall()

        variant_rows = conn.execute(
            """
            SELECT variant,
                   COUNT(*) AS conversations,
                   COALESCE(SUM(resolved), 0) AS resolved,
                   COALESCE(AVG(cx_score), 0) AS avg_cx
            FROM conversations WHERE variant IS NOT NULL GROUP BY variant
            """
        ).fetchall()

        fb_rows = conn.execute(
            """
            SELECT rating, COUNT(*) AS cnt FROM feedback GROUP BY rating
            """
        ).fetchall()

    count = row["conversation_count"] or 0
    resolved = row["resolved_count"] or 0
    escalated = row["escalated_count"] or 0
    total_cost = row["total_cost_usd"] or 0.0

    conversions: dict[str, dict] = {}
    for r in intent_rows:
        key = r["intent"]
        if key not in conversions:
            conversions[key] = {"starts": 0, "converted": 0, "by_mode": {}}
        conversions[key]["starts"] += r["starts"]
        conversions[key]["converted"] += r["converted"]
        conversions[key]["by_mode"][r["entry_mode"]] = {
            "starts": r["starts"],
            "converted": r["converted"],
            "rate": _conversion_rate(r["converted"], r["starts"]),
        }

    for key, data in conversions.items():
        data["rate"] = _conversion_rate(data["converted"], data["starts"])

    booking_conv = conversions.get("booking", {"starts": 0, "converted": 0})
    return {
        "conversation_count": count,
        "resolved_count": resolved,
        "escalated_count": escalated,
        "resolution_rate": round(resolved / count, 4) if count else 0.0,
        "escalation_rate": round(escalated / count, 4) if count else 0.0,
        "total_cost_usd": round(total_cost, 6),
        "cost_per_resolution_usd": round(total_cost / resolved, 6) if resolved else 0.0,
        "avg_cx_score": round(row["avg_cx_score"] or 0, 1),
        "booking_count": booking_count,
        "booking_conversion_rate": _conversion_rate(
            booking_conv.get("converted", 0),
            booking_conv.get("starts", 0),
        ),
        "conversions": conversions,
        "routes_by_agent": {r["agent"]: r["cnt"] for r in route_rows},
        "feedback_summary": {r["rating"]: r["cnt"] for r in fb_rows},
        "experiments": {
            r["variant"]: {
                "conversations": r["conversations"],
                "resolved": r["resolved"],
                "resolution_rate": round(r["resolved"] / r["conversations"], 4) if r["conversations"] else 0,
                "avg_cx_score": round(r["avg_cx"] or 0, 1),
            }
            for r in variant_rows
        },
    }


def get_admin_dashboard() -> dict:
    with get_conn() as conn:
        bookings = conn.execute(
            "SELECT * FROM bookings ORDER BY id DESC LIMIT 25"
        ).fetchall()
        escalations = conn.execute(
            "SELECT id, thread_id, reason, ticket_id, handover_json, created_at FROM escalations ORDER BY id DESC LIMIT 25"
        ).fetchall()
        feedback = conn.execute(
            "SELECT thread_id, rating, created_at FROM feedback ORDER BY id DESC LIMIT 25"
        ).fetchall()
        routes = conn.execute(
            "SELECT thread_id, agent, route_reason, message_preview, created_at FROM agent_routes ORDER BY id DESC LIMIT 30"
        ).fetchall()
        intents = conn.execute(
            "SELECT thread_id, intent, entry_mode, converted, conversion_tool, created_at FROM intent_events ORDER BY id DESC LIMIT 30"
        ).fetchall()
        conversations = conn.execute(
            """
            SELECT thread_id, channel, resolved, escalated, turns, last_agent, variant,
                   primary_intent, entry_mode, cx_score, total_cost_usd, updated_at
            FROM conversations ORDER BY updated_at DESC LIMIT 30
            """
        ).fetchall()

    esc_list = []
    for e in escalations:
        item = dict(e)
        if item.get("handover_json"):
            try:
                item["handover"] = json.loads(item["handover_json"])
            except json.JSONDecodeError:
                item["handover"] = {}
        esc_list.append(item)

    return {
        "metrics": aggregate_metrics(),
        "bookings": [dict(b) for b in bookings],
        "escalations": esc_list,
        "feedback": [dict(f) for f in feedback],
        "routes": [dict(r) for r in routes],
        "intents": [dict(i) for i in intents],
        "conversations": [dict(c) for c in conversations],
    }
