# Strike Tips: Production Deployment & Security Plan (v2.0)

> **📅 Updated:** April 2026 | **Version:** 2.0
> **⚠️ Note:** Project refactored to `core_agent/` - path references updated below

## 1. Executive Summary
This plan outlines the transition of the Strike Tips system from a local prototype to a production-grade, secure, and highly-available serverless architecture.

## 2. Infrastructure Architecture (L8 Standard)
- **Frontend**: Hosted on Vercel or Netlify (Publicly accessible, CI/CD automated).
- **Backend (API)**: Docker containers via `docker compose` (see `docker-compose.yml`)
- **Authentication**: Clerk (Identity Management & JWT issuance).
- **Memory/Vector Store**: ChromaDB Cloud (Global, low-latency).
- **Secrets Management**: Environment variables in `.env` (Encrypted at rest).
- **Observability**: Grafana Cloud (LGTM Stack for monitoring, logs, and tracing).

## 3. Security Roadmap (SecOps)
- **Token Validation**: All incoming requests to FastAPI routes will be wrapped in a JWT-validation middleware using Clerk's SDK.
- **Envelope Encryption**: User API keys will be stored as encrypted blobs in the database.
- **DDoS Mitigation**: Docker resource limits provide basic protection.
- **API Access Control**: Implemented `X-API-KEY` header-based authentication for all API and MCP endpoints.

## 4. Deployment Strategy (DevOps)
- **CI/CD**: GitHub Actions pipeline triggered on `git push`.
    - `Linting & Type Checking`: Ensures code quality.
    - `Test Suite`: Runs `pytest core_agent/tests/` to guarantee no regressions.
    - `Deployment`: `docker compose up -d` (Atomic deployment).
- **High Availability**: Multi-container setup ensures zero-downtime during updates.

## 5. Updated Path References (v2.0)

| Old Path | New Path |
|----------|----------|
| `strike-tips/` | `core_agent/` |
| `strike-tips/api.py` | `core_agent/api.py` |
| `strike-tips/tests/` | `core_agent/tests/` |
| `strike-tips/config/` | `core_agent/config/` |
| `strike-tips/skills/` | `core_agent/skills/` |
| `strike-tips/data/` | `data/` (project root) |

---
