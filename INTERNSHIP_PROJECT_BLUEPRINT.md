# CloudDash Multi-Agent Customer Support System - Project Blueprint

## 1. Project Goal

Build a working prototype of a multi-agent customer support system for a fictional SaaS product called CloudDash, a cloud infrastructure monitoring platform.

The system should accept a customer message, classify the request, route it to the correct specialist agent, retrieve relevant knowledge base articles, answer with citations, hand over between agents when needed, and escalate to a human operator when the issue cannot be resolved.

## 2. Recommended Tech Stack

- Language: Python
- API: FastAPI
- Agent orchestration: lightweight custom orchestrator, LangGraph, or LangChain
- Data validation: Pydantic
- Vector database: ChromaDB or FAISS
- Embeddings: OpenAI embeddings, sentence-transformers, or another available embedding model
- LLM: OpenAI-compatible model, Gemini, Groq, Ollama, or any provider you can run reliably
- Logging: Python logging with JSON logs
- Tests: pytest
- Optional UI: Streamlit or Gradio

For an internship assessment, prefer a simple system that runs reliably over an over-engineered system.

## 3. Main Components

### 3.1 Interface Layer

Purpose: Lets users interact with the system.

Recommended API endpoints:

- `POST /conversations`
  - Starts a new conversation.
  - Returns `conversation_id` and `trace_id`.

- `POST /conversations/{conversation_id}/messages`
  - Accepts a customer message.
  - Runs triage, routing, retrieval, agent response, handover, or escalation.
  - Returns the assistant response, active agent, citations, and any handover details.

- `GET /conversations/{conversation_id}`
  - Returns full conversation history and current state.

Optional:

- Add a simple Streamlit or Gradio UI after the backend works.

### 3.2 Conversation State

Purpose: Stores everything the system knows during a support session.

Suggested fields:

- `conversation_id`
- `trace_id`
- `customer_id`
- `active_agent`
- `messages`
- `summary`
- `entities`
- `current_intent`
- `retrieved_sources`
- `handover_history`
- `escalation_status`

Use Pydantic models for state objects.

### 3.3 Triage Agent

Purpose: First point of contact.

Responsibilities:

- Classify the customer intent.
- Extract useful entities such as plan, cloud provider, integration, date, product area, urgency, and customer ID.
- Decide which specialist agent should handle the request.
- Detect multi-intent messages.

Example routes:

- Technical issue -> Technical Support Agent
- Billing, invoice, refund, upgrade -> Billing Agent
- Account access, SSO, RBAC -> Technical Support Agent or Account Agent if you add one
- Unknown, urgent, angry, unsupported -> Escalation Agent

### 3.4 Technical Support Agent

Purpose: Handles product and integration problems.

Responsibilities:

- Search the knowledge base.
- Provide step-by-step troubleshooting.
- Cite relevant KB articles.
- Generate small code/config examples if useful.
- Refuse to invent unsupported product details.

Example topics:

- Alerts not firing
- AWS CloudWatch integration failure
- API authentication
- Dashboard errors
- Webhooks
- SSO setup

### 3.5 Billing Agent

Purpose: Handles pricing, subscription, invoice, and payment questions.

Responsibilities:

- Search billing and pricing KB articles.
- Explain invoice line items.
- Simulate plan upgrade/downgrade.
- Cite policy documents.
- Escalate refund disputes or sensitive payment issues.

Do not let this agent fabricate pricing or refund policies. It should answer only from KB content.

### 3.6 Escalation Agent

Purpose: Creates a clean handover package for a simulated human support team.

Responsibilities:

- Summarize the conversation.
- Classify priority.
- Detect customer sentiment.
- Include customer ID, issue type, entities, attempted resolution, and relevant KB sources.
- Return a simulated support ticket ID.

Example output:

- `ticket_id`
- `priority`
- `sentiment`
- `summary`
- `recommended_team`
- `context_snapshot`

### 3.7 Orchestrator

Purpose: Coordinates agents and conversation flow.

Responsibilities:

- Load agent config from YAML/JSON.
- Call the Triage Agent.
- Select the next agent.
- Pass state between agents.
- Trigger handover if an agent detects a different domain.
- Trigger escalation if confidence is low or the KB has no answer.
- Log every important event.

The orchestrator should be generic enough that adding a new agent does not require rewriting core routing logic.

### 3.8 Knowledge Base

Purpose: Provides trustworthy CloudDash information for grounded answers.

Create 15-20 articles across:

