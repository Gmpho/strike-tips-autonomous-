#Core Pipeline
- Multi-source scraper with graceful fallbacks (Betway API → scraper → PDF harvester)
- AdaptiveOddsMonitor daemon collecting & merging Betway (45s) + Oddschecker (5min) into a single snapshot
- Snapshot cache layer (in-memory + Redis pub/sub + disk) for live odds distribution
- RaceAnalyzer with edge detection, Kelly staking, and value bet identification

#AI Agent System
- Model pipeline with orchestrator.py routing through specialist agents
- Multiple providers: Groq (primary), Gemini, Ollama with fallback logic
- Intent classifier for routing user queries to the right tools
- MAF tool registry exposing racing tools to AI agents
- Dream engine for background reasoning & heartbeat generation

#Infrastructure
- Redis-backed task queue, snapshot caching, and pub/sub
- Centralized HTTP client management with connection pooling
- Docker Compose setup (API, odds monitor, agents)
- API with auth middleware, monitoring, racing, and betting routes
- Self-healing parsers that adapt to website changes
Frontend / HUD
- strike-tips-hud/ dashboard with analytics visualizations, ROI tracking, healing view, workflow display
Memory
- Dual memory: ChromaDB (race intelligence RAG) + Honcho (user/agent memory)
- Intelligence cache manager for historical odds baselines
- Learning engine that adjusts probabilities based on results
