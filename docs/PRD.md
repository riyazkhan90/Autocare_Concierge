# Product Requirements Document (PRD)

**Product:** Al Futtaim Automotive Concierge (800-AF)  
**Version:** 1.0 (portfolio demo)  
**Status:** Demo-ready  
**Last updated:** June 2026

---

## 1. Executive summary

Build a unified conversational assistant for Al Futtaim Automotive customers across **service** and **sales** journeys — via **text** and **voice** — with measurable containment, conversion, and handover quality. The assistant routes to specialist agents, completes actions through tools where possible, and escalates to human advisors with structured context when needed.

This PRD describes the **portfolio demonstration** implementation. Production rollout would replace mocked backends (DMS, recall OEM feed, CRM) with live integrations while preserving the same product surfaces.

---

## 2. Problem statement

Automotive customers in the UAE contact Al Futtaim for:

- Workshop appointments (all makes, Al-Futtaim Auto Centers)
- Safety recall enquiries
- Trade-in valuations and test drives
- General service centre and programme questions

Today these interactions are fragmented across phone, web forms, and in-dealer touchpoints. A conversational layer can:

- Reduce repeat data entry
- Improve first-contact resolution
- Capture structured handovers when humans are required
- Provide product metrics to iterate prompts and journeys

---

## 3. Goals & non-goals

### Goals

| ID | Goal |
|----|------|
| G1 | Single agent brain serving text and voice channels |
| G2 | Multi-agent routing to Service, Sales, Recall, Handover, General specialists |
| G3 | Complete high-intent journeys via tools (book, recall lookup, trade-in, test drive) |
| G4 | Structured 800-AF escalation with ticket ID and CRM-ready JSON |
| G5 | Product metrics: resolution, escalation, conversion funnels, cost per resolution, CX score |
| G6 | Guided UI journeys for booking, recall, and trade-in |
| G7 | A/B prompt experiments per conversation thread |
| G8 | Ops dashboard for live iteration |

### Non-goals (demo scope)

- Production CRM / DMS integration
- Live OEM recall API
- Arabic TTS end-to-end
- Admin authentication and RBAC
- PCI / PII compliance certification
- Official Al Futtaim brand approval

---

## 4. Users & personas

| Persona | Needs | Primary journeys |
|---------|-------|------------------|
| **Service customer** | Book maintenance, check slots, find centres | Booking wizard, free text |
| **Recall-conscious owner** | Check open campaigns | Recall lookup |
| **Trade-in prospect** | Ballpark valuation before visit | Trade-in wizard |
| **Sales prospect** | Schedule test drive | Free text / agent-led |
| **Frustrated caller** | Speak to a human quickly | Handover / escalation |
| **Returning customer (Sara demo)** | Personalised greeting, vehicle on file | Demo profile load |
| **Product / ops team** | Funnels, routing audit, handover review | Admin dashboard |

---

## 5. User stories

### Service

- As a customer, I can book a service appointment and receive an **AF-** confirmation code.
- As a customer, I can check availability near a preferred date before confirming.
- As a customer, I can find service centres by UAE city.

### Sales

- As a customer, I can get a trade-in estimate using make, model, year, mileage band, and condition.
- As a customer, I can request a test drive and receive a **TD-** request ID.

### Recall

- As a customer, I can look up open recalls by make, model, and year.

### Handover

- As a customer, I can ask for a human advisor and receive a ticket **AF-TICKET-** reference.
- As an advisor, I receive a structured handover package (intent, sentiment, vehicle, summary).

### Product / ops

- As a PO, I can see resolution rate, escalation rate, and cost per resolution.
- As a PO, I can compare conversion funnels by intent and entry mode (guided vs free text).
- As a PO, I can audit which specialist agent handled each turn.

---

## 6. Functional requirements

### 6.1 Channels

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-CH-1 | Text chat via web UI | P0 |
| FR-CH-2 | Voice input (hold-to-talk) with STT | P0 |
| FR-CH-3 | Voice output via TTS or browser fallback | P1 |
| FR-CH-4 | Bilingual prompts (EN/AR reply matching) | P1 |

### 6.2 Agent orchestration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-OR-1 | Route to Service, Sales, Recall, Handover, or General agent | P0 |
| FR-OR-2 | Keyword routing for high-confidence intents | P0 |
| FR-OR-3 | Sticky follow-up (short replies stay with same agent) | P0 |
| FR-OR-4 | LLM fallback router when keywords do not match | P1 |
| FR-OR-5 | Log every routing decision with reason | P0 |

