---
id: scaffold-app-type
name: "Scaffold an App Type (aine-aws-app-builder)"
description: "Generates the project structure, CDK stack, agent skeleton, and frontend scaffold for a specific AINE app type — ready to build on."
trigger: command
phrase: "/scaffold-app"
---

## Objective

Generate a complete project scaffold for the specified app type, including CDK infrastructure, agent code, frontend shell, and configuration — so the team can start building immediately without structural decisions.

## App Type Scaffolds

### claims-processing

```
{projectName}/
├── infrastructure/
│   ├── app.py
│   ├── cdk.json
│   ├── requirements.txt
│   └── stacks/
│       └── claims_stack.py        # DynamoDB (claims + policies), S3, Lambda, API GW, Textract, SNS
├── src/
│   ├── agent/
│   │   ├── agent.py               # Strands Agent: claims intake, validation, adjudication
│   │   └── tools/
│   │       ├── claims.py           # create_claim, get_claim, update_claim, list_claims
│   │       ├── policy.py           # lookup_policy, verify_coverage
│   │       ├── documents.py        # extract_document, validate_document
│   │       ├── validation.py       # validate_claim, check_fraud_indicators
│   │       └── notifications.py    # send_notification, send_reminder
│   ├── handlers/
│   │   └── api_handler.py          # Lambda handler: API GW → Agent
│   └── models/
│       └── claim.py                # Pydantic models: Claim, Policy, Document
├── frontend/
│   ├── package.json                # React + Vite + Tailwind
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx       # Claims overview, metrics
│   │   │   ├── Chat.tsx            # Agent conversation interface
│   │   │   ├── ClaimDetail.tsx     # Single claim view
│   │   │   └── ReviewQueue.tsx     # Human review queue
│   │   └── components/
│   │       ├── Layout.tsx
│   │       └── StatusBadge.tsx
│   └── vite.config.ts
├── tests/
│   └── unit/
├── scripts/
│   ├── deploy.sh
│   └── seed_data.py
├── requirements.txt
└── README.md
```

### enterprise-chatbot

```
{projectName}/
├── infrastructure/
│   └── stacks/
│       └── chatbot_stack.py        # Bedrock KB, Lambda, API GW, Cognito, S3 (docs)
├── src/
│   ├── agent/
│   │   ├── agent.py               # Strands Agent: conversational, RAG-backed
│   │   └── tools/
│   │       ├── knowledge.py        # search_knowledge_base, get_document
│   │       ├── actions.py          # create_ticket, schedule_meeting, send_email
│   │       └── integrations.py     # slack_post, jira_create, salesforce_query
│   ├── handlers/
│   │   └── api_handler.py
│   └── models/
│       └── conversation.py
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Chat.tsx            # Full-screen chat with streaming
│   │   │   ├── History.tsx         # Conversation history
│   │   │   └── Admin.tsx           # KB management, analytics
│   │   └── components/
│   │       ├── ChatMessage.tsx
│   │       ├── SourceCitation.tsx
│   │       └── FeedbackWidget.tsx
│   └── vite.config.ts
├── knowledge/
│   ├── ingest/                     # Document ingestion scripts
│   └── sources/                    # Source document staging
├── tests/
└── README.md
```

### document-pipeline

```
{projectName}/
├── infrastructure/
│   └── stacks/
│       └── pipeline_stack.py       # S3, Textract/BDA, Step Functions, DynamoDB, SQS, Lambda
├── src/
│   ├── agent/
│   │   ├── agent.py               # Strands Agent: document classification + extraction
│   │   └── tools/
│   │       ├── extraction.py       # extract_text, extract_tables, extract_forms
│   │       ├── classification.py   # classify_document, detect_document_type
│   │       ├── validation.py       # validate_extraction, cross_reference
│   │       └── storage.py          # store_result, query_results
│   ├── handlers/
│   │   ├── upload_handler.py       # S3 trigger → start processing
│   │   └── step_function_tasks.py  # Individual step function task handlers
│   ├── workflows/
│   │   └── processing.asl.json     # Step Functions state machine definition
│   └── models/
│       └── document.py
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Upload.tsx          # Drag-and-drop document upload
│   │   │   ├── Processing.tsx      # Real-time processing status
│   │   │   └── Results.tsx         # Extracted data review + correction
│   │   └── components/
│   │       ├── DocumentViewer.tsx
│   │       └── ExtractionTable.tsx
│   └── vite.config.ts
├── tests/
└── README.md
```

### rag-assistant

```
{projectName}/
├── infrastructure/
│   └── stacks/
│       └── assistant_stack.py      # Bedrock KB, OpenSearch Serverless, S3, Lambda, API GW
├── src/
│   ├── agent/
│   │   ├── agent.py               # Strands Agent: RAG-powered Q&A
│   │   └── tools/
│   │       ├── retrieval.py        # search_knowledge, get_context, rerank
│   │       ├── synthesis.py        # summarize, compare, explain
│   │       └── feedback.py         # log_feedback, report_issue
│   ├── handlers/
│   │   └── api_handler.py
│   ├── ingestion/
│   │   ├── ingest.py              # Document chunking + embedding pipeline
│   │   └── connectors/            # Source connectors (S3, Confluence, SharePoint)
│   └── models/
│       └── knowledge.py
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Ask.tsx             # Question interface with source citations
│   │   │   ├── Sources.tsx         # Knowledge base management
│   │   │   └── Analytics.tsx       # Usage metrics, unanswered questions
│   │   └── components/
│   │       ├── Citation.tsx
│   │       └── ConfidenceScore.tsx
│   └── vite.config.ts
├── tests/
└── README.md
```

