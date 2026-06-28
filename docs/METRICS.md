# Metrics & Analytics Guide

**System:** Al Futtaim Automotive Concierge  
**Source of truth:** `metrics/store.py`  
**Surfaces:** `GET /metrics`, `GET /admin/dashboard`, `static/admin.html`

---

## 1. Philosophy

Metrics answer three product questions:

1. **Containment** — Did we resolve without a human?  
2. **Conversion** — Did high-intent journeys complete via tools?  
3. **Efficiency** — What does each resolution cost in inference spend?

All metrics are derived from SQLite event tables populated during live conversations.

---

## 2. Core KPIs

### Resolution rate

```
resolved_count / conversation_count
```

- A conversation is **resolved** when the latest turn does **not** call `escalate_to_human`.  
- Updated on each `upsert_conversation` after every text/voice turn.  
- **Target (demo):** &gt; 70% on happy-path scenarios.

### Escalation rate

```
escalated_count / conversation_count
```

- **Escalated** when `escalate_to_human` appears in tool calls for that turn.  
- Inverse signal to resolution (not identical due to multi-turn threads).

### Cost per resolution

```
total_cost_usd / resolved_count
```

Includes LLM tokens (all turns) plus STT/TTS on voice channel.

### Average CX score

Composite per conversation (0–100):

- Base from resolution outcome  
- Adjusted for turn count and thumbs up/down feedback  

Stored on `conversations.cx_score`.

---

## 3. Conversion funnels

### Intent detection

On each message, `detect_intent()` keyword-matches against:

| Intent | Example keywords |
|--------|------------------|
| `booking` | book, appointment, service, oil change, حجز |
| `recall` | recall, استدعاء |
| `tradein` | trade-in, valuation, استبدال |
| `sales` | test drive, buy a car |

First match per thread per intent → `log_intent()` creates one `intent_events` row (**start**).

### Conversion

When a conversion tool succeeds:

| Tool | Intent |
|------|--------|
| `book_appointment` | booking |
| `lookup_vehicle_recall` | recall |
| `get_trade_in_quote` | tradein |
| `request_test_drive` | sales |

`intent_events.converted` set to 1; `conversion_tool` recorded.

### Conversion rate (per intent)

```
converted / starts
```

- **starts** — rows in `intent_events` for that intent  
- **converted** — sum of `converted` flag (0 or 1 per row)  
- Always ≤ 100% when using this formula  

### Booking conversion (dashboard card)

```
booking_converted / booking_starts
```

Uses `intent_events` for booking — **not** raw `bookings` table count.

> **Note:** `booking_count` (total rows in `bookings`) can exceed `starts` when one thread books multiple times. The conversion **rate** uses intent conversions, not booking row count.

### Entry mode breakdown

`intent_events.entry_mode`:

| Mode | Meaning |
|------|---------|
| `free_text` | Natural typing |
| `guided` | Wizard confirm message |
| `voice` | Voice channel |

Compare `guided` vs `free_text` conversion in funnel table `by_mode`.

---

## 4. A/B experiments

| Field | Description |
|-------|-------------|
| `conversations.variant` | A or B per thread |
| Variant A | Base prompts, max_tokens 320 |
| Variant B | Brevity addendum, max_tokens 256 |

Dashboard **Experiments** section shows per variant:

- Conversation count  
- Resolution rate  
- Average CX score  

---

## 5. Routing analytics

### `agent_routes` table

Each turn logs:

| Column | Example |
|--------|---------|
| `agent` | service |
| `route_reason` | keyword_service, sticky_follow_up, llm_router |
| `message_preview` | First 200 chars of user message |

**Use cases:**

- Audit misroutes  
- Prove multi-agent orchestration in demos  
- Tune keyword lists vs LLM fallback rate  

Access via `GET /admin/routes` or **Routing log** button in chat UI.

---

## 6. Escalation & handover metrics

### `escalations` table

| Column | Description |
|--------|-------------|
| `ticket_id` | `AF-TICKET-XXXXXX` |
| `handover_json` | Full 800-AF package |
| `reason` | Escalation trigger |
| `conversation_summary` | Agent-provided summary |

### Handover package fields

```json
{
  "programme": "800-AF",
  "division": "Automotive",
  "ticket_id": "AF-TICKET-…",
  "thread_id": "…",
  "intent": "booking",
  "routed_agent": "service",
  "variant": "A",
  "reason": "…",
  "summary": "…",
  "sentiment": "neutral | frustrated | urgent",
  "recommended_action": "…",
  "customer": { },
  "vehicle": { }
}
```

---

## 7. Bookings table

Separate from funnel — logs every `book_appointment` success:

| Column | Example |
|--------|---------|
| `confirmation_code` | AF-A1B2C3D4 |
| `service_type` | Oil change |
| `vehicle_model` | 2020 Toyota Camry |
| `thread_id` | UUID link to conversation |

Ops dashboard **Recent bookings** lists latest 25.

---

## 8. Feedback

`POST /feedback` with `rating: "up" | "down"` affects CX score for the thread.

---

## 9. API examples

```bash
# Aggregate metrics
curl -s http://localhost:8080/metrics | python3 -m json.tool

# Full dashboard payload
curl -s http://localhost:8080/admin/dashboard | python3 -m json.tool

# Routing log
curl -s "http://localhost:8080/admin/routes?limit=10" | python3 -m json.tool
```

### Sample `/metrics` response shape

```json
{
  "conversation_count": 12,
  "resolution_rate": 0.8333,
  "escalation_rate": 0.1667,
  "cost_per_resolution_usd": 0.000412,
  "booking_count": 8,
  "booking_conversion_rate": 0.6667,
  "conversions": {
    "booking": {
      "starts": 3,
      "converted": 2,
      "rate": 0.6667,
      "by_mode": {
        "guided": { "starts": 2, "converted": 1, "rate": 0.5 },
        "free_text": { "starts": 1, "converted": 1, "rate": 1.0 }
      }
    }
  },
  "experiments": {
    "A": { "conversations": 7, "resolution_rate": 0.8571, "avg_cx_score": 78.2 },
    "B": { "conversations": 5, "resolution_rate": 0.8, "avg_cx_score": 75.0 }
  }
}
```

---

## 10. Dashboard interpretation guide

| Card / table | Read as |
|--------------|---------|
| Conversations | Total unique threads |
| Resolution rate | Containment health |
| Escalation rate | Handover pressure |
| Cost / resolution | Unit economics |
| Bookings | Absolute completed appointments |
| Booking conversion | % of booking intents that converted |
| Conversion funnel table | Per-intent starts → converted |
| Experiments | A/B prompt performance |
| Escalations + JSON | Handover quality for CRM integration |

---

## 11. Related documents

- [PRD.md](PRD.md) — success metrics requirements  
- [TECHNICAL.md](TECHNICAL.md) — schema details  
- [ARCHITECTURE.md](ARCHITECTURE.md) — where events are logged