### 6.3 Tools & integrations (mocked)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-TL-1 | `book_appointment` → AF confirmation + SQLite log | P0 |
| FR-TL-2 | `lookup_vehicle_recall` → mock recall dict | P0 |
| FR-TL-3 | `get_trade_in_quote` → formula estimate, mileage bands | P0 |
| FR-TL-4 | `request_test_drive` → TD request ID | P1 |
| FR-TL-5 | `escalate_to_human` → ticket + handover JSON | P0 |
| FR-TL-6 | `get_customer_profile` → demo CRM lookup | P1 |
| FR-TL-7 | `find_service_center` → UAE centre list | P1 |

### 6.4 Guided journeys (UI)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-UI-1 | Multi-step wizard for booking, recall, trade-in | P0 |
| FR-UI-2 | Progress indicator and editable collected chips | P0 |
| FR-UI-3 | Thread-guided follow-up when agent asks OPTIONS | P1 |
| FR-UI-4 | Agent badge on each assistant reply | P1 |
| FR-UI-5 | Light / dark theme | P2 |

### 6.5 Metrics & dashboard

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-MT-1 | Resolution and escalation rates | P0 |
| FR-MT-2 | Intent conversion funnels (starts → converted) | P0 |
| FR-MT-3 | Cost per resolution (LLM + STT + TTS) | P0 |
| FR-MT-4 | A/B variant assignment and comparison | P1 |
| FR-MT-5 | Ops dashboard with bookings, escalations, routing | P0 |

---

## 7. Success metrics

| Metric | Definition | Demo target (indicative) |
|--------|------------|----------------------------|
| **Resolution rate** | Conversations not escalated / total conversations | > 70% in happy-path demos |
| **Escalation rate** | Escalated / total conversations | < 30% |
| **Booking conversion** | Booking intents converted via tool / intent starts | Track; compare guided vs free text |
| **Cost per resolution** | Total inference cost / resolved conversations | Visible and trending down with prompt tuning |
| **CX score** | Composite: resolution + turns + feedback | > 70 average |
| **Time to handover** | Turns until `escalate_to_human` when requested | ≤ 2 turns |

---

## 8. Entry modes

| Mode | Description | Tracked in metrics |
|------|-------------|-------------------|
| `free_text` | User types naturally | Yes |
| `guided` | Wizard or guided chip completion | Yes |
| `voice` | Voice channel transcript | Yes |

Entry mode is sent on `POST /chat/text` and stored on intent events for funnel comparison.

---

## 9. Escalation & handover

Escalation triggers (agent prompt + product policy):

1. Customer requests a human / service advisor  
2. Customer expresses frustration or dissatisfaction  
3. Request outside tool capability (warranty disputes, legal, financing contracts)

Handover package includes: programme (800-AF), ticket ID, thread ID, intent, routed agent, A/B variant, reason, summary, sentiment, recommended SLA, customer profile, vehicle on file.

---

## 10. Out of scope & roadmap

| Phase | Item |
|-------|------|
| **Now (demo)** | Mock tools, SQLite metrics, static UI |
| **Phase 2** | DMS booking API, live recall feed |
| **Phase 3** | CRM webhook on escalation (Salesforce / Dynamics) |
| **Phase 4** | Arabic TTS, RTL UI polish |
| **Phase 5** | LangGraph supervisor visual graph, admin auth |

---

## 11. Acceptance criteria (demo)

- [ ] User can complete a guided service booking and receive `AF-` code  
- [ ] User can complete trade-in with mileage **band** (no exact odometer re-prompt)  
- [ ] User can escalate and see `AF-TICKET-` in reply  
- [ ] Ops dashboard shows conversions, bookings, escalations with handover JSON  
- [ ] Routing log shows specialist per turn  
- [ ] Voice channel works with STT; TTS or browser fallback  
- [ ] Booking conversion ≤ 100% (converted intents / starts)

---

## 12. References

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design  
- [TECHNICAL.md](TECHNICAL.md) — API and deployment  
- [METRICS.md](METRICS.md) — KPI definitions  
- [CAPABILITIES.md](../CAPABILITIES.md) — demo script
