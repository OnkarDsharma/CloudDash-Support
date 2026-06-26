# CloudDash Multi-Agent Customer Support System

> AI Engineering Intern Assessment — Vikara.ai  
> Built by Onkareshwar Sharma, 3rd Year CSE, IIIT Naya Raipur

A production-architecture prototype of a multi-agent customer support system for **CloudDash**, a fictional B2B SaaS cloud infrastructure monitoring platform. The system routes customer conversations through specialized AI agents, grounds every response in a knowledge base with citations, handles cross-domain handovers, and escalates unresolvable cases to human operators — all through a REST API and a live Streamlit UI.

---

## Live Demo

```
API:        http://127.0.0.1:8000
Streamlit:  http://localhost:8501
API Docs:   http://127.0.0.1:8000/docs
```

---

## What Makes This Different

Most student projects build a single chatbot that calls an LLM and returns a response. This system is architected the way a real production support platform would be:

| Standard Chatbot | This System |
|-----------------|-------------|
| One model handles everything | Specialized agents per domain |
| No audit trail | Full handover history with timestamps |
| Hallucinated answers | Every claim grounded in KB citations |
| No safety layer | Input + output guardrails |
| Single-turn | Stateful multi-turn conversations |
| No observability | Structured JSON logs with trace IDs |
| Hardcoded logic | Config-driven, swappable components |

---

## Architecture

```
Customer Message
      │
      ▼
┌─────────────────┐
│  Input Guardrail │  ← blocks injection attacks, off-topic requests
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Triage Agent   │  ← score-based intent classification + entity extraction
└────────┬────────┘
         │
         ├──────────────────────────────────────┐
         │                                      │
         ▼                                      ▼
┌──────────────────┐              ┌─────────────────────┐
│ Technical Support│              │   Billing Agent      │
│     Agent        │              │                      │
│  KB Retrieval    │              │  KB Retrieval        │
│  Citations       │              │  Citations           │
└────────┬─────────┘              └──────────┬──────────┘
         │                                   │
         │   Multi-Intent Handover            │
         └──────────────┬────────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │ Escalation Agent  │  ← ticket + priority + sentiment + team
              └──────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │  Output Guardrail │  ← PII redaction + citation enforcement
              └──────────────────┘
                        │
                        ▼
                  Customer Response
                  + Handover Audit Log
```

Every agent transition is recorded as a `HandoverPayload` in `conversation.handover_history` — a complete audit trail with timestamp, source agent, target agent, reason, entities, recent messages, and KB citations transferred.

---

## Agent Design

### Triage Agent
**Job:** Read the message, score it against domain keyword lists, route to the right specialist.

**How it works:**
- Score-based classification (not first-match if/elif) — counts keyword hits per domain
- Technical score vs Billing score — highest wins; technical wins on tie (safer default)
- Hard overrides for escalation triggers: "immediate refund", "charged twice", "manager", "datadog"
- Extracts entities: plan, cloud provider, product area, urgency
- Conversation-aware fallback: follow-up messages with no keywords inherit the previous intent

**Why score-based instead of if/elif:**
First-match keyword routing fails on multi-domain messages. "I want to upgrade but check my SSO issue" would always hit billing because "upgrade" comes first. Scoring counts all signals and picks the strongest domain.

### Technical Support Agent
**Job:** Find the right KB article and return a grounded, cited answer.

**How it works:**
- Calls `KnowledgeBaseRetriever.retrieve()` with the message + conversation context
- Retriever rewrites the query using: conversation summary, current intent, entities, recent messages
- Returns top-K results from the semantic vector index
- Builds response from the top citation's snippet
- If no citations found: sets `needs_escalation=True`, never fabricates

### Billing Agent
**Job:** Handle billing policy questions. Escalate anything requiring human authority.

**How it works:**
- Same retrieval flow as Technical
- Hard escalation triggers: "immediate refund", "manager", "charged twice", "duplicate charge"
- Multi-intent awareness: checks handover payload for technical citations and appends them to the response
- No citations found → escalates immediately, never guesses at pricing

### Escalation Agent
**Job:** Package the conversation into a structured ticket for human support.