### multi-agent

```
{projectName}/
├── infrastructure/
│   └── stacks/
│       └── orchestration_stack.py  # AgentCore, Step Functions, DynamoDB, S3, EventBridge
├── src/
│   ├── agents/
│   │   ├── orchestrator.py        # Supervisor agent: routes tasks to specialists
│   │   ├── specialist_a.py        # Domain specialist agent A
│   │   ├── specialist_b.py        # Domain specialist agent B
│   │   └── tools/
│   │       ├── routing.py          # delegate_task, collect_results, escalate
│   │       ├── shared.py           # Common tools across agents
│   │       └── domain_a.py         # Specialist A tools
│   ├── handlers/
│   │   └── api_handler.py
│   ├── coordination/
│   │   ├── state_machine.py       # Multi-agent state management
│   │   └── memory.py             # Shared memory across agents
│   └── models/
│       └── task.py
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Orchestrator.tsx    # Multi-agent task view
│   │   │   ├── AgentStatus.tsx     # Individual agent monitoring
│   │   │   └── TaskHistory.tsx     # Completed task audit trail
│   │   └── components/
│   │       ├── AgentCard.tsx
│   │       └── TaskFlow.tsx
│   └── vite.config.ts
├── tests/
└── README.md
```

### contact-center

```
{projectName}/
├── infrastructure/
│   └── stacks/
│       └── contact_stack.py        # Connect, Lex, Lambda, DynamoDB, Bedrock KB, SNS
├── src/
│   ├── agent/
│   │   ├── agent.py               # Strands Agent: customer service + escalation
│   │   └── tools/
│   │       ├── customer.py         # lookup_customer, get_history, update_record
│   │       ├── tickets.py          # create_ticket, update_ticket, escalate
│   │       ├── knowledge.py        # search_faq, get_procedure, find_article
│   │       └── channels.py         # transfer_to_agent, send_sms, send_email
│   ├── handlers/
│   │   ├── api_handler.py
│   │   └── connect_handler.py     # Amazon Connect contact flow integration
│   └── models/
│       └── interaction.py
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── AgentDesktop.tsx    # Unified agent desktop
│   │   │   ├── CustomerView.tsx    # Customer 360 view
│   │   │   └── Analytics.tsx       # CSAT, resolution time, deflection rate
│   │   └── components/
│   │       ├── ConversationPanel.tsx
│   │       └── SuggestedResponse.tsx
│   └── vite.config.ts
├── tests/
└── README.md
```

## Procedure

1. **Determine the app type** from the input. Validate it matches one of the supported types above.

2. **Determine the appLevel** from the input or `state/current.yaml`. Default to PoC if unset. The `app-level` steering file (auto-loaded under `.kiro/specs/**`) defines what each level adds. The same scaffold structure shown above is the **Production** scaffold — use the per-level table below to scope down for PoC and MVP.

   | What the scaffold includes | PoC | MVP | Production |
   |---|---|---|---|
   | `infrastructure/` (dev stack) | ✅ | ✅ | ✅ |
   | `infrastructure/stacks/staging_stack.py` | — | ✅ | ✅ |
   | `infrastructure/stacks/prod_stack.py` | — | — | ✅ |
   | `src/agent/` + `src/handlers/` | ✅ (basic) | ✅ (full) | ✅ (full) |
   | `frontend/` chat-only UI | ✅ | ✅ | ✅ |
   | `frontend/` HITL queue and escalation pages | ✅ | ✅ | ✅ |
   | `frontend/` admin dashboard | ✅ | ✅ | ✅ |
   | `tests/` unit + integration | — | ✅ | ✅ |
   | `tests/chaos/` and `tests/performance/` | — | — | ✅ |
   | `evaluation/` gold set | ✅ | ✅ | ✅ |
   | `.github/workflows/ci.yml` | — | ✅ | ✅ |
   | `.github/workflows/cd.yml` (with prod gate) | — | — | ✅ |
   | `docs/runbook.md` | — | ✅ | ✅ |
   | `docs/model-card-template.md` | — | ✅ | ✅ |
   | `docs/architecture-decisions/` | — | — | ✅ |

   When the workload graduates from PoC to MVP, re-run the scaffold and the missing pieces are added without touching what's already there.

3. **Generate the project structure** using the scaffold template for that app type, scoped to the chosen appLevel.

3. **Create the CDK stack** with:
   - All required AWS resources for the app type
   - Proper IAM roles with least privilege
   - Environment-aware configuration (dev/staging/prod via SSM)
   - Outputs for API endpoint, frontend URL, etc.

4. **Create the agent skeleton** with:
   - System prompt tailored to the domain
   - Tool stubs with docstrings and type hints
   - Guardrail configuration
   - Error handling patterns

5. **Create the frontend shell** with:
   - Vite + React + TypeScript + Tailwind
   - Amplify Authenticator wired to Cognito
   - API client with typed endpoints
   - Page shells with routing

6. **Create supporting files**:
   - `requirements.txt` with pinned versions
   - `README.md` with setup and deploy instructions
   - `scripts/seed_data.py` with sample data
   - `.env.example` with required environment variables

7. **Write the scaffold report** to `artifacts/aws-app-builder/scaffold-{timestamp}.md` documenting what was generated and next steps.

## Done when

- All directories and skeleton files exist
- CDK stack synthesizes without errors (`cdk synth`)
- Frontend builds without errors (`npm run build`)
- Agent imports and tool stubs are valid Python
- README accurately describes the project

