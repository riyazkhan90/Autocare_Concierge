# Technical Specification

**System:** Al Futtaim Automotive Concierge  
**Version:** 1.0

---

## 1. Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Groq API key | Free tier at [console.groq.com](https://console.groq.com) |

---

## 2. Setup & run

```bash
cp .env.example .env
# Set GROQ_API_KEY in .env

uv sync
uv run uvicorn main:app --reload --port 8080
```

| URL | Purpose |
|-----|---------|
| http://localhost:8080 | Chat UI |
| http://localhost:8080/admin | Ops dashboard |
| http://localhost:8080/health | Health check |

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API authentication |
| `SKIP_TTS` | No | `true` to use browser TTS instead of Orpheus (saves quota) |

---

## 3. Project structure

```
Autocare_Concierge/
├── main.py                 # FastAPI app, chat/voice endpoints
├── agent/
│   ├── graph.py            # Multi-agent orchestrator, run_agent()
│   ├── router.py           # Intent routing (keyword + LLM + sticky)
│   ├── prompts.py          # System prompts (all specialists + router)
│   ├── tools.py            # LangChain tools (mock business logic)
│   ├── context.py          # Per-thread runtime context
│   ├── customers.py        # Mock CRM profiles
│   └── experiments.py      # A/B variant assignment
├── metrics/
│   └── store.py            # SQLite schema, logging, aggregates
├── static/
│   ├── index.html          # Chat + voice + guided wizards
│   ├── admin.html          # Ops dashboard
│   ├── theme.css / theme.js
│   └── alfuttaim-*.svg     # Brand assets
├── data/
│   └── alfuttaim.db        # SQLite (created at startup)
└── docs/                   # Documentation
```

---

## 4. API reference

### 4.1 Health & metrics

#### `GET /health`

```json
{ "status": "ok" }
```

#### `GET /metrics`

Returns `aggregate_metrics()` — resolution, escalation, conversions, A/B, costs.

#### `GET /admin/dashboard`

Returns metrics plus recent bookings, escalations (with handover JSON), intents, conversations.

#### `GET /admin/routes?limit=50`

Returns multi-agent routing log (max 200).

---

### 4.2 Chat

#### `POST /chat/text`

**Request body:**

