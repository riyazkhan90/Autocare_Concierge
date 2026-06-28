# Al Futtaim Automotive Concierge

A conversational AI for **Al Futtaim Automotive** service and sales — one agent brain serving both **text chat** and **voice**, built entirely on [Groq](https://console.groq.com) (free tier, no credit card required).

Designed for a multi-brand mobility group operating across the UAE and GCC (passenger vehicles, aftersales, and Al-Futtaim Auto Centers).

## Architecture

```
┌─────────────┐     ┌─────────────┐
│  Text Chat  │     │ Voice Chat  │
│ POST /chat/ │     │ POST /chat/ │
│    text     │     │   voice     │
└──────┬──────┘     └──────┬──────┘
       │                   │
       │            Whisper STT (groq SDK)
       │                   │
       └────────┬──────────┘
                ▼
     ┌──────────────────────┐
     │   Router (800-AF)    │
     │  keyword + LLM route │
     └──────────┬───────────┘
                │
    ┌───────────┼───────────┬───────────┐
    ▼           ▼           ▼           ▼
 Service     Sales       Recall    Handover/General
 Agent       Agent       Agent         Agent
    │           │           │           │
    └───────────┴───────────┴───────────┘
                │
       SQLite metrics + agent_routes log
```

**Stack:** Python 3.11 · uv · FastAPI · LangGraph · langchain-groq · groq SDK · SQLite

| Channel | Groq model | Purpose |
|---------|-----------|---------|
| Chat + tools | `openai/gpt-oss-120b` | Reasoning, tool calling |
| Voice in | `whisper-large-v3-turbo` | Speech-to-text |
| Voice out | `canopylabs/orpheus-v1-english` | Text-to-speech |

No vector database, no RAG, no additional APIs.

## Capabilities & demo script

See **[CAPABILITIES.md](CAPABILITIES.md)** for the full services matrix, platform features, real-vs-mocked breakdown, and a **5-minute live demo script** for Product Owner interviews.

## Documentation

Full product and technical documentation lives in **[docs/](docs/README.md)**:

| Document | Description |
|----------|-------------|
| [PRD](docs/PRD.md) | Product requirements, user stories, success metrics |
| [Architecture](docs/ARCHITECTURE.md) | System design, multi-agent flow, data architecture |
| [Technical](docs/TECHNICAL.md) | API reference, schema, setup, configuration |
| [Prompts](docs/PROMPTS.md) | Prompt engineering guide, routing, A/B variants |
| [Metrics](docs/METRICS.md) | KPI definitions, funnels, dashboard interpretation |
| [Deployment](docs/DEPLOYMENT.md) | Railway deployment guide |

## JD requirement mapping

| Role requirement | Implementation |
|-----------------|----------------|
| Hands-on building (not just spec'ing) | Full Python codebase: FastAPI, LangGraph agent, SQLite metrics, static UI |
| Conversational AI + escalation | `escalate_to_human` + structured `AF-TICKET-` 800-AF handover JSON |
| Human handover logic | Ops dashboard → escalations with full handover package |
| Resolution + conversion + cost metrics | `/metrics` + `/admin/dashboard` |
| Multi-agent orchestration | Router → Service / Sales / Recall / Handover / General |
| A/B experiments | Variant A vs B assigned per `thread_id` |
| Builder-first / AI dev tools | Built with [Cursor](https://cursor.com) |

## Disclaimer

> Recall data, trade-in quotes, and appointment slots are **mocked** for this portfolio demo — the agent architecture, escalation logic, and cost-tracking are real and production-shaped. This is not an official Al Futtaim product; branding is used for demonstration purposes.

## Setup

```bash
cp .env.example .env
# Add your GROQ_API_KEY from https://console.groq.com (free, no credit card)

uv run uvicorn main:app --reload --port 8080
```

**Security:** Put your real key only in `.env` (gitignored). Never commit `.env` or paste keys into `.env.example` — that file is tracked and must stay as `your_key_here`.

**Demo TTS limit:** Groq Orpheus free tier caps at ~3600 TPD (tokens per day). For demos, set `SKIP_TTS=true` in `.env` — voice replies use the browser's built-in speech instead (no Groq TTS quota used).

Open http://localhost:8080

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Resolution, conversion, CX, cost, A/B experiments |
| POST | `/chat/text` | `{message, thread_id, entry_mode?, customer_phone?}` |
| POST | `/chat/voice` | Multipart audio + `duration_seconds` → transcript, reply, audio |
| POST | `/feedback` | `{thread_id, rating: "up"\|"down"}` |
| GET | `/admin/dashboard` | Full ops dashboard JSON |
| GET | `/admin/routes` | Multi-agent routing log |
| GET | `/customer/{phone}` | Mock customer profile |
| GET | `/customer/demo/sara` | Demo profile for portfolio |
| GET | `/admin` | Ops dashboard UI |

## Cost rates (metrics)

| Component | Rate |
|-----------|------|
| GPT OSS 120B input | $0.15 / 1M tokens |
| GPT OSS 120B output | $0.60 / 1M tokens |
| Whisper Large v3 Turbo | $0.04 / hour of audio |
| Orpheus TTS English | $22 / 1M characters |

## Project structure

```
agent/
  router.py   # Intent router (keyword + LLM)
  prompts.py  # Specialist system prompts
  tools.py    # LangChain tools (mocked business logic)
  graph.py    # Multi-agent orchestrator + MemorySaver
metrics/
  store.py    # SQLite persistence + aggregate_metrics()
main.py       # FastAPI app
static/
  index.html  # Chat + voice UI
```

## Multi-agent specialists (800-AF)

| Agent | Tools | Handles |
|-------|-------|---------|
| **Service** | availability, book, escalate | Workshop appointments, maintenance |
| **Sales** | trade-in, test drive, escalate | Valuations, test drives |
| **Recall** | recall lookup, escalate | Safety recall campaigns |
| **Handover** | escalate | Explicit human requests, frustration |
| **General** | escalate | Greetings, general FAQs |

Routing: keyword match → sticky follow-up → LLM classifier. Each turn logged to `agent_routes`.

## Tools

1. **check_appointment_availability** — mock slots near a preferred date
2. **book_appointment** — `AF-` confirmation code + SQLite log
3. **lookup_vehicle_recall** — hardcoded recall dict
4. **get_trade_in_quote** — formula-based estimate
5. **request_test_drive** — mock test drive request ID
6. **escalate_to_human** — handover summary logged for Al Futtaim advisor follow-up
