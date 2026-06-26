# CloudDash Multi-Agent Customer Support

API-first prototype for a multi-agent customer support system built for the AI Engineering Intern assessment.

CloudDash is a fictional B2B SaaS platform for cloud infrastructure monitoring, alerting, and cost optimization. This project will route customer support conversations through specialized agents, retrieve knowledge base content with citations, support cross-agent handover, and escalate unresolved cases to a simulated human operator.

## Current Status

Phase 1 through Phase 3 are in progress:

- Project scope and architecture direction defined.
- API-first FastAPI skeleton created.
- Health endpoint available.
- Core folders created for agents, retrieval, handover, config, state, and tests.
- Typed Pydantic models added for conversations, messages, retrieval results, handovers, agent responses, and escalation tickets.
- In-memory conversation store added for the prototype.
- Conversation start, fetch, and message endpoints added.
- Sample CloudDash knowledge base added with 18 JSON articles across FAQ, troubleshooting, billing, API, and account access categories.
- Local RAG retrieval pipeline added with chunking, deterministic embeddings, JSON vector index, query rewriting, and citation results.
- Core deterministic agents added: Triage, Technical Support, Billing, and Escalation.
- Message API now routes through Triage, calls the selected specialist, and escalates duplicate-charge/refund-manager cases.

## Preferred Stack

- Python
- FastAPI
- Pydantic
- ChromaDB or FAISS for vector retrieval
- Config-driven agents using YAML
- pytest for tests
- Structured JSON logging

## Architecture Overview

```text
Customer
  |
  v
FastAPI
  |
  v
Conversation State
  |
  v
Triage Agent
  |
  +--> Technical Support Agent --> RAG Retriever --> Knowledge Base
  |
  +--> Billing Agent -----------> RAG Retriever --> Knowledge Base
  |
  +--> Escalation Agent --------> Human Handover Package
  |
  v
Response with citations, handover details, or escalation ticket
```

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Copy environment variables:

```bash
copy .env.example .env
```

Run the API:

```bash
powershell -ExecutionPolicy Bypass -File scripts/run_api.ps1
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "clouddash-support-api",
  "version": "0.1.0"
}
```

## API

- `GET /health` - Service health check.
- `POST /conversations` - Start a new support conversation.
- `POST /conversations/{conversation_id}/messages` - Send a customer message.
- `GET /conversations/{conversation_id}` - Retrieve conversation history and state.

The message endpoint currently stores the customer message and returns a placeholder Triage Agent response. Real routing and agent logic will be added in later phases.

## Repository Structure

```text
.
  README.md
  INTERNSHIP_PROJECT_BLUEPRINT.md
  .env.example
  requirements.txt
  main.py
  agents/
  api/
  config/
  handover/
  knowledge_base/
  retrieval/
  services/
  state/
  tests/
```

## Knowledge Base

The knowledge base lives in `knowledge_base/articles/` as JSON files. JSON is used because each article needs reliable metadata for retrieval, filtering, citations, and test validation.

Each article follows this structure:

```json
{
  "id": "KB-001",
  "title": "Supported Cloud Providers",
  "category": "faq",
  "tags": ["cloud providers", "aws", "gcp", "azure"],
  "content": "Article body...",
  "last_updated": "2026-04-15",
  "applies_to": ["Starter", "Pro", "Enterprise"]
}
```

The current KB contains 18 articles covering:

- FAQs
- Troubleshooting guides
- Billing and pricing policies
- API documentation
- Account and access management

It intentionally includes support for the assessment demo scenarios: AWS alert failures, SSO plus Pro-to-Enterprise upgrade handover, duplicate charge escalation, and unsupported Datadog integration handling.

## Retrieval Pipeline

Phase 5 uses a local retrieval pipeline so the project can run without paid APIs or native vector database setup:

1. Load JSON articles from `knowledge_base/articles/`.
2. Split article content into overlapping chunks.
3. Create deterministic hash-based embeddings for each chunk.
4. Persist the local vector index to `.data/vector_store/index.json`.
5. Rewrite user queries with conversation summary, intent, entities, and recent customer messages.
6. Search the vector index and return citation-ready `RetrievalResult` objects.

Build or rebuild the index:

```bash
python knowledge_base/ingest.py
```

The current embedding/vector-store layer is intentionally simple and swappable. For a stronger production version, replace `HashingEmbeddingProvider` and `JsonVectorStore` with OpenAI embeddings plus ChromaDB, FAISS, Qdrant, Pinecone, or another vector store.

## Agent Layer

The current Phase 6 agents are deterministic Python classes:

- `TriageAgent` classifies intent, extracts basic entities, and chooses the target agent.
- `TechnicalSupportAgent` retrieves KB citations and returns grounded troubleshooting guidance.
- `BillingAgent` retrieves billing policy citations and flags duplicate-charge, immediate-refund, and manager-request cases for escalation.
- `EscalationAgent` creates a simulated human-support ticket with priority, sentiment, recommended team, summary, and context snapshot.

This gives the project a working end-to-end support path before adding an LLM. Later, the deterministic response builders can be replaced with LLM calls while keeping the same `AgentResponse` contract.

## Design Decisions

- API-first because the assessment recommends a REST API and it is easy to demo live.
- Keep orchestration lightweight at first, then add LangGraph/LangChain only if it clearly helps.
- Store agent definitions in config so new agents can be added without rewriting the core orchestrator.
- Start with in-memory conversation state for the prototype, then document how it would move to a database in production.
- Store KB articles as structured JSON so Phase 5 can chunk, embed, retrieve, and cite content without fragile text parsing.
- Use deterministic local embeddings first so tests and demos are repeatable without external model calls.

## Known Limitations

- Agent responses are deterministic templates, not LLM-generated responses yet.
- Retrieval uses local hash embeddings, which are good for a prototype but less semantically accurate than production embedding models.
- Conversation state uses an in-memory store, so data resets when the server restarts.
- Formal handover audit logging and guardrails are planned for later phases.
