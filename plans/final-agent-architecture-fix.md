# Strike Tips: Production Deployment & Security Plan

## 1. Executive Summary
This plan outlines the transition of the Strike Tips system from a local prototype to a production-grade, secure, and highly-available serverless architecture.

## 2. Infrastructure Architecture (L8 Standard)
- **Frontend**: Hosted on Vercel or Netlify (Publicly accessible, CI/CD automated).
- **Backend (API)**: Modal Serverless Containers (Scalable, Pay-per-second).
- **Authentication**: Clerk (Identity Management & JWT issuance).
- **Memory/Vector Store**: ChromaDB Cloud (Global, low-latency).
- **Secrets Management**: Modal Secrets (Encrypted at rest and injected at runtime).
- **Observability**: Grafana Cloud (LGTM Stack for monitoring, logs, and tracing).

## 3. Security Roadmap (SecOps)
- **Token Validation**: All incoming requests to FastAPI routes will be wrapped in a JWT-validation middleware using Clerk's SDK.
- **Envelope Encryption**: User API keys will be stored as encrypted blobs in the database, with the Master Encryption Key stored securely in Modal Secrets (never in code).
- **DDoS Mitigation**: Modal's infrastructure provides built-in rate-limiting and DDoS protection by design (only serving requests for your defined functions).
- **API Access Control**: Implemented `X-API-KEY` header-based authentication for all API and MCP endpoints, with secure rotation procedures documented in `docs/deployment_security.md`.

## 4. Deployment Strategy (DevOps)
- **CI/CD**: GitHub Actions pipeline triggered on `git push`.
    - `Linting & Type Checking`: Ensures code quality.
    - `Test Suite`: Runs `pytest strike-tips/tests/` to guarantee no regressions.
    - `Deployment`: `modal deploy strike-tips/api.py` (Atomic deployment).
- **High Availability**: Multi-region deployment on Modal to ensure zero-downtime during updates.

## 5. Observability (AIOps)
- **Cloud Monitoring**: Integration with Grafana Cloud (Loki for logs, Tempo for tracing, Prometheus for metrics).
- **Audit Logging**: WORM storage for all betting-related state changes, ensuring a non-repudiable history.
- **Performance Budget**: Daily automated scans and AI performance tracking via `performance_tracker.py` visualized in custom Grafana dashboards.

---

## Approval Required
- [ ] Approve the transition to Clerk for Authentication.
- [ ] Approve the use of Modal Secrets for all environment credentials.
- [ ] Approve the CI/CD automation plan (GitHub Actions).
- [ ] Approve the integration of Grafana Cloud for system-wide AIOps and dashboarding.

*By approving this plan, we lock in the security and observability architecture for your future platform growth.*
