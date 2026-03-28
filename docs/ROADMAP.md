# MongoRAG SaaS Roadmap

## Vision

Multi-tenant AI chatbot SaaS powered by RAG. Customers sign up, upload documents, get an embeddable script tag, and install a chatbot on their website that answers questions grounded in their own data.

## Architecture

- **Next.js** — SaaS frontend, dashboard, marketing site
- **FastAPI** — Python AI backend (RAG ingestion, retrieval, chat)
- **Pydantic AI** — RAG/agent orchestration (decided: lighter than LangChain, native Pydantic/FastAPI fit)
- **MongoDB Atlas + Vector Search** — document storage and retrieval
- **Stripe** — subscriptions and billing
- **Embeddable widget** — lightweight JS bundle for customer websites

## Reference Implementation

**[coleam00/MongoDB-RAG-Agent](https://github.com/coleam00/MongoDB-RAG-Agent)** — a working RAG agent that we adapt and extend rather than building from scratch.

### What we reuse:
| Component | Source File | Value |
|---|---|---|
| Hybrid RRF search | `src/tools.py` | Concurrent vector + text search with Reciprocal Rank Fusion |
| Document ingestion | `src/ingestion/` | Docling HybridChunker + batch embedder (PDF, Word, PPT, Excel, HTML, MD) |
| Pluggable providers | `src/providers.py` | OpenAI, OpenRouter, Ollama, Gemini support |
| Agent pattern | `src/agent.py` | Pydantic AI agent with tool calling |
| MongoDB schema | Collections | `documents` + `chunks` with vector + text indexes |

### What we build on top:
- Multi-tenant isolation (`tenant_id` on every query)
- FastAPI HTTP API (reference repo is CLI-only)
- Authentication (NextAuth.js + API keys)
- Dashboard, billing, widget
- Conversation history, streaming SSE
- Stable chunk IDs (SHA256-based) for idempotent upserts
- Document version tracking and content hashing
- Tiered LLM model strategy (cheap default, escalate on low confidence)
- Versioned system prompt templates
- RAG-specific metrics (latency breakdown, cost per request, retrieval quality)
- Query rewriting and multi-query expansion (post-MVP)
- Production deployment

## Atlas Tier Strategy

| Tier | Use | Storage | Cost | Notes |
|---|---|---|---|---|
| Free (M0) | Local dev, testing | 0.5GB, 100 ops/sec | $0 | Vector Search works but constrained |
| Flex | MVP, early users | 5GB, 500 ops/sec | $8–30/mo | No private endpoints |
| Dedicated M10+ | Production | Full features | ~$57/mo+ | Private endpoints, continuous backups, `$rankFusion` |

M2/M5 and Serverless were sunset — plan around Free, Flex, or Dedicated only.

## Phases & Issues

### Phase 1: Foundation & Architecture
| # | Issue | Priority |
|---|-------|----------|
| 1 | Define system architecture and technical decisions | 🔴 Critical |
| 2 | Initialize monorepo structure with Next.js and FastAPI | 🔴 Critical |
| 3 | Set up CI/CD pipeline with GitHub Actions | 🟡 Medium |

### Phase 2: Backend Core & RAG
| # | Issue | Priority |
|---|-------|----------|
| 4 | Set up MongoDB Atlas with Vector Search indexes | 🔴 Critical |
| 5 | Implement document ingestion pipeline (chunking + embedding + storage) | 🔴 Critical |
| 6 | Implement RAG retrieval and chat endpoint | 🔴 Critical |

### Phase 3: Multi-Tenancy & Auth
| # | Issue | Priority |
|---|-------|----------|
| 7 | Implement user authentication (signup, login, sessions) | 🔴 Critical |
| 8 | Implement API key generation, validation, and management | 🔴 Critical |
| 9 | Enforce tenant isolation across all API endpoints | 🔴 Critical |

### Phase 4: Subscription & Billing
| # | Issue | Priority |
|---|-------|----------|
| 10 | Integrate Stripe for subscription plans and checkout | 🟠 High |
| 11 | Implement usage metering and rate limiting | 🟠 High |

### Phase 5: Dashboard
| # | Issue | Priority |
|---|-------|----------|
| 12 | Build dashboard layout, navigation, and overview page | 🟠 High |
| 13 | Build document management UI (upload, list, update, delete) | 🟠 High |
| 14 | Build API key management UI | 🟠 High |
| 15 | Build billing and plan management UI | 🟡 Medium |

### Phase 6: Embeddable Widget
| # | Issue | Priority |
|---|-------|----------|
| 16 | Build embeddable chat widget | 🔴 Critical |
| 17 | Build bot configuration and management | 🟡 Medium |

### Phase 7: Document Management
| # | Issue | Priority |
|---|-------|----------|
| 18 | Implement document CRUD API (list, update metadata, delete with cascade) | 🟠 High |
| 19 | Add URL-based document ingestion (web scraping) | 🟡 Medium |

### Phase 8: Observability, Testing & Security
| # | Issue | Priority |
|---|-------|----------|
| 20 | Add structured logging, error tracking, and monitoring | 🟡 Medium |
| 21 | Add comprehensive test suite (unit, integration, e2e) | 🟡 Medium |
| 22 | Security hardening: input validation, CORS, CSP, secrets management | 🟠 High |
| 23 | Add RAG quality evaluation harness | 🟡 Medium |

### Phase 9: Deployment & Production
| # | Issue | Priority |
|---|-------|----------|
| 24 | Dockerize services and create production deployment pipeline | 🟠 High |
| 25 | Build marketing landing page and onboarding flow | 🟡 Medium |
| 26 | Add production database backup, migration, and disaster recovery plan | 🟡 Medium |

### Phase 10: Future Enhancements
| # | Issue | Priority |
|---|-------|----------|
| 27 | Add conversation analytics and query insights dashboard | 🟢 Low |
| 28 | Advanced RAG: reranking, query rewriting, citations, parameter tuning | 🟢 Low |
| 29 | Add team management and role-based access control | 🟢 Low |
| 30 | Add webhook notifications and integration API | 🟢 Low |

## Dependency Graph (Critical Path)

```
#1 Architecture
 └─► #2 Monorepo Setup
      ├─► #3 CI/CD
      ├─► #4 MongoDB Schema + Vector Search
      │    ├─► #5 Ingestion Pipeline
      │    │    └─► #6 Chat Endpoint ──► #16 Widget
      │    │         └─► #23 Eval Harness
      │    └─► #7 Auth
      │         ├─► #8 API Keys ──► #9 Tenant Isolation
      │         ├─► #10 Stripe ──► #11 Usage Metering
      │         └─► #12 Dashboard ──► #13, #14, #15
      └─► #24 Docker + Deploy
```

## MVP Definition

**MVP = Phases 1–6** (Issues #1–#17)

A customer can:
1. Sign up and log in
2. Upload documents
3. Get an embeddable script tag
4. Install the chatbot on their website
5. Get answers grounded in their own documents
6. Subscribe to a paid plan

## Suggested Sprint Plan (Solo Founder)

| Sprint | Duration | Issues | Goal |
|--------|----------|--------|------|
| 1 | 1-2 weeks | #1, #2, #3 | Foundation ready |
| 2 | 2-3 weeks | #4, #5, #6 | RAG pipeline working end-to-end |
| 3 | 1-2 weeks | #7, #8, #9 | Auth + tenant isolation |
| 4 | 1-2 weeks | #10, #11 | Billing integrated |
| 5 | 2-3 weeks | #12, #13, #14, #15 | Dashboard functional |
| 6 | 2-3 weeks | #16, #17, #18 | Widget + document management |
| 7 | 1-2 weeks | #20, #21, #22 | Hardening |
| 8 | 1-2 weeks | #24, #25, #26 | Production launch |
