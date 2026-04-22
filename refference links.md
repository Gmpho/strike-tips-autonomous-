https://learn.microsoft.com/en-us/agent-framework/overview/?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/get-started/workflows?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/get-started/add-tools?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/get-started/your-first-agent?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/get-started/memory?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/workflows/executors?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/workflows/state?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/workflows/visualization?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/workflows/edges?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/
https://learn.microsoft.com/en-us/agent-framework/workflows/events?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/workflows/observability?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/agents/rag?pivots=programming-language-python
https://learn.microsoft.com/en-us/agent-framework/agents/skills?pivots=programming-language-python






Task Breakdown:                                                                                                                          
                                                                                                                                           
  Task 1: Extend `model_factory.py` to support all providers via Pydantic AI                                                               
                                                                                                                                           
  - Objective: Single get_model(tier) that returns a Pydantic AI model object for Ollama, Groq, or Gemini based on .env                    
  - Add GroqModel for GROQ_API_KEY tiers and GoogleModel for Gemini tiers                                                                  
  - Add get_model_with_fallback(tier) that returns an ordered list for the fallback chain                                                  
  - No changes to .env keys — just wire existing ModelConfig values into Pydantic AI providers                                             
  - Test: python -c "from config.model_factory import get_model; print(get_model('SCRAPER'))" prints model object without error            
  - Demo: All 3 provider types instantiate correctly from env vars                                                                         
                                                                                                                                           
  Task 2: Define structured output schemas in `agents/schemas.py`                                                                          
                                                                                                                                           
  - Objective: Typed Pydantic models for every agent response — replaces raw AgentResponse string                                          
  - Models: RaceAnalysis(runners: list[RunnerEdge], recommended: str, confidence: float), BetDecision(action: Literal["RECORD","REJECT"],  
  track: str, race_number: int, horse: str, stake: float, reason: str), AccountSummary(balance: float, pnl: float, open_bets: int),        
  AgentReply(summary: str, model_used: str, data: RaceAnalysis | BetDecision | AccountSummary | None)                                      
  - Test: Each schema validates with .model_validate({...})                                                                                
  - Demo: Import schemas, instantiate each, confirm field validation works                                                                 
                                                                                                                                           
  Task 3: Refactor `StrikeDeps` and wire into `brain.py`                                                                                   
                                                                                                                                           
  - Objective: StrikeDeps becomes a proper Pydantic AI deps container with strike, memory, and tools fields                                
  - Move StrikeDeps from brain.py stub into agents/schemas.py                                                                              
  - StrikeBrain.initialize() constructs and stores a StrikeDeps instance                                                                   
  - Test: brain.deps is accessible and brain.deps.strike is not None after init                                                            
  - Demo: brain.initialize(); assert brain.deps.strike is not None                                                                         
                                                                                                                                           
  Task 4: Create `agents/tools.py` — MAF tools as Pydantic AI `@agent.tool` functions                                                      
                                                                                                                                           
  - Objective: Wrap the 11 MAF tool registry functions as @agent.tool decorated functions that accept RunContext[StrikeDeps]               
  - Each tool extracts ctx.deps.strike and delegates to the existing TOOL_REGISTRY function — no logic duplication                         
  - Group into two sets: ANALYST_TOOLS (evaluaterace, searchpastraces, calculateprobabilityedge, searchracingdata) and `BANKROLLTOOLS`     
  (recordselection, updateraceresult, getaccountsummary, calculatemax_position)                                                            
  - Test: Call each tool function directly with a mock RunContext                                                                          
  - Demo: await analyst_tools.evaluate_race(ctx, track="turffontein", race_number=3) returns RaceAnalysis                                  
                                                                                                                                           
  Task 5: Build specialist agents in `agents/specialists/`                                                                                 
                                                                                                                                           
  - Objective: Replace AnalystSpecialist and BankrollSpecialist stubs with real Pydantic AI Agent instances                                
  - analyst_agent.py: Agent(model, deps_type=StrikeDeps, output_type=RaceAnalysis, tools=ANALYST_TOOLS, system_prompt=...)                 
  - bankroll_agent.py: Agent(model, deps_type=StrikeDeps, output_type=BetDecision, tools=BANKROLL_TOOLS, system_prompt=...)                
  - scanner_agent.py: Agent(model, deps_type=StrikeDeps, output_type=list[RaceAnalysis], tools=[run_daily_analysis, get_odds_snapshot],    
  system_prompt=...)                                                                                                                       
  - Each agent uses get_model_with_fallback(role_tier) — local first, cloud on failure                                                     
  - Test: await analyst_agent.run("analyse race 3 turffontein", deps=deps) returns typed RaceAnalysis                                      
  - Demo: Each specialist agent runs end-to-end and returns its typed output                                                               
                                                                                                                                           
  Task 6: Replace `IntentClassifier` + `ModelPipeline` with Pydantic AI router agent                                                       
                                                                                                                                           
  - Objective: Replace the regex IntentClassifier and hand-rolled ModelPipeline.chat() with a lightweight Pydantic AI router agent that    
  dispatches to the right specialist                                                                                                       
  - Router agent: Agent(model=get_model('FAST_LOCAL'), output_type=IntentResponse, system_prompt=...) — uses racing_llama locally, Groq    
  fallback                                                                                                                                 
  - ModelPipeline.chat() becomes: intent = await router.run(message) → dispatch to correct specialist agent → return AgentReply            
  - UnifiedOrchestrator.chat() signature unchanged — returns AgentResponse (backward compat wrapper around AgentReply)                     
  - Test: await pipeline.chat("analyse race 3 turffontein") routes to analyst, returns RaceAnalysis wrapped in AgentReply                  
  - Demo: Full chat round-trip works via the existing /api/agent/chat route                                                                
                                                                                                                                           
  Task 7: Wire agents into MCP server                                                                                                      
                                                                                                                                           
  - Objective: Expose the three specialist agents as MCP tools alongside the existing 11 MAF tools                                         
  - Add @mcp.tool wrappers for analyst_chat, bankroll_chat, scanner_chat that call the respective Pydantic AI agents                       
  - Each MCP tool accepts a query: str and returns the serialised structured output (.model_dump_json())                                   
  - Test: curl http://localhost:8000/mcp/messages lists the new agent tools                                                                
  - Demo: HUD AIChat component can call analyst_chat via MCP and receive a structured RaceAnalysis JSON response                           
                                                                                                                                           
  ────────




  Implementation Plan — Pydantic AI + Microsoft Agent Framework + MCP Integration                                                          
                                                                                                                                           
  Problem Statement:                                                                                                                       
                                                                                                                                           
  The hand-rolled ModelPipeline (regex intent classifier, raw httpx calls, string outputs) needs to be replaced with proper MAF Agent      
  instances using @tool decorated functions, structured Pydantic outputs, MAF Skills for domain expertise, MAF Workflows for the multi-step
  race analysis pipeline, and a clean cloud/local model factory — all wired through the existing MCP server.                               
                                                                                                                                           
  Requirements:                                                                                                                            
                                                                                                                                           
  - MAF Agent with @tool decorator replaces regex IntentClassifier + raw httpx pipeline                                                    
  - Structured Pydantic outputs (RaceAnalysis, BetDecision, AccountSummary) instead of raw strings                                         
  - MAF Skills (SKILL.md + scripts) package domain expertise for each specialist role                                                      
  - MAF Workflow (Executor graph) for the multi-step race scan: scrape → analyse → bankroll check → notify                                 
  - MAF ContextProvider wraps ChromaDB RAG — replaces manual grounding in ModelPipeline.chat()                                             
  - Model routing: local Ollama (fine-tuned models) → Groq → Gemini chain via model_factory.py                                             
  - Groq and Gemini accessed via OpenAI-compatible client (MAF OpenAIChatClient with custom base_url) — no Azure required                  
  - MCP server exposes agents internally (HUD + Telegram) — internal only for now                                                          
  - UnifiedOrchestrator.chat() signature unchanged — zero breaking changes to routes                                                       
                                                                                                                                           
  Architecture:                                                                                                                            
                                                                                                                                           
  graph TD                                                                                                                                 
      A[HUD / Telegram / REST] --> B[UnifiedOrchestrator.chat]                                                                             
      B --> C[MAF Agent - OllamaClient / OpenAIChatClient]                                                                                 
      C -->|@tool calls| D[agents/tools.py - 11 MAF tools]                                                                                 
      C -->|SkillsProvider| E[.kilo/skills/ SKILL.md files]                                                                                
      C -->|ChromaContextProvider| F[ChromaDB RAG]                                                                                         
      D --> G[TOOL_REGISTRY → StrikeTips / BankrollGovernor]                                                                               
                                                                                                                                           
      C --> H{model_factory fallback chain}                                                                                                
      H -->|local| I[Ollama: racing_qwen / func_gemma / lfm_racing / ds_racing]                                                            
      H -->|cloud T1| J[Groq: llama-3.3-70b via OpenAI-compat]                                                                             
      H -->|cloud T2-T4| K[Gemini flash chain via OpenAI-compat]                                                                           
                                                                                                                                           
      B --> L[MAF Workflow]                                                                                                                
      L --> M[ScrapeExecutor → AnalyseExecutor → BankrollExecutor → NotifyExecutor]                                                        
                                                                                                                                           
      C --> N[FastMCP Server]                                                                                                              
      N --> O[HUD React AIChat / Telegram Bot]                                                                                             
                                                                                                                                           
  Key design decisions:                                                                                                                    
                                                                                                                                           
  - MAF Agent is the single LLM interface — replaces all _call_ollama / _call_groq raw httpx                                               
  - MAF OllamaClient for local models; OpenAIChatClient with Groq/Gemini base_url for cloud                                                
  - MAF @tool(approval_mode="never_require") wraps the 11 existing TOOL_REGISTRY functions — no logic duplication                          
  - MAF Skills (SKILL.md) replace the text prompt files in /prompts/ — progressive disclosure keeps context lean                           
  - MAF Workflow with Executor graph replaces the ad-hoc scrape_and_analyze_track coroutine                                                
  - MAF ContextProvider wraps RacingMemory.search_form_insights() — replaces manual RAG grounding                                          
  - Groq has no native MAF provider — use OpenAIChatClient(base_url="https://api.groq.com/openai/v1") (OpenAI-compatible)                  
  - Gemini same pattern via OpenAIChatClient(base_url="https://generativelanguage.googleapis.com/v1beta/openai/")                          
                                                                                                                                           
  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
                                                                                                                                           
  Task Breakdown:                                                                                                                          
                                                                                                                                           
  Task 1: Extend `model_factory.py` — MAF client factory for all providers                                                                 
                                                                                                                                           
  - Objective: get_client(tier) returns a MAF client object (OllamaClient or OpenAIChatClient) based on .env tier config;                  
  get_client_chain(tiers) returns ordered list for fallback                                                                                
  - Ollama: from agent_framework.ollama import OllamaClient → OllamaClient(model=model_name, host=OLLAMA_HOST)                             
  - Groq/Gemini: from agent_framework.openai import OpenAIChatClient with base_url + api_key from env                                      
  - Keep existing get_model() as deprecated alias — no breaking changes                                                                    
  - Test: python -c "from config.model_factory import get_client; print(get_client('SCRAPER'))" prints client without error                
  - Demo: All 3 provider types instantiate from env vars; get_client_chain(['SCRAPER','ORCHESTRATOR','ORCHESTRATOR_T2']) returns 3-item    
  list                                                                                                                                     
  Task 2: Define structured output schemas in `agents/schemas.py`                                                                          
                                                                                                                                           
  - Objective: Typed Pydantic models for every agent response                                                                              
  - RunnerEdge(name: str, odds: float, edge: float, confidence: str), RaceAnalysis(track: str, race_number: int, runners: list[RunnerEdge],
  recommended: str, confidence: float), BetDecision(action: Literal["RECORD","REJECT"], track: str, race_number: int, horse: str, stake:   
  float, reason: str), AccountSummary(balance: float, pnl: float, open_bets: int), AgentReply(summary: str, model_used: str, data:         
  RaceAnalysis | BetDecision | AccountSummary | None = None)                                                                               
  - Test: Each schema validates with .model_validate({...})                                                                                
  - Demo: Import and instantiate each schema; confirm field validation and serialisation work                                              
                                                                                                                                           
  Task 3: Create MAF `@tool` wrappers in `agents/tools.py`                                                                                 
                                                                                                                                           
  - Objective: Wrap the 11 TOOL_REGISTRY functions as MAF @tool decorated functions — LLM can now call them autonomously                   
  - Each wrapper: @tool(approval_mode="never_require") + typed Annotated params + delegates to TOOL_REGISTRY[name](strike=strike, ...)     
  - Write-ops (record_selection, update_race_result) use approval_mode="always_require" for human-in-the-loop safety                       
  - Group: ANALYST_TOOLS, BANKROLL_TOOLS, SCANNER_TOOLS                                                                                    
  - Test: Call each tool function directly with mock args; confirm it returns expected dict                                                
  - Demo: get_account_summary() tool returns AccountSummary-compatible dict without error                                                  
                                                                                                                                           
  Task 4: Create MAF `Skills` for each specialist domain                                                                                   
                                                                                                                                           
  - Objective: Replace /prompts/*.txt files with proper MAF SKILL.md skill packages under .kilo/skills/                                    
  - race-analyst/SKILL.md — SA racing analysis instructions, edge calculation rules, track knowledge                                       
  - bankroll-governor/SKILL.md — Half-Kelly rules, discipline constraints, ZAR currency rules                                              
  - race-scanner/SKILL.md — daily scan procedure, track list, complexity classification                                                    
  - Each skill references the existing Modelfile system prompt content — no new content, just restructured                                 
  - Test: SkillsProvider(skill_paths=Path(".kilo/skills")) loads all 3 skills without error                                                
  - Demo: Agent with SkillsProvider lists available skills in its context; load_skill("race-analyst") returns full instructions            
                                                                                                                                           
  Task 5: Create `ChromaContextProvider` in `agents/chroma_context.py`                                                                     
                                                                                                                                           
  - Objective: MAF ContextProvider that calls RacingMemory.search_form_insights() before each agent run — replaces manual RAG grounding in 
  ModelPipeline.chat()                                                                                                                     
  - before_run(): searches ChromaDB with the user message, injects top-3 results via context.extend_instructions()                         
  - Only activates for analysis intents (check message for race/track keywords) to avoid context bloat                                     
  - Test: provider.before_run(...) with a mock message containing "turffontein" injects ChromaDB results                                   
  - Demo: Agent with ChromaContextProvider receives relevant past race data in context without manual grounding code                       
                                                                                                                                           
  Task 6: Build specialist MAF `Agent` instances in `agents/specialists/`                                                                  
                                                                                                                                           
  - Objective: Replace AnalystSpecialist and BankrollSpecialist stubs with real MAF Agent instances                                        
  - analyst_agent.py: client.as_agent(name="analyst", instructions=..., tools=ANALYST_TOOLS, context_providers=[skills_provider,           
  chroma_provider])                                                                                                                        
  - bankroll_agent.py: client.as_agent(name="bankroll", instructions=..., tools=BANKROLL_TOOLS, context_providers=[skills_provider])       
  - scanner_agent.py: client.as_agent(name="scanner", instructions=..., tools=SCANNER_TOOLS, context_providers=[skills_provider,           
  chroma_provider])                                                                                                                        
  - Each uses get_client('SCRAPER') (local Ollama) as primary; fallback handled in Task 7                                                  
  - Test: await analyst_agent.run("analyse race 3 turffontein", session=session) returns text response with tool calls                     
  - Demo: Each specialist agent runs end-to-end, calls the right tools, returns a response                                                 
                                                                                                                                           
  Task 7: Replace `ModelPipeline` with MAF agent dispatch + fallback chain                                                                 
                                                                                                                                           
  - Objective: ModelPipeline.chat() becomes: classify intent (keyword pre-filter → MAF router agent) → dispatch to specialist → fallback   
  chain on failure → return AgentReply                                                                                                     
  - Router: lightweight MAF agent on get_client('FAST_LOCAL') with output_type=IntentResponse — replaces IntentClassifier LLM fallback     
  - Fallback: try specialist on local Ollama → on httpx.TimeoutException or empty response, retry with get_client('ORCHESTRATOR') (Groq) → 
  then Gemini chain                                                                                                                        
  - UnifiedOrchestrator.chat() wraps result in AgentResponse dataclass — backward compat, zero route changes                               
  - Test: await pipeline.chat("analyse race 3 turffontein") routes to analyst, returns AgentReply with RaceAnalysis data                   
  - Demo: Full chat round-trip works via existing /api/agent/chat route; model_used field shows which model was used                       
                                                                                                                                           
  Task 8: Build MAF `Workflow` for the race scan pipeline                                                                                  
                                                                                                                                           
  - Objective: Replace ad-hoc scrape_and_analyze_track() coroutine with a proper MAF Workflow (Executor graph)                             
  - Executors: ScrapeExecutor (calls TAB4RacingScraper) → AnalyseExecutor (calls analyst agent per race) → BankrollExecutor (calls bankroll
  governor) → NotifyExecutor (calls Telegram)                                                                                              
  - WorkflowBuilder(start=ScrapeExecutor).add_edge(scrape, analyse).add_edge(analyse, bankroll).add_edge(bankroll, notify).build()         
  - StrikeTips.run_daily_scan() calls await workflow.run(tracks) instead of the current coroutine                                          
  - Test: Run workflow with mock scraper returning 2 races; confirm all 4 executors fire in order                                          
  - Demo: await workflow.run(["turffontein"]) produces RaceAnalysis outputs and triggers mock notification                                 
                                                                                                                                           
  Task 9: Wire agents into MCP server                                                                                                      
                                                                                                                                           
  - Objective: Expose the three specialist agents as MCP tools alongside the existing 11 MAF tools                                         
  - Add @mcp.tool wrappers: analyst_chat(query: str), bankroll_chat(query: str), scanner_chat(query: str) — each calls the respective MAF  
  agent and returns .model_dump_json()                                                                                                     
  - Test: curl http://localhost:8000/mcp/messages lists the 3 new agent tools                                                              
  - Demo: HUD AIChat component calls analyst_chat via MCP and receives structured RaceAnalysis JSON; Telegram bot routes to correct        
  specialist                                                                                                                               
                                                                                                                                           
  ─────────────────────
