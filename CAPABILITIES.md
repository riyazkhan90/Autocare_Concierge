# Al Futtaim Automotive Concierge — Capabilities & Demo Guide

Portfolio reference for **Product Owner – Conversational AI** roles.  
One agent brain, two channels (text + voice), measurable product metrics, **800-AF multi-agent orchestration**.

---

## Customer services

| Service | Agent | Tool | What the customer gets |
|---------|-------|------|------------------------|
| **Service availability** | Service | `check_appointment_availability` | Up to 3 mock slots near a preferred date |
| **Service booking** | Service | `book_appointment` | `AF-` confirmation code; logged to SQLite |
| **Recall lookup** | Recall | `lookup_vehicle_recall` | Open recalls by make, model, year |
| **Trade-in estimate** | Sales | `get_trade_in_quote` | Formula-based estimate |
| **Test drive** | Sales | `request_test_drive` | Mock `TD-` request ID |
| **Service centre locator** | Service / General | `find_service_center` | Centres by UAE city |
| **Customer profile** | All | `get_customer_profile` | Mock vehicle-on-file lookup |
| **Human handover** | Handover | `escalate_to_human` | Structured 800-AF JSON + `AF-TICKET-` ID |

---

## Multi-agent orchestration (800-AF)

| Agent | Routes from | Tools |
|-------|-------------|-------|
| **Service** | booking, maintenance keywords | availability, book, profile, centres, escalate |
| **Sales** | trade-in, test drive | trade-in, test drive, profile, escalate |
| **Recall** | recall keywords | recall lookup, profile, escalate |
| **Handover** | human / frustration | escalate only |
| **General** | greetings, FAQs | profile, centres, escalate |

Routing: keyword → sticky follow-up → LLM classifier. Logged to `agent_routes`.

---

## Product & platform features

| Feature | Where | Why it matters (PO lens) |
|---------|-------|--------------------------|
| **Resolution rate** | `GET /metrics` | Containment without escalation |
| **Conversion funnels** | `GET /metrics`, `/admin/dashboard` | Booking/recall/trade-in starts → converted |
| **Escalation rate** | metrics | Handover quality signal |
| **Cost per resolution** | metrics | LLM + STT + TTS unit economics |
| **CX quality score** | per conversation | Resolved + turns + feedback composite |
| **A/B experiments** | Variant A vs B per `thread_id` | Hypothesis-driven prompt iteration |
| **Structured handover** | `escalations.handover_json` | CRM-ready 800-AF package |
| **Ops dashboard** | `/admin` | Live interaction data for iteration |
| **Guided journeys** | `static/index.html` | Booking, recall, trade-in wizards |
| **Thread-guided follow-ups** | UI on agent OPTIONS | Guided steps from conversation context |
| **Demo customer profile** | Welcome → Sara Ahmed | Personalisation without re-asking |
| **Multi-agent routing log** | `GET /admin/routes` | Orchestration audit trail |

---

## 5-minute hiring manager demo

1. **Open UI** — http://localhost:8080  
2. **Load demo customer** → book service → **Service Agent** badge → `AF-` code  
3. **Trade-in** → **Sales Agent** badge  
4. **Escalate** → ticket `AF-TICKET-…` in reply  
5. **Ops dashboard** — http://localhost:8080/admin — conversions, A/B, handover JSON  
6. **Routing log** — show multi-agent decisions  

Full documentation: **[docs/README.md](docs/README.md)** (PRD, architecture, technical spec, prompts, metrics).

---

## API quick reference

```bash
curl -s http://localhost:8080/metrics | python3 -m json.tool
curl -s http://localhost:8080/admin/dashboard | python3 -m json.tool
curl -s http://localhost:8080/customer/demo/sara | python3 -m json.tool
```

---

## Roadmap (integration points)

- Al-Futtaim Auto Centers / DMS booking API  
- Live recall OEM feed  
- CRM push on escalation (Salesforce, Dynamics)  
- Arabic TTS end-to-end  
- LangGraph supervisor visual graph  