- FAQs
- Troubleshooting guides
- Billing and pricing policies
- API documentation
- Account and access management

Recommended article format:

```json
{
  "id": "KB-001",
  "title": "How to Configure Alert Thresholds",
  "category": "troubleshooting",
  "tags": ["alerts", "configuration", "thresholds"],
  "content": "Step-by-step guide content here...",
  "last_updated": "2026-04-15",
  "applies_to": ["Pro", "Enterprise"]
}
```

### 3.9 RAG Pipeline

Purpose: Retrieves relevant KB content before an agent answers.

Workflow:

1. Load KB articles.
2. Split content into chunks.
3. Create embeddings.
4. Store chunks in a vector database.
5. Rewrite the user query using conversation context.
6. Retrieve top matching chunks.
7. Pass chunks to the selected agent.
8. Include citations in the final answer.

Bonus:

- Hybrid retrieval: vector search plus keyword/BM25.
- Re-ranking before final answer generation.

### 3.10 Handover Protocol

Purpose: Transfers a conversation between agents without losing context.

Handover payload should include:

- `timestamp`
- `source_agent`
- `target_agent`
- `reason`
- `conversation_summary`
- `entities`
- `recent_messages`
- `retrieved_sources`
- `context_snapshot`

Every handover should be logged.

If handover fails:

- Return to Triage Agent, or
- Escalate to human support.

### 3.11 Guardrails

Input guardrail examples:

- Detect prompt injection attempts.
- Reject off-topic queries.
- Flag abusive or unsafe content.

Output guardrail examples:

- Redact PII such as email, phone number, API key, or credit card-like strings.
- Check that billing/pricing/policy claims are supported by retrieved KB chunks.
- If no source supports the answer, say the KB does not contain enough information and offer escalation.

### 3.12 Observability

Log these events as structured JSON:

- Conversation started
- Agent invoked
- Intent classified
- KB retrieval performed
- Handover created
- Escalation created
- Error occurred

Each log should include:

- `trace_id`
- `conversation_id`
- `agent`
- `event`
- `timestamp`
- `latency_ms`
- `metadata`

## 4. Recommended Repository Structure

```text
cloud-dash-support/
  README.md
  ARCHITECTURE.md
  .env.example
  requirements.txt
  main.py
  agents/
    base.py
    triage.py
    technical.py
    billing.py
    escalation.py
  api/
    routes.py
    schemas.py
  config/
    agents.yaml
    routing.yaml
  handover/
    protocol.py
    logger.py
  knowledge_base/
    articles/
      kb_001_alert_thresholds.json
      kb_002_aws_integration.json
    ingest.py
  retrieval/
    chunking.py
    embeddings.py
    vector_store.py
    retriever.py
  services/
    llm.py
    guardrails.py
    logging.py
  state/
    models.py
    store.py
  tests/
    test_triage.py
    test_retrieval.py
    test_handover.py
    test_api.py
```

## 5. Build Workflow From Scratch

### Phase 1 - Understand and Scope

1. Read the assessment carefully.
2. Choose the simplest reliable stack.
3. Decide API-first or CLI-first. API is recommended.
4. Write a short architecture sketch before coding.

Deliverable:

- `README.md` with project goal and setup plan.

### Phase 2 - Create Project Skeleton

1. Create folders for agents, API, retrieval, handover, config, state, and tests.
2. Add `requirements.txt`.
3. Add `.env.example`.
4. Add basic FastAPI app or CLI entry point.

Deliverable:

- App starts successfully with a health endpoint.

### Phase 3 - Define Data Models

Create Pydantic models for:

- Message
- ConversationState
- AgentResponse
- RetrievalResult
- HandoverPayload
- EscalationTicket

Deliverable:

- Typed state that all agents share.

### Phase 4 - Create Knowledge Base

1. Write 15-20 CloudDash articles.
2. Cover the required categories.
3. Include article IDs and metadata.
4. Make sure test scenarios have matching articles.

Minimum articles to include:

- AWS integration credentials updated
- Alerts not firing
- Alert thresholds
- Dashboard loading slowly
- API authentication
- API rate limits
- Webhook setup
- SSO setup
- RBAC roles
- Invite team members
- Reset API key
- Supported cloud providers
- Pro vs Enterprise plan
- Upgrade and downgrade rules
- Refund policy
- Duplicate charge policy
- Invoice explanation
- Payment failures

Deliverable:

- KB articles in JSON or Markdown.

### Phase 5 - Build Retrieval

