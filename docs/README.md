# Al Futtaim Automotive Concierge — Documentation

Portfolio documentation for the **800-AF** conversational AI demo.  
Use this index to navigate product, architecture, technical, and operational references.

> **Disclaimer:** This is a portfolio demonstration project. Branding references Al Futtaim Automotive for context; integrations (DMS, recall feeds, CRM) are mocked unless stated otherwise.

---

## Document map

| Document | Audience | Purpose |
|----------|----------|---------|
| [PRD.md](PRD.md) | Product, stakeholders | Goals, users, requirements, success metrics, scope |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Engineering, architects | System design, agent orchestration, data flow |
| [TECHNICAL.md](TECHNICAL.md) | Developers | API, stack, schema, deployment, configuration |
| [PROMPTS.md](PROMPTS.md) | AI / conversation designers | Prompt structure, routing, A/B variants, OPTIONS |
| [METRICS.md](METRICS.md) | Product, ops, analytics | KPI definitions, funnels, dashboard interpretation |
| [DEPLOYMENT.md](DEPLOYMENT.md) | DevOps | Railway deployment guide |
| [../CAPABILITIES.md](../CAPABILITIES.md) | Hiring managers, demo | Live demo script and capability matrix |

---

## Quick links

| Resource | URL (local) |
|----------|-------------|
| Chat UI | http://localhost:8080 |
| Ops dashboard | http://localhost:8080/admin |
| Health | `GET /health` |
| Metrics API | `GET /metrics` |
| Dashboard API | `GET /admin/dashboard` |

---

## Repository layout

```
agent/           # Multi-agent orchestration, tools, prompts, routing
metrics/         # SQLite persistence and aggregate metrics
static/          # Chat UI, admin dashboard, theme assets
main.py          # FastAPI application entry point
data/            # SQLite database (runtime, gitignored contents optional)
docs/            # This documentation set
```

---

## Recommended reading order

1. **PRD** — understand the problem and success criteria  
2. **ARCHITECTURE** — see how text/voice, routing, and tools connect  
3. **TECHNICAL** — run, configure, and extend the system  
4. **PROMPTS** — tune conversation behaviour  
5. **METRICS** — interpret dashboard and API numbers  
6. **CAPABILITIES** — prepare for a live demo