**How it works:**
- Classifies priority: "high" if urgency entity exists or trigger words detected
- Classifies sentiment: "frustrated" if angry/manager/immediate language detected
- Recommends team: billing vs technical vs general based on intent
- Builds full context snapshot: conversation ID, trace ID, customer ID, entities, retrieved sources, recent messages
- Creates `EscalationTicket` with unique `ESC-XXXXXXXX` ID

### Orchestrator
**Job:** Run the full pipeline without routes.py knowing anything about agents.

**How it works:**
1. Run Triage — get intent and target agent
2. Log handover if agent changed
3. Detect multi-intent (does this message need two agents?)
4. Run primary specialist
5. If `needs_escalation=True` → escalate
6. If multi-intent detected → run secondary specialist via handover
7. Return final `AgentResponse`

`routes.py` does exactly 5 things: validate, load, append message, call orchestrator, save. Nothing else.

---

## RAG Pipeline

### Why local semantic embeddings instead of OpenAI?

The assessment asks for a working prototype without external dependencies. The retrieval pipeline is designed with a **swappable embedder interface** — the same `embed()` function signature works whether you use:

- `HashingEmbeddingProvider` (zero dependencies, deterministic, good for tests)
- `all-MiniLM-L6-v2` via sentence-transformers (local, 80MB, semantically accurate)
- OpenAI `text-embedding-3-small` (API call, best quality)

Switch by changing one import in `retrieval/vector_store.py`. Nothing else changes.

### How retrieval works

```
1. Load 18 JSON KB articles from knowledge_base/articles/
2. Chunk each article with overlap (preserves context across chunk boundaries)
3. Embed: title + tags + chunk text → 384-dimensional vector
4. Persist to .data/vector_store/index.json
5. At query time:
   - Rewrite query using: summary + intent + entities + recent messages
   - Embed rewritten query
   - Cosine similarity search across all records
   - Return top-K results as RetrievalResult objects with source_id, title, snippet, score
6. Agent builds response from citations — never from model memory
```

### Query rewriting example

Customer message: "Which line item would cause a higher charge?"

Without rewriting this is semantically weak. With rewriting:
```
"billing_question product_area: Billing I don't understand why my invoice 
for March is higher than usual. Which line item would cause a higher charge?"
```

Now the retriever has full context and finds KB-016 (invoice explanation) instead of drifting.

---

## Handover Protocol

The handover system (`handover/protocol.py`) is the most architecturally significant part of this project.

### Multi-intent detection

```python
Message: "I want to upgrade from Pro to Enterprise but check my SSO issue first"

Technical score: 2 (sso + integration)
Billing score:   1 (upgrade)
→ Primary: Technical (SSO)
→ Secondary: Billing (upgrade)
→ execute_handover(technical → billing, entities, KB citations)
```

### What gets transferred in a HandoverPayload

```json
{
  "id": "uuid",
  "timestamp": "2026-06-26T...",
  "source_agent": "technical",
  "target_agent": "billing",
  "reason": "multi-intent: technical keywords [sso, integration] + billing keywords [upgrade]",
  "conversation_summary": "...",
  "entities": {"plan": "Enterprise", "product_area": "SSO"},
  "recent_messages": [...last 4 messages...],
  "retrieved_sources": [...KB citations from technical agent...],
  "context_snapshot": {
    "current_intent": "technical_issue",
    "status": "active",
    "message_count": 1,
    "timestamp": "..."
  }
}
```

The receiving agent gets everything. The customer never repeats themselves.

### Graceful fallback

If a target agent fails, `fallback_agent(conversation)` returns:
- `ESCALATION` if conversation is already escalated
- `TRIAGE` otherwise

---

## Guardrails

### Input Guardrail (`check_input`)

Runs before the orchestrator. If triggered, the orchestrator is **never called**.

**Prompt injection patterns blocked:**
- "ignore previous instructions"
- "reveal your system prompt"
- "bypass policy"
- "jailbreak mode"
- "act as if you have no restrictions"

**Off-topic patterns blocked:**
- Writing code/scripts unrelated to CloudDash
- Poems, jokes, stories
- Stock prices, weather, general knowledge

**Result:** `active_agent` stays `triage`, `handover_history` stays empty, no KB search performed.

### Output Guardrail (`check_output`)

