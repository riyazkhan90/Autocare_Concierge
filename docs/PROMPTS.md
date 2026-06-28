# Prompt Engineering Guide

**System:** Al Futtaim Automotive Concierge (800-AF)  
**Source of truth:** `agent/prompts.py`, `agent/experiments.py`, `agent/router.py`

---

## 1. Prompt architecture

```
SHARED_GUIDELINES          ← all specialist agents
    │
    ├── SERVICE_PROMPT
    ├── SALES_PROMPT
    ├── RECALL_PROMPT
    ├── HANDOVER_PROMPT
    └── GENERAL_PROMPT

ROUTER_PROMPT              ← standalone classifier (no tools)
```

Specialist prompts are injected into LangGraph `create_react_agent` as the system message. Variant B appends an extra brevity block via `apply_variant_prompt()`.

---

## 2. Shared guidelines

All specialists inherit `SHARED_GUIDELINES`:

| Rule | Rationale |
|------|-----------|
| 1–3 sentences, &lt; 60 words | Voice-friendly; reduces TTS cost |
| One question at a time | Reduces abandonment in guided flows |
| Multi-brand wording | Al Futtaim serves Toyota, Lexus, Honda, Ford, Volvo, BYD, all makes |
| Gulf Standard Time | UAE market |
| `OPTIONS:` line format | Powers UI chips and guided wizards |
| Standard choice labels | Aligns UI catalog with agent offers |
| Match customer language (EN/AR) | Bilingual support |
| Never fabricate codes/values | Forces tool use |
| Mandatory escalation triggers | Product policy for handover |

### OPTIONS format

```
Your reply text here.

OPTIONS: Minor service | Interim service | Major service | Oil change
```

- 2–6 pipe-separated options  
- Omit `OPTIONS:` when not offering choices  
- UI strips `OPTIONS:` from displayed bubble text  

---

## 3. Specialist prompts

### Service Agent

**Handles:** Appointments, availability, workshop services.

**Gather before booking:** service type, date, time, customer name, vehicle make/model/year.

**Critical tool rule:**

```
vehicle_model as single string: "2020 Toyota Camry"
All five fields required in book_appointment JSON
```

**Flow:** Prefer `check_appointment_availability` when date unconfirmed.

---

### Sales Agent

**Handles:** Trade-in, valuations, test drives.

**Trade-in fields:** make, model, year, mileage, condition.

**Mileage policy:** Accept approximate bands (e.g. `40,000 – 80,000 km`). Pass range directly to `get_trade_in_quote` — **do not** ask for exact odometer.

**Test drive fields:** brand, model, preferred date, customer name.

---

### Recall Agent

**Handles:** Safety recall lookups only.

**Flow:** make + model + year → `lookup_vehicle_recall`.

**Disclaimer:** No data on file ≠ no recalls in the real world.

---

### Handover Agent

**Handles:** Human requests, frustration, complaints.

**Behaviour:** Acknowledge → summarise → `escalate_to_human`. Do not attempt complex resolution.

---

### General Agent

**Handles:** Greetings, hours, locations, FAQs.

**Behaviour:** Guide toward correct journey or escalate; does not book or run recalls directly.

---

## 4. Router prompt

**Model:** Same LLM, `max_tokens=16`, temperature 0.

**Output:** Exactly one token from: `service`, `sales`, `recall`, `handover`, `general`.

**Precedence in code (before LLM):**

1. Keyword routes (handover highest priority)  
2. Sticky follow-up for short messages  
3. LLM classifier  
4. Sticky last agent  
5. Default `general`  

### Keyword examples

| Agent | Keywords (sample) |
|-------|-------------------|
| handover | speak to, human, frustrated, complaint |
| recall | recall, safety recall, استدعاء |
| sales | trade-in, valuation, test drive, استبدال |
| service | book, appointment, oil change, صيانة, حجز |

---

## 5. A/B experiment (Variant B)

**Assignment:** `md5(thread_id)[0] % 2` → A or B.

**Variant B changes:**

1. Prompt addendum — max 2 sentences, &lt; 40 words, skip pleasantries  
2. LLM `max_tokens` — 256 vs 320 for variant A  

**Hypothesis:** Shorter replies improve voice UX and resolution speed without hurting conversion.

**Measure:** Ops dashboard → Experiments table (resolution rate, avg CX by variant).

---

## 6. Tool-use reliability

### Booking JSON failures

Groq may truncate tool-call JSON when `max_tokens` is low. Mitigations in `graph.py`:

1. `max_tokens` 320 (A) / 256 (B)  
2. Retry with system note appended to user message specifying required JSON fields  

### Vehicle context fallback

If `book_appointment` omits `vehicle_model`:

1. Thread context `vehicle` (parsed from message or demo profile)  
2. Else `"Vehicle not specified"`

---

## 7. Standard OPTIONS catalog

Aligned between prompts and UI (`static/index.html` `VEHICLE_CATALOG`):

| Category | Values |
|----------|--------|
| Services | Minor, Interim, Major, Oil change, Brake inspection, AC service |
| Makes | Toyota, Lexus, Honda, Ford, BMW, Volvo, BYD, Other |
| Mileage bands | Under 40,000 km; 40,000 – 80,000 km; 80,000 – 120,000 km; Over 120,000 km |
| Conditions | Excellent, Good, Fair, Poor |
| Times | 09:00, 11:30, 14:00, 16:00 |

Keep prompt labels and UI catalog in sync when adding options.

---

## 8. Escalation prompt contract

When calling `escalate_to_human`:

| Parameter | Content |
|-----------|---------|
| `reason` | Short trigger (e.g. "Customer requested human advisor") |
| `conversation_summary` | Full context for advisor: intent, vehicle, actions taken, open questions |

Backend builds `handover_json` with sentiment inference, ticket ID, and customer profile.

---

## 9. Tuning checklist

| Symptom | Adjustment |
|---------|------------|
| Replies too long | Strengthen brevity in SHARED_GUIDELINES; test variant B |
| Wrong agent routed | Add keywords to `router.py`; refine ROUTER_PROMPT |
| Asks for exact mileage | Reinforce SALES_PROMPT mileage band rule |
| Booking tool fails | Check max_tokens; verify vehicle_model in prompt |
| Too many escalations | Tighten escalation triggers; improve tool coverage |
| OPTIONS not showing | Ensure newline before `OPTIONS:`; 2–6 choices |

---

## 10. Related documents

- [ARCHITECTURE.md](ARCHITECTURE.md) — orchestration flow  
- [PRD.md](PRD.md) — product requirements  
- [METRICS.md](METRICS.md) — measure prompt changes