```json
{
  "message": "Book an oil change for my 2020 Toyota Camry",
  "thread_id": "uuid-string",
  "entry_mode": "free_text",
  "customer_phone": "+971501234567"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `message` | string | required | User message |
| `thread_id` | string | required | Conversation ID (client-generated UUID) |
| `entry_mode` | `"free_text"` \| `"guided"` \| `"voice"` | `"free_text"` | Journey attribution |
| `customer_phone` | string \| null | null | Optional CRM lookup |

**Response:**

```json
{
  "reply": "…",
  "thread_id": "…",
  "cost_breakdown": {
    "llm_input_tokens": 1200,
    "llm_output_tokens": 85,
    "llm_cost_usd": 0.000231,
    "extra_cost_usd": 0,
    "total_cost_usd": 0.000231,
    "escalated": false,
    "routed_agent": "service",
    "route_reason": "keyword_service",
    "variant": "A"
  },
  "routed_agent": "service",
  "agent_label": "Service Agent",
  "route_reason": "keyword_service",
  "variant": "A",
  "customer_greeting": "Welcome back, Sara! …"
}
```

---

#### `POST /chat/voice`

**Multipart form:**

| Field | Type | Description |
|-------|------|-------------|
| `audio` | file | WebM/audio recording |
| `thread_id` | string | Conversation ID |
| `duration_seconds` | float | Recording length (for STT cost) |

**Response:** transcript, reply_text, audio_base64 (or `use_browser_tts: true`), cost_breakdown with STT/TTS lines.

---

### 4.3 Feedback & customer

#### `POST /feedback`

```json
{ "thread_id": "…", "rating": "up" }
```

#### `GET /customer/{phone}`

Returns mock profile or 404.

#### `GET /customer/demo/sara`

Returns Sara Ahmed demo profile (`+971501234567`).

---

## 5. Agent execution

### `run_agent(message, thread_id) → AgentResult`

1. `ensure_variant(thread_id)` — A/B assignment  
2. `route_message(message, thread_id)` — select specialist  
3. `log_agent_route(...)` — audit  
4. Invoke LangGraph ReAct agent with `MemorySaver` checkpoint  
5. On tool parse error: retry once with booking JSON hint  
6. Return reply, tokens, escalation flag, tool names  

### Tool inventory

| Tool | Conversion intent | Side effects |
|------|-------------------|--------------|
| `check_appointment_availability` | — | None |
| `book_appointment` | booking | `bookings` row, `intent_events.converted` |
| `lookup_vehicle_recall` | recall | `intent_events.converted` |
| `get_trade_in_quote` | tradein | `intent_events.converted` |
| `request_test_drive` | sales | `intent_events.converted` |
| `escalate_to_human` | — | `escalations` row + handover JSON |
| `get_customer_profile` | — | None |
| `find_service_center` | — | None |

---

## 6. Database schema

### `conversations`

| Column | Type | Description |
|--------|------|-------------|
| `thread_id` | TEXT PK | Client conversation ID |
| `channel` | TEXT | `text` or `voice` |
| `resolved` | INTEGER | 1 if not escalated on last turn |
| `escalated` | INTEGER | 1 if `escalate_to_human` called |
| `total_cost_usd` | REAL | Cumulative inference cost |
| `turns` | INTEGER | Message count |
| `last_agent` | TEXT | Last routed specialist |
| `variant` | TEXT | A or B |
| `primary_intent` | TEXT | Detected intent |
| `entry_mode` | TEXT | First entry mode |
| `customer_phone` | TEXT | Optional |
| `cx_score` | REAL | Composite quality score |

### `intent_events`

| Column | Description |
|--------|-------------|
| `intent` | `booking`, `recall`, `tradein`, `sales` |
| `entry_mode` | `free_text`, `guided`, `voice` |
| `converted` | 1 when conversion tool succeeds |
| `conversion_tool` | Tool name that converted |

One row per `(thread_id, intent)` — deduplicated on `log_intent`.

### `escalations`

Includes `handover_json` — full 800-AF package (see ARCHITECTURE.md).

---

## 7. Cost model

Defined in `metrics/store.py`:

| Component | Rate |
|-----------|------|
| LLM input | $0.15 / 1M tokens |
| LLM output | $0.60 / 1M tokens |
| STT | $0.04 / hour |
| TTS | $22 / 1M characters |

---

## 8. Groq models

| Use | Model |
|-----|-------|
| Chat + routing + tools | `openai/gpt-oss-120b` |
| Speech-to-text | `whisper-large-v3-turbo` |
| Text-to-speech | `canopylabs/orpheus-v1-english` (voice: `austin`) |

### Known constraints

- **Tool JSON truncation:** `max_tokens` set to 320 (A) / 256 (B); retry on parse failure for booking  
- **TTS quota:** Free tier ~3600 TPD; use `SKIP_TTS=true` for demos  
- **Orpheus terms:** One-time acceptance required in Groq console if TTS fails  

---

## 9. UI technical notes

### OPTIONS protocol

Assistant may end replies with:

```
OPTIONS: Toyota | Lexus | Honda | Ford
```

UI parses this for reply chips or guided wizard mounting.

### Guided wizard flows

Configured in `FLOW_CONFIG` in `index.html`. Confirm step sends `flow.buildMessage(state)` with `entry_mode: "guided"`.

### Theme

`localStorage` key: `alfuttaim_theme` (`light` | `dark`).

---

## 10. Development & testing

```bash
# Health
curl -s http://localhost:8080/health

# Metrics
curl -s http://localhost:8080/metrics | python3 -m json.tool

# Text chat
curl -s -X POST http://localhost:8080/chat/text \
  -H "Content-Type: application/json" \
  -d '{"message":"Check recalls for 2020 Toyota Camry","thread_id":"test-001"}'

# Demo customer
curl -s http://localhost:8080/customer/demo/sara | python3 -m json.tool
```

---

## 11. Related documents

- [ARCHITECTURE.md](ARCHITECTURE.md)  
- [PROMPTS.md](PROMPTS.md)  
- [METRICS.md](METRICS.md)
