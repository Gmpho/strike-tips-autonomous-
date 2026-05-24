1. Redis snapshot caching + HTTP client management — introduced shared connection-pooled HTTP clients and snapshot caching architecture across providers, scrapers, and the dreamer engine
2. Redis-backed task queue — refactored racing search tool to use a registry with dynamic limits
3. Centralized search logic — migrated racing data search to the tool registry
4. Persistent search caching + URL safety filtering for racing data queries
5. ROI tracking integration — added real-world search context to agent dreams, enhanced analytics HUD with trend visualizations
6. Heartbeat engine — background dream generation with persistence, improved chat UI with local storage, agent lifecycle tracking
7. GitHub Actions workflow display — added to HealingView sidebar
8. Healing event logging — for adaptive odds monitor synchronization
9. Live racing data integration — into DreamEngine, Groq model optimization, pre-warm agent pipeline
10. Racing SA calendar — direct calendar integration into MAF tool results for SA racing queries
Architecture
- core_agent/ — main agent package with orchestrator, pipeline, providers (Gemini, Groq, Ollama), tools, skills, parsers
- strike-tips-hud/ — frontend UI