Runs after the orchestrator, before the response reaches the customer.

**PII redaction:** emails, AWS access keys (`AKIA...`), API key patterns, long random strings, credit card numbers — replaced with `[REDACTED-TYPE]`.

**Citation enforcement:** If the response touches pricing, refunds, policies, or plans but has zero KB citations → appends transparency notice. The system never fabricates CloudDash facts.

---

## Guardrails & Safety — Assessment Requirement Coverage

| Requirement | Implementation |
|-------------|----------------|
| Input guardrail | Prompt injection + off-topic regex patterns |
| Output guardrail | PII redaction + citation enforcement |
| Never fabricate pricing/policies | Citation enforcement + agent fallback when no KB found |
| Graceful degradation | `needs_escalation=True` when no citations, fallback_agent on failure |

---

## Configuration & Extensibility

Agent routing rules live in `config/routing.yaml`. Agent definitions live in `config/agents.yaml`.

**Adding a new agent (e.g. Onboarding Agent) requires:**

1. Create `agents/onboarding.py` extending `BaseAgent`
2. Add one entry to `Orchestrator._agent_map`
3. Add routing keywords to `triage.py`

**Core orchestration loop: unchanged.**

This satisfies the assessment requirement: *"Adding a new agent type should not require modifying the core orchestration code."*

---

## Observability

Every agent invocation, KB retrieval, and handover event is logged with structured fields:

```python
logger.info("handover_executed", extra={
    "trace_id": conversation.trace_id,
    "handover_id": payload.id,
    "source_agent": source,
    "target_agent": target,
    "reason": reason,
    "entities_transferred": list(payload.entities.keys()),
    "sources_transferred": len(payload.retrieved_sources),
    "timestamp": payload.timestamp.isoformat(),
})
```

Every conversation has a unique `trace_id` (UUID) that connects all logs for that session.

---

## Setup

**1. Clone and create virtual environment**
```bash
git clone https://github.com/OnkarDsharma/CloudDash-Support.git
cd CloudDash-Support
python -m venv .venv
.venv\Scripts\activate
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
pip install streamlit sentence-transformers
```

**3. Configure environment**
```bash
copy .env.example .env
```

**4. Build knowledge base index**
```bash
python knowledge_base/ingest.py
```
This downloads `all-MiniLM-L6-v2` (~80MB, one time) and builds the semantic vector index.

**5. Start the API**
```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_api.ps1
```

**6. Start the Streamlit UI**
```bash
streamlit run demo_app.py
```

**7. Health check**
```bash
curl http://127.0.0.1:8000/health
```

---

## Running Tests

```bash
python -m pytest tests/ -v --basetemp="./tmp"
```

**83 tests across 9 test files — all pass.**

| Test File | Coverage |
|-----------|----------|
| `test_health.py` | Health endpoint |
| `test_conversations.py` | Conversation CRUD + message flow |
| `test_agents.py` | Individual agent unit tests |
| `test_knowledge_base.py` | KB article structure + demo scenario coverage |
| `test_retrieval.py` | Chunking, vector index, retrieval accuracy |
| `test_guardrails.py` | Injection blocking, off-topic, PII redaction, citation enforcement |
| `test_handover.py` | Multi-intent detection, payload construction, fallback |
| `test_orchestrator.py` | Routing, escalation, handover logging |
| `test_scenarios.py` | End-to-end demo scenarios 1–4 + edge cases |

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| POST | `/conversations` | Start a new support conversation |
| POST | `/conversations/{id}/messages` | Send a customer message |
| GET | `/conversations/{id}` | Get full conversation state + history |

Full interactive docs: `http://127.0.0.1:8000/docs`

---

## Demo Scenarios

See `DEMO.md` for exact commands and expected outputs for all 4 assessment scenarios plus bonus guardrail demo.

| Scenario | Message | Expected |
|----------|---------|----------|
| 1 — Technical | AWS alerts stopped firing | `technical`, KB-005 cited |
| 2 — Handover | SSO issue + upgrade | `technical→billing` handover |
| 3 — Escalation | Charged twice + manager | Ticket `ESC-`, high priority |
| 4 — KB failure | Datadog integration? | No fabrication, escalated |
| Bonus | Ignore previous instructions | Blocked, orchestrator never called |

