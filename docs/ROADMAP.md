# MongoRAG SaaS Roadmap

## Vision

Multi-tenant AI chatbot SaaS powered by RAG. Customers sign up, upload documents, get an embeddable script tag, and install a chatbot on their website that answers questions grounded in their own data.

## Architecture

- **Next.js** — SaaS frontend, dashboard, marketing site
- **FastAPI** — Python AI backend (RAG ingestion, retrieval, chat)
- **LangChain** — RAG orchestration
- **MongoDB Atlas + Vector Search** — document storage and retrieval
- **Stripe** — subscriptions and billing
- **Embeddable widget** — lightweight JS bundle for customer websites

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
| 28 | Implement advanced RAG features: hybrid search, reranking, and citations | 🟢 Low |
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