1. Implement KB loading.
2. Implement chunking.
3. Generate embeddings.
4. Store chunks in ChromaDB or FAISS.
5. Implement `retrieve(query, conversation_state)`.
6. Return citations with article ID, title, and chunk text.

Deliverable:

- A script that indexes the KB.
- A retriever that returns relevant articles for sample queries.

### Phase 6 - Build Agents

1. Implement a base agent interface.
2. Implement Triage Agent.
3. Implement Technical Support Agent.
4. Implement Billing Agent.
5. Implement Escalation Agent.
6. Load prompts and routing rules from config files.

Deliverable:

- Each agent can be called independently with a test message.

### Phase 7 - Build Orchestration

1. Start or load conversation state.
2. Run Triage Agent.
3. Route to the specialist agent.
4. Retrieve KB chunks.
5. Generate final response.
6. Save updated state.
7. Detect handover or escalation.

Deliverable:

- End-to-end response for a single technical support query.

### Phase 8 - Implement Handover

1. Create a HandoverPayload model.
2. Add handover decision logic.
3. Preserve entities, history, and summary.
4. Log handover event.
5. Add fallback behavior.

Deliverable:

- Cross-agent scenario works without asking the customer to repeat details.

### Phase 9 - Add Guardrails

1. Add prompt injection detection.
2. Add off-topic detection if time allows.
3. Add PII redaction for output.
4. Add hallucination check for policy/billing answers.

Deliverable:

- The system refuses unsupported claims and offers escalation.

### Phase 10 - Add Tests

Write focused tests for:

- Triage routing
- KB retrieval
- Citation presence
- Handover payload creation
- Escalation ticket creation
- API message endpoint

Deliverable:

- `pytest` passes.

### Phase 11 - Prepare Demo

Test these required scenarios:

1. Alerts stopped firing after AWS credential update.
2. Upgrade to Enterprise plus SSO issue handover.
3. Duplicate April charge and manager request.
4. Datadog integration retrieval failure.

Deliverable:

- Demo script in README.
- Live API URL.

### Phase 12 - Deployment

Simple deployment options:

- Render
- Railway
- Fly.io
- Hugging Face Spaces if using Gradio/Streamlit

Deliverable:

- Public live demo URL.

## 6. Suggested Development Order

Build in this order:

1. FastAPI skeleton
2. Data models
3. Mock LLM service
4. Triage routing
5. Knowledge base articles
6. Retrieval pipeline
7. Technical Agent
8. Billing Agent
9. Escalation Agent
10. Handover protocol
11. Guardrails
12. Tests
13. README and architecture diagram
14. Deployment

This order gives you a working prototype early, then improves quality.

## 7. Architecture Flow

```text
Customer
  |
  v
API or CLI
  |
  v
Conversation State Store
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

## 8. What to Explain in the Internship Discussion

Be ready to explain:

- Why you chose your orchestration pattern.
- How conversation state is preserved.
- How the Triage Agent classifies and routes requests.
- How RAG retrieval works.
- How citations prevent hallucination.
- How handover preserves context.
- What happens when retrieval fails.
- How guardrails protect the system.
- How you would add a new Onboarding Agent.
- What you would improve for production.

Production improvements to mention:

- Persistent database instead of in-memory state
- Tenant isolation
- Authentication and authorization
- Rate limiting
- Human support tool integration
- Queue-based background processing
- Better observability with Langfuse, LangSmith, or Phoenix
- Evaluation dataset for retrieval quality
- Cost and latency monitoring

## 9. Minimum Viable Submission Checklist

- Working API or CLI
- At least four agents: Triage, Technical, Billing, Escalation
- 15-20 KB articles
- RAG retrieval with citations
- Handover protocol
- Simulated human escalation
- Structured JSON logging with trace IDs
- One input guardrail
- One output guardrail
- README with setup and demo steps
- Architecture overview or diagram
- A few meaningful tests
- Public live demo URL

## 10. Best Strategy for a 5-Day Take-Home

Day 1:

- Setup project
- Define data models
- Build API skeleton
- Draft KB articles

Day 2:

- Build ingestion and retrieval
- Test citations
- Implement Triage Agent

Day 3:

- Implement Technical and Billing agents
- Add conversation state
- Add handover flow

Day 4:

- Implement Escalation Agent
- Add guardrails
- Add structured logging
- Write tests

Day 5:

- Polish README
- Deploy
- Run all demo scenarios
- Prepare explanation for live discussion