---

## Known Limitations & Production Roadmap

| Limitation | Current | Production Fix |
|-----------|---------|----------------|
| Agent responses | Deterministic KB templates | LLM call (GPT-4/Claude) with KB context + conversation history |
| Conversation state | In-memory, resets on restart | Redis or PostgreSQL with session persistence |
| Embeddings | `all-MiniLM-L6-v2` local | OpenAI `text-embedding-3-small` or hosted model |
| Vector store | JSON file on disk | ChromaDB / Qdrant / Pinecone |
| Triage | Keyword scoring | LLM-based intent classifier with confidence scores |
| Multi-tenancy | Single instance | Tenant-scoped conversation stores + API key auth |
| Rate limiting | None | FastAPI middleware + Redis token bucket |
| Monitoring | Python logging | Langfuse / LangSmith for LLM traces + latency |

The entire system is designed for these upgrades to be **drop-in replacements** behind the same interfaces:
- `BaseAgent.run()` → swap template for LLM call
- `embed()` → swap embedder
- `InMemoryConversationStore` → swap store backend
- `JsonVectorStore` → swap vector DB

No orchestration code changes required for any of these.

---

## Repository Structure

```
CloudDash-Support/
├── agents/
│   ├── base.py              # BaseAgent ABC + format_citations
│   ├── triage.py            # Score-based intent classification
│   ├── technical.py         # KB retrieval + technical response
│   ├── billing.py           # Billing policy + escalation detection
│   ├── escalation.py        # Ticket creation + context packaging
│   └── orchestrator.py      # Full pipeline coordination
├── api/
│   ├── app.py               # FastAPI app factory
│   ├── routes.py            # Thin HTTP layer (5 responsibilities only)
│   └── schemas.py           # Request/response Pydantic models
├── handover/
│   └── protocol.py          # Multi-intent detection + handover execution + fallback
├── knowledge_base/
│   ├── articles/            # 18 JSON KB articles
│   └── ingest.py            # Load articles + build retrieval index
├── retrieval/
│   ├── chunking.py          # Article → overlapping chunks
│   ├── embeddings.py        # Hash-based embedder (tests/fallback)
│   ├── embeddings_semantic.py # sentence-transformers embedder (production)
│   ├── vector_store.py      # JSON vector store + cosine search
│   └── retriever.py         # Query rewriting + retrieval orchestration
├── services/
│   ├── guardrails.py        # Input + output safety checks
│   └── settings.py          # Pydantic settings from .env
├── state/
│   ├── models.py            # All Pydantic data models
│   └── store.py             # In-memory conversation store
├── config/
│   ├── agents.yaml          # Agent definitions
│   └── routing.yaml         # Routing rules
├── tests/                   # 83 tests, all passing
├── demo_app.py              # Streamlit UI
├── DEMO.md                  # Exact demo commands + expected outputs
└── README.md
```

---

## Design Decisions

**Why FastAPI over Flask/Django?**
Native async support, automatic OpenAPI docs, Pydantic integration for typed models, and production-ready performance. The assessment explicitly recommends REST API.

**Why deterministic agents first, not LLM calls?**
Deterministic agents make tests reliable and repeatable without API costs or rate limits. The `BaseAgent.run() → AgentResponse` contract means LLM calls can replace template logic without changing any orchestration code. This is the correct order to build: skeleton first, intelligence second.

**Why JSON vector store over ChromaDB/FAISS?**
Zero external dependencies for the prototype. The `JsonVectorStore` implements the same search interface that any vector DB would — swap the backend without touching retriever or agent code.

**Why score-based triage over LLM classification?**
Deterministic, fast, zero latency, no API cost, and 100% testable. Accurate enough for a prototype with 4 domains. The scoring approach also handles multi-intent detection naturally — if both scores are above zero, it's a multi-domain message.

**Why a separate Orchestrator class?**
Routes.py should only know HTTP. Agent logic should only know agents. The orchestrator is the seam between them. This means you can swap the entire routing strategy (keyword → LLM → rule engine) without touching the API layer.

---

*Built for the Vikara.ai AI Engineering Intern assessment, June 2026.*