# MAF Framework.md - Microsoft Agent Framework Integration

> **Latest Documentation from Context7 + Microsoft Learn** - Updated 2026-03-24

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Creating Your First Agent](#creating-your-first-agent)
4. [Custom Tools (Function Tools)](#custom-tools-function-tools)
5. [Multi-Turn Conversations](#multi-turn-conversations)
6. [Workflows & Orchestration](#workflows--orchestration)
7. [Custom Model Providers](#custom-model-providers)
8. [MCP Integration](#mcp-integration)
9. [Memory & State Management](#memory--state-management)
10. [OpenAI-Compatible Endpoints](#openai-compatible-endpoints)
11. [Architecture Mapping for Strike Tips](#architecture-mapping-for-strike-tips)

---

## Overview

The **Microsoft Agent Framework (MAF)** is a comprehensive multi-language framework for building, orchestrating, and deploying AI agents. It supports both .NET and Python, ranging from simple chat agents to complex multi-agent workflows.

### Key Features

- **Multi-language support**: Python and .NET
- **Built-in providers**: OpenAI, Azure OpenAI, Anthropic, Ollama
- **Custom provider support**: Extend with any LLM via `BaseChatClient`
- **MCP Integration**: Connect to Model Context Protocol servers
- **Memory & State**: In-memory session state, Azure Cosmos DB for persistence
- **Workflow orchestration**: Graph-based agent execution

---

## Installation

```bash
pip install agent-framework
```

For Azure Cosmos DB memory:
```bash
pip install agent-framework-azure-cosmos
```

---

## Creating Your First Agent

### Basic Agent with OpenAI

```python
import asyncio
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

async def main():
    agent = Agent(
        client=OpenAIChatClient(),
        instructions="""
        1) A robot may not injure a human being...
        2) A robot must obey orders given it by human beings...
        3) A robot must protect its own existence...

        Give me the TLDR in exactly 5 words.
        """
    )

    result = await agent.run("Summarize the Three Laws of Robotics")
    print(result)

asyncio.run(main())
# Output: Protect humans, obey, self-preserve, prioritized.
```

### Agent with Azure OpenAI

```python
from agent_framework.azure_openai import AzureOpenAIChatClient

client = AzureOpenAIChatClient(
    endpoint="https://your-resource.openai.azure.com/",
    api_key="your-api-key",
    api_version="2024-02-15-preview",
    deployment_name="gpt-4"
)

agent = Agent(client=client, instructions="You are a helpful assistant.")
```

### Agent with Ollama (Native Client)

MAF has native support for Ollama via `OllamaChatClient`:

```python
from agent_framework import Agent
from agent_framework.ollama import OllamaChatClient

# Configure via environment variables:
# OLLAMA_HOST=http://localhost:11434 (default)
# OLLAMA_MODEL_ID=ds_racing (your model name)

client = OllamaChatClient(model_id="ds_racing")

agent = Agent(
    client=client,
    instructions="You are an expert South African horse racing analyst."
)

response = await agent.run("Analyze Turffontein Race 3 for value bets")
print(response.text)
```

### Using Your Custom Racing Models

Strike Tips comes with 5 optimized Ollama Modelfiles for racing:

```python
from agent_framework.ollama import OllamaChatClient

# Option 1: Deep Reasoning (DeepSeek R1 based)
reasoner = OllamaChatClient(model_id="ds_racing")

# Option 2: Tool Calling (FunctionGemma based)
tool_caller = OllamaChatClient(model_id="func_gemma")

# Option 3: Fast Local (Qwen based)
fast_local = OllamaChatClient(model_id="racing_qwen")

# Option 4: Reliable JSON Output (Llama based)
json_output = OllamaChatClient(model_id="racing_llama")

# Option 5: LFM Reasoning (Long Form Model)
reasoning_alt = OllamaChatClient(model_id="lfm_racing")
```

### Recommended MAF + Ollama Setup for Strike Tips

```python
import os
from agent_framework import Agent, ConcurrentBuilder
from agent_framework.ollama import OllamaChatClient

# Create specialized agents for different tasks
reasoning_agent = Agent(
    client=OllamaChatClient(model_id="ds_racing"),
    instructions="You are a South African horse racing expert. Analyze form and give betting recommendations in ZAR."
)

tool_agent = Agent(
    client=OllamaChatClient(model_id="func_gemma"),
    instructions="You are a tool-calling machine. Call tools to get bankroll, scan races, and search form."
)

fast_agent = Agent(
    client=OllamaChatClient(model_id="racing_qwen"),
    instructions="Respond with valid JSON tool calls for racing operations."
)

# Build workflow (concurrent execution)
workflow = (
    ConcurrentBuilder()
    .participants([reasoning_agent, tool_agent])
    .build()
)
```

### Agent with Ollama (OpenAI-Compatible)

Alternatively, use the OpenAI client with Ollama's OpenAI-compatible endpoint:

```python
import os
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

# Configure via environment variables:
# export OPENAI_BASE_URL="http://localhost:11434/v1"
# export OPENAI_API_KEY="not-needed"
# export OPENAI_CHAT_MODEL_ID=ds_racing

client = OpenAIChatClient(
    base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
    api_key="not-needed"  # Ollama doesn't require API key
)

agent = Agent(
    client=client,
    model_id="ds_racing",
    instructions="You are an expert horse racing analyst."
)
```

---

## Custom Tools (Function Tools)

### Using @tool Decorator

The `@tool` decorator explicitly defines the name and description of a Python function tool, providing more control over how the agent interprets and utilizes the function.

```python
from typing import Annotated
from pydantic import Field
from agent_framework import tool

@tool(name="weather_tool", description="Retrieves weather information for any location")
def get_weather(
    location: Annotated[str, Field(description="The location to get the weather for.")],
) -> str:
    return f"The weather in {location} is cloudy with a high of 15°C."
```

### Define Multiple Function Tools

```python
from typing import Any
from agent_framework import tool
from pydantic import Field

@tool
def get_weather(
    location: Annotated[str, Field(description="The city.")],
) -> str:
    """Get the current weather for a location."""
    return f"The weather in {location} is sunny with a temperature of 22°C."

@tool
def get_forecast(
    location: Annotated[str, Field(description="The city.")],
    days: Annotated[int, Field(description="Number of days to forecast")] = 3,
) -> dict[str, Any]:
    """Get the weather forecast for a location."""
    return {
        "location": location,
        "days": days,
        "forecast": [
            {"day": 1, "weather": "Sunny", "high": 24, "low": 18},
            {"day": 2, "weather": "Partly cloudy", "high": 22, "low": 17},
            {"day": 3, "weather": "Rainy", "high": 19, "low": 15},
        ],
    }
```

### Add Tools to Agent

```python
from agent_framework import ChatAgent, tool

@tool
def get_weather(
    location: Annotated[str, Field(description="The location to get weather for")]
) -> str:
    """Get weather for a location."""
    return f"Weather in {location}: sunny"

# Direct use with agent (automatic conversion)
agent = ChatAgent(name="assistant", chat_client=client, tools=[get_weather])
```

---

## Multi-Turn Conversations

### Create Conversation Thread

Agents are stateless and do not maintain any state internally between calls. To have a multi-turn conversation, create a thread object to hold the conversation state.

```python
# Create a new thread for the conversation
thread = agent.get_new_thread()

# First interaction
result1 = await agent.run("Tell me a joke about a pirate.", thread=thread)
print(result1.text)

# Second interaction - agent remembers the context
result2 = await agent.run("Now add some emojis to the joke.", thread=thread)
print(result2.text)
```

### Multiple Independent Conversations

```python
async def main():
    thread1 = agent.get_new_thread()
    thread2 = agent.get_new_thread()

    result1 = await agent.run("Tell me a joke about a pirate.", thread=thread1)
    print(result1.text)

    result2 = await agent.run("Tell me a joke about a robot.", thread=thread2)
    print(result2.text)

    result3 = await agent.run("Now add some emojis to the joke.", thread=thread1)
    print(result3.text)

asyncio.run(main())
```

### Serialize/Deserialize Thread for Persistence

```python
from agent_framework import ChatAgent
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import AzureCliCredential

async def multi_turn_example():
    async with (
        AzureCliCredential() as credential,
        ChatAgent(
            chat_client=AzureAIAgentClient(async_credential=credential),
            instructions="You are a helpful assistant"
        ) as agent
    ):
        thread = agent.get_new_thread()

        # First interaction
        response1 = await agent.run("My name is Alice", thread=thread)
        print(f"Agent: {response1.text}")

        # Second interaction - agent remembers the name
        response2 = await agent.run("What's my name?", thread=thread)
        print(f"Agent: {response2.text}")  # Should mention "Alice"

        # Serialize thread for storage
        serialized = await thread.serialize()

        # Later, deserialize and continue conversation
        new_thread = await agent.deserialize_thread(serialized)
        response3 = await agent.run("What did we talk about?", thread=new_thread)
        print(f"Agent: {response3.text}")
```

---

## Workflows & Orchestration

### Sequential Workflow

Define a workflow with multiple agents executing in sequence.

```python
from agent_framework import WorkflowBuilder

builder = WorkflowBuilder()
builder.register_agent(factory_func=create_analyzer_agent, name="analyzer")
builder.register_agent(factory_func=create_better_agent, name="better")

# Add edges using registered factory function names
builder.add_edge("analyzer", "better")
builder.set_start_executor("analyzer")

workflow = builder.build()
```

### Concurrent Workflow (Fan-out/Fan-in)

Run multiple agents in parallel and aggregate their results.

```python
from agent_framework import ConcurrentBuilder, WorkflowOutputEvent

def summarize_results(results: list) -> str:
    """Custom aggregator function."""
    return " / ".join([r.data for r in results])

workflow = (
    ConcurrentBuilder()
    .participants([researcher, marketer, legal])
    .with_aggregator(summarize_results)
    .build()
)

output_evt: WorkflowOutputEvent | None = None
async for event in workflow.run_stream("We are launching a new budget-friendly electric bike."):
    if isinstance(event, WorkflowOutputEvent):
        output_evt = event

if output_evt:
    print("===== Final Consolidated Output =====")
    print(output_evt.data)
```

### Conditional Workflow with Branching

Route execution based on agent results.

```python
from semantic_kernel.agents import AgentExecutor
from semantic_kernel.workflow import WorkflowBuilder

# Build the workflow graph
# Start at spam detector, route based on result
workflow = (
    WorkflowBuilder()
    .set_start_executor(spam_detection_agent)
    # Not spam path
    .add_edge(spam_detection_agent, to_email_assistant_request, condition=get_condition(False))
    .add_edge(to_email_assistant_request, email_assistant_agent)
    .add_edge(email_assistant_agent, handle_email_response)
    # Spam path
    .add_edge(spam_detection_agent, handle_spam_classifier_response, condition=get_condition(True))
    .build()
)
```

---

## Custom Model Providers

### Using @ai_function Decorator

```python
from typing import Annotated
from agent_framework import Agent, ai_function
from agent_framework.openai import OpenAIChatClient

@ai_function(description="Get the current weather in a given location")
async def get_weather(location: Annotated[str, "The location as a city name"]) -> str:
    """Get the current weather in a given location."""
    return f"The current weather in {location} is sunny."

agent = Agent(
    name="MyAgent",
    model_client=OpenAIChatClient(),
    tools=get_weather,
    description="An agent that can get the weather.",
)
response = await agent.run("What is the weather in Amsterdam?")
print(response)
```

### Using Tools List with Pydantic

```python
import asyncio
from typing import Annotated
from random import randint
from pydantic import Field
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient


def get_weather(
    location: Annotated[str, Field(description="The location to get the weather for.")],
) -> str:
    """Get the weather for a given location."""
    conditions = ["sunny", "cloudy", "rainy", "stormy"]
    return f"The weather in {location} is {conditions[randint(0, 3)]} with a high of {randint(10, 30)}°C."


def get_menu_specials() -> str:
    """Get today's menu specials."""
    return """
    Special Soup: Clam Chowder
    Special Salad: Cobb Salad
    Special Drink: Chai Tea
    """


async def main():
    agent = Agent(
        client=OpenAIChatClient(),
        instructions="You are a helpful assistant that can provide weather and restaurant information.",
        tools=[get_weather, get_menu_specials]
    )

    response = await agent.run("What's the weather in Amsterdam and what are today's specials?")
    print(response)

asyncio.run(main())
```

---

## Custom Model Providers

### Creating a Custom Chat Client

Extend `BaseChatClient` to integrate any LLM provider:

```python
from agent_framework import BaseChatClient, ChatResponse, Message
from typing import Any

class GeminiChatClient(BaseChatClient):
    """Custom client for Google Gemini via OpenAI-compatible API."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def _inner_get_response(
        self, 
        *, 
        messages, 
        options, 
        **kwargs
    ) -> ChatResponse:
        # Call your Gemini API here
        # Using OpenAI-compatible interface or google-genai SDK
        return ChatResponse(messages=[Message(role="assistant", text="Response")])

    async def _inner_get_streaming_response(
        self, 
        *, 
        messages, 
        options, 
        **kwargs
    ):
        yield ChatResponseUpdate(...)
```

### Using with Environment Variable for Custom Endpoint

```bash
export OPENAI_BASE_URL="https://your-custom-endpoint.com/v1"
```

This allows integration with self-hosted models, proxies, or alternative API providers that maintain OpenAI API compatibility.

### Registering Custom Providers Declaratively

```python
from pathlib import Path
from agent_framework.declarative import AgentFactory

agent_factory = AgentFactory(
    additional_mappings={
        "GeminiProvider": {
            "package": "my_custom_module",
            "name": "GeminiChatClient",
            "model_id_field": "model_id",
        }
    }
)

agent = agent_factory.create_agent_from_yaml_path(Path("custom_provider.yaml"))
```

---

## MCP Integration

### What is MCP?

The **Model Context Protocol (MCP)** is an open standard for connecting AI agents to data sources and tools. It enables secure, controlled access to local and remote resources through a standardized protocol.

### Connecting MCP Tools to MAF Agent

The framework supports connecting to MCP servers to use their tools:

1. **Connect to MCP Server**: Establish connection to an MCP server
2. **List Available Tools**: Retrieve tools from the server
3. **Convert to AIFunctions**: Transform MCP tools into callable agent functions
4. **Invoke from Agent**: Use function calling capabilities

### Using MCP Tools with SSE

```python
from agent_framework import MCPToolset, SseServerParams

async def get_agent_async():
    toolset = MCPToolset(
        tool_filter=['read_file', 'list_directory'],
        connection_params=SseServerParams(
            url="http://remote-server:port/path", 
            headers={"Authorization": "Bearer token"}
        )
    )

    root_agent = LlmAgent(
        model='gemini-2.0-flash',
        name='agent_name',
        instruction='agent_instructions',
        tools=[toolset]
    )
    return root_agent, toolset
```

### Testing with MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

Use this CLI tool to connect to an MCP server, list available tools, and test their functionality.

---

## Memory & State Management

### In-Memory Session State (Default)

The framework provides lightweight session management:

```python
from agent_framework import AgentSession
import uuid
import json

# Create session
session = AgentSession(session_id=str(uuid.uuid4()))
session.state["bankroll"] = 1000.0
session.state["last_race"] = "Fairview"

# Serialize to JSON
data = session.to_dict()
json_str = json.dumps(data)

# Deserialize
data = json.loads(json_str)
session = AgentSession.from_dict(data)
```

### Using Context Providers

```python
from agent_framework import Agent, InMemoryHistoryProvider

agent = Agent(
    client=OpenAIChatClient(),
    instructions="You are helpful.",
    history_provider=InMemoryHistoryProvider()
)
```

### Azure Cosmos DB for Persistent Memory

```python
from agent_framework_azure_cosmos import CosmosHistoryProvider

provider = CosmosHistoryProvider(
    endpoint="https://<account>.documents.azure.com:443/",
    credential="<key-or-token-credential>",
    database_name="agent-framework",
    container_name="chat-history",
)

agent = Agent(
    client=OpenAIChatClient(),
    instructions="You are helpful.",
    history_provider=provider
)
```

### Custom Context Providers

```python
class BankrollContextProvider(ContextProvider):
    async def before_run(
        self,
        agent: "SupportsAgentRun",
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any]
    ) -> None:
        bankroll = state.get("bankroll", {})
        context.extend_instructions(
            self.source_id, 
            f"Current bankroll: R{bankroll.get('balance', 0)}"
        )
```

---

## OpenAI-Compatible Endpoints

The Microsoft Agent Framework can expose agents via OpenAI-compatible Chat Completions and Responses endpoints.

### Base URL Configuration

```text
http://localhost:8080/v1
```

The port can be customized using the `--port` CLI option.

### Expose Multiple Agents

```python
from openai import OpenAI

# Configure client options for the Foundry endpoint
client_options = {
    "base_url": "https://<myresource>.services.ai.azure.com/openai/v1/"
}

# Authenticate using Azure CLI credentials
credential = DefaultAzureCredential()

# Create the OpenAI client
client = OpenAI(
    api_key=credential.get_token("https://ai.azure.net/.default").token,
    **client_options
)

# Make requests
response = client.responses.create(
    metadata={"entity_id": "weather_agent"},  # Your agent name
    input="What's the weather in Seattle?"
)

# Extract text from response
print(response.output[0].content[0].text)
```

### Available Endpoints

Agents will be available at the following base paths:

- **Chat Completions**: `/agent_name/v1/chat/completions`
  - Example: `/math/v1/chat/completions`, `/science/v1/chat/completions`
- **Responses**: `/agent_name/v1/responses`
  - Example: `/math/v1/responses`, `/science/v1/responses`

---

## Architecture Mapping for Strike Tips

### Mapping Existing Components to MAF

| Existing Component | MAF Role | Implementation Method |
|-------------------|----------|------------------------|
| `scraper.py` | Tool | Wrapped in `@ai_function` or via MCP |
| `form_analyzer.py` | Logic Layer | Called by the Agent during reasoning |
| `scheduler.py` | Workflow Trigger | Replaced by MAF's Workflow orchestration |
| `strike_tips.py` | Service Layer | Remains as "muscles" for betting |
| `ai_providers.py` | Model Connector | Custom `BaseChatClient` for Gemini |
| `data/` | Resources | Exposed via MCP resources |
| `telegram_agent_loop.py` | User Interface | Replaced by MAF Agent with session state |

### Implementation Steps

1. **Toolification**: Register skills as `@ai_function` decorated async functions
2. **Resource Mapping**: Create MCP resources for data browsing
3. **Graph Definition**: Define "Betting Lifecycle" as a workflow with safety checks
4. **Memory**: Use `AgentSession` for stateful conversation + optional CosmosDB for persistence
5. **Custom Provider**: Implement `GeminiChatClient(BaseChatClient)` for Gemini integration

### Example: Gemini Custom Client for Strike Tips

```python
import os
from agent_framework import BaseChatClient, ChatResponse, Message
from google.genai import client as gemini_client
from google.genai import types

class GeminiChatClient(BaseChatClient):
    """Custom Gemini client using google-genai SDK."""
    
    def __init__(self, model: str = "gemini-2.0-flash"):
        self._client = gemini_client.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self._model = model
    
    async def _inner_get_response(
        self, 
        *, 
        messages, 
        options, 
        **kwargs
    ) -> ChatResponse:
        # Convert messages to Gemini format
        contents = self._convert_messages(messages)
        
        response = await self._client.agenerate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=options.get("temperature", 0.7),
                max_output_tokens=options.get("max_tokens", 2048),
            )
        )
        
        return ChatResponse(
            messages=[Message(role="assistant", text=response.text)]
        )
    
    def _convert_messages(self, messages):
        # Convert MAF messages to Gemini format
        # ... implementation
        pass
```

---

## Dependencies & Requirements

```txt
agent-framework>=0.1.0
google-genai>=0.1.0
pydantic>=2.0.0
aiohttp>=3.9.0
ollama>=0.1.0  # For local inference
```

---

## 10. Dependency Notes & Known Issues

### Current Status (2026-03-24)

⚠️ **Known Dependency Conflict**:
- `agent-framework-core 1.0.0rc5` requires: `packaging>=24.1,<25`
- `xai-sdk 1.8.1` requires: `packaging>=25.0,<26`

**Recommended Resolution**:
1. Wait for stable `agent-framework` release (non-RC) that resolves the packaging version
2. Or use a separate virtual environment for MAF development
3. Alternative: Remove `xai-sdk` if not needed (use agent-framework instead)

### Installation Commands (After Resolution)

```bash
# Clean install when dependencies are compatible
pip install agent-framework
pip install agent-framework-ollama  # For Ollama support

# Verify no conflicts
pip check
```

---

## 11. FastMCP Integration (2026-03-25)

**FastMCP** is a Python framework (by Prefect) for building Model Context Protocol servers. It provides a simpler alternative to building MCP servers manually.

### Installation

```bash
pip install fastmcp
```

### Creating a FastMCP Server

```python
from fastmcp import FastMCP

# Create server with a name
mcp = FastMCP(name="StrikeTipsServer")

# Register tools using the @mcp.tool decorator
@mcp.tool
def analyze_race(race_id: str, track: str) -> dict:
    """Analyze a race for value betting opportunities."""
    # Your existing race analysis logic
    return {"value_bets": [], "edge": 0.0}

@mcp.tool
def get_bankroll_status() -> dict:
    """Get current bankroll status."""
    return {"balance": 1000.0, "profit_loss": 0.0}

# Register resources using @mcp.resource decorator
@mcp.resource("racing://history/{date}")
def get_race_history(date: str) -> str:
    """Get race history for a specific date."""
    # Fetch from your data store
    return json.dumps(history_data)

# Run the server
if __name__ == "__main__":
    mcp.run()
```

### Tool Decorator Options

```python
# Basic tool - function name becomes tool name
@mcp.tool
def add(a: int, b: int) -> int:
    """Adds two numbers."""
    return a + b

# Custom tool name
@mcp.tool(name="custom_tool_name")
def my_tool(x: str) -> str:
    """Tool description."""
    return x

# With typed parameters using Pydantic
from pydantic import Field
from typing import Annotated

@mcp.tool
def calculate_edge(
    horse_name: Annotated[str, Field(description="Name of the horse")],
    odds_decimal: Annotated[float, Field(description="Decimal odds")],
    true_probability: Annotated[float, Field(description="Estimated true probability")]
) -> dict:
    """Calculate betting edge for a horse."""
    edge = (1 / odds_decimal) - true_probability
    return {"edge": edge, "recommendation": "BET" if edge > 0.05 else "SKIP"}
```

### Resource Templates

```python
import json
from fastmcp import FastMCP, Context

mcp = FastMCP("RacingDataServer")

# Dynamic resource with URI parameters
@mcp.resource("racing://track/{track_name}/races")
def get_track_races(track_name: str) -> str:
    """Get all races for a specific track."""
    races = fetch_races(track_name)
    return json.dumps(races)

# Resource with context access
@mcp.resource("racing://system-status")
async def get_system_status(ctx: Context) -> str:
    """Provides system status information."""
    return json.dumps({
        "status": "operational",
        "request_id": ctx.request_id
    })

# Resource with annotations for read-only hints
@mcp.resource(
    "racing://{date}/summary",
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
def get_daily_summary(date: str) -> str:
    """Get daily racing summary."""
    return json.dumps({"date": date, "total_races": 10})
```

### Connecting FastMCP to MAF

```python
from agent_framework import MCPToolset, SseServerParams
from agent_framework import LlmAgent

# Connect to FastMCP server via SSE
toolset = MCPToolset(
    tool_filter=['analyze_race', 'get_bankroll_status'],
    connection_params=SseServerParams(
        url="http://localhost:8000/mcp",  # FastMCP server URL
        headers={}
    )
)

# Create MAF agent with MCP tools
agent = LlmAgent(
    model='gemini-2.0-flash',
    name='racing_agent',
    instructions='You are a South African horse racing expert.',
    tools=[toolset]
)
```

### FastMCP Server Options

```python
from fastmcp import FastMCP

# HTTP server (SSE transport) - for production
mcp = FastMCP("MyServer", transport="http")

# stdio transport - for local development
mcp = FastMCP("MyServer", transport="stdio")

# Run with custom port
mcp.run(port=8080)
```

### Testing FastMCP Server

```bash
# Use MCP Inspector to test your server
npx @modelcontextprotocol/inspector
```

---

## 12. MCP Protocol Architecture (2026-03-25)

The **Model Context Protocol (MCP)** is an open standard for connecting AI agents to tools, resources, and data. It uses a client-server architecture with three main components.

### Core Concepts

| Component | Description |
|-----------|-------------|
| **Tools** | Functions the LLM can call to perform actions |
| **Resources** | Data the LLM can read (files, APIs, databases) |
| **Prompts** | Reusable prompt templates |

### MCP Server Capabilities

```python
# List available tools
list_tools() -> list[Tool]

# Call a tool
call_tool(name: str, arguments: dict) -> list[Content]

# List available resources
list_resources() -> list[Resource]

# Read a resource
read_resource(uri: AnyUrl) -> ResourceResult

# List prompts
list_prompts() -> list[Prompt]

# Get a rendered prompt
get_prompt(name: str, arguments: dict) -> GetPromptResult
```

### Transport Options

1. **stdio**: Local process communication (development)
2. **SSE (Server-Sent Events)**: HTTP-based (production)

### FastMCP Simplified Approach

FastMCP wraps the low-level MCP SDK with decorators:

```python
from fastmcp import FastMCP

mcp = FastMCP("Demo")

@mcp.tool          # Registers as callable tool
def my_tool(x: str) -> str:
    return f"Result: {x}"

@mcp.resource("data://info")  # Registers as readable resource
def get_info() -> str:
    return json.dumps({"version": "1.0"})

@mcp.prompt        # Registers as prompt template
def summarize(text: str) -> str:
    return f"Summarize: {text}"

mcp.run()  # Starts stdio or HTTP server
```

### Middleware Hooks

FastMCP supports operation hooks for logging, validation, and modification:

```python
# Tool execution hook
async def on_call_tool(context: MiddlewareContext, call_next):
    tool_name = context.message.name
    args = context.message.arguments
    result = await call_next(context)
    # Log, validate, or modify result
    return result

# Resource read hook
async def on_read_resource(context: MiddlewareContext, call_next):
    uri = context.message.uri
    result = await call_next(context)
    return result
```

---

## References

### Official Documentation
- [Microsoft Agent Framework GitHub](https://github.com/microsoft/agent-framework)
- [Python Samples](https://github.com/microsoft/agent-framework/tree/main/python/samples)
- [MCP Protocol Documentation](https://modelcontextprotocol.io)
- [Azure Cosmos DB Provider](https://github.com/microsoft/agent-framework/tree/main/python/packages/azure-cosmos)

### Microsoft Learn
- [Get Started: Your First Agent](https://learn.microsoft.com/en-us/agent-framework/get-started/your-first-agent?pivots=programming-language-python)
- [Get Started: Add Tools](https://learn.microsoft.com/en-us/agent-framework/get-started/add-tools?pivots=programming-language-python)
- [Get Started: Multi-Turn Conversations](https://learn.microsoft.com/en-us/agent-framework/get-started/multi-turn?pivots=programming-language-python)
- [Get Started: Memory](https://learn.microsoft.com/en-us/agent-framework/get-started/memory?pivots=programming-language-python)
- [Get Started: Workflows](https://learn.microsoft.com/en-us/agent-framework/get-started/workflows?pivots=programming-language-python)
- [Integrations: OpenAI Endpoints](https://learn.microsoft.com/en-us/agent-framework/integrations/openai-endpoints?tabs=dotnet-cli%2Cuser-secrets&pivots=programming-language-python)

---

## Pydantic AI Integration (Alternative/Sibling)

Strike Tips already uses Pydantic AI in `ai_pydantic.py`. Here's how to use it with MAF:

### Basic Pydantic AI Agent with Dependency Injection

```python
from pydantic_ai import Agent, RunContext
from dataclasses import dataclass

@dataclass
class StrikeDeps:
    """Dependencies for racing agent."""
    strike: 'StrikeTips'
    memory: 'RacingMemory'

# Create agent with dependency injection
agent = Agent(
    'gemini-2.0-flash',
    deps_type=StrikeDeps,
)

@agent.system_prompt
def get_instructions(ctx: RunContext[StrikeDeps]) -> str:
    bankroll = ctx.deps.strike.get_bankroll_status()
    return f"""You are a South African horse racing expert.
Current bankroll: R{bankroll.get('current_bankroll', 0)}"""

@agent.tool
async def scan_races(ctx: RunContext[StrikeDeps], track: str) -> str:
    """Scan races at a specific track for value bets."""
    results = await ctx.deps.strike.scrape_and_analyze_track(track)
    return f"Found {len(results)} races with value bets."

@agent.tool
def get_bankroll(ctx: RunContext[StrikeDeps]) -> str:
    """Get current bankroll status."""
    status = ctx.deps.strike.get_bankroll_status()
    return f"Bankroll: R{status.get('current_bankroll', 0)}"
```

### Tool with RunContext

```python
@agent.tool
async def query_memory(ctx: RunContext[StrikeDeps], query: str) -> str:
    """Query historical racing data from memory."""
    results = ctx.deps.memory.search_similar_conditions(query)
    return str(results)
```

### FunctionToolset for Multiple Tools

```python
from pydantic_ai import FunctionToolset

# Create toolset from skills
toolset = FunctionToolset(tools=[
    scan_races,
    get_bankroll,
    query_memory,
])

agent = Agent('gemini-2.0-flash', toolsets=[toolset])
```

### MAF + Pydantic AI Hybrid Approach

You can use both frameworks together:

```python
from agent_framework import Agent as MAFAgent
from pydantic_ai import Agent as PydanticAgent

# Pydantic AI for intent classification & routing
pydantic_agent = PydanticAgent(
    'gemini-2.0-flash',
    deps_type=StrikeDeps,
    tools=[scan_races, get_bankroll]
)

# MAF for workflow orchestration & multi-agent
maf_agent = MAFAgent(
    client=OllamaChatClient(model_id="ds_racing"),
    instructions="Execute betting workflow with safety checks."
)

# Hybrid: Use Pydantic for classification, MAF for execution
async def hybrid_process(message: str):
    # Classify intent with Pydantic AI
    intent_result = await pydantic_agent.run(message)
    
    # Execute with MAF workflow
    maf_result = await maf_agent.run(f"Execute: {intent_result.output}")
    return maf_result
```

---

## Current Strike Tips Pydantic AI Implementation

Your existing implementation in `strike-tips/ai_pydantic.py` follows these patterns:

### 1. Agent with Dependencies (Current Implementation)

```python
# From ai_pydantic.py - StrikeDeps
@dataclass
class StrikeDeps:
    strike: StrikeTips

# Agent initialization with deps_type
class L7Orchestrator:
    def __init__(self, strike_instance: StrikeTips):
        self.classifier = get_model("CLASSIFIER")
        
        self.agent = Agent(
            self.classifier,
            deps_type=StrikeDeps,
            retries=2, 
            system_prompt="""You are an intent classifier for a racing bot.
            Classify user messages into EXACTLY one of these labels:
            GET_BANKROLL, SCAN_RACES, GET_RESULTS, SEARCH_FORM, GET_INTELLIGENCE, OTHER.
            Output ONLY the label."""
        )
```

### 2. Tool Registration (Current Implementation)

```python
# The tools are defined in AgentTools (skills/agent_tools.py)
# and accessed via brain.tools.execute_tool()

async def chat(self, user_msg: str, model_override: str = None) -> AgentResponse:
    # Intent classification
    result_val = await self.agent.run(user_msg, deps=StrikeDeps(strike=self.strike))
    intent = str(getattr(result_val, 'output', result_val)).strip().upper()
    
    # Routing based on intent
    if "GET_BANKROLL" in intent:
        data = self.strike.get_bankroll_status()
        ...
```

### 3. Response Model (Current Implementation)

```python
# From ai_pydantic.py - AgentResponse
class AgentResponse(BaseModel):
    summary: str = Field(description="Concise summary of the analysis.")
    confidence: float = Field(default=0.0, description="Confidence 0-1")
    suggested_action: str = Field(default="SKIP", description="BET, SKIP, SCAN, or INFO")
    grounding_sources: List[str] = Field(default_factory=list)
```

### 4. Recommended Migration to MAF

To migrate from pure Pydantic AI to MAF while keeping the same patterns:

```python
from agent_framework import Agent as MAFAgent
from agent_framework.ollama import OllamaChatClient
from pydantic_ai import Agent as PydanticAgent
from dataclasses import dataclass

# Keep current Pydantic AI for intent classification
pydantic_agent = PydanticAgent(
    'gemini-2.0-flash',
    deps_type=StrikeDeps,
    system_prompt="""Classify into: GET_BANKROLL, SCAN_RACES, ..."""
)

# Use MAF for tool execution with Ollama
maf_agent = MAFAgent(
    client=OllamaChatClient(model_id="ds_racing"),
    tools=[run_daily_scan, get_bankroll_status, query_memory],
    instructions="Execute betting operations with safety checks."
)

# Hybrid workflow
async def process_request(message: str, deps: StrikeDeps):
    # Step 1: Classify intent (Pydantic AI)
    intent = await pydantic_agent.run(message, deps=deps)
    
    # Step 2: Execute action (MAF)
    if "SCAN" in intent.output:
        result = await maf_agent.run(f"Scan all tracks and find value bets")
    elif "BANKROLL" in intent.output:
        result = await maf_agent.run("Get current bankroll status")
    
    return result
```

---

## Appendix: Original Strike Tips MAF Integration Strategy

### MAF Integration Strategy: Mapping the "Truth"

This document maps your existing codebase (the "Truth") to the new Microsoft Agent Framework (MAF) + FastMCP ecosystem for full-spectrum autonomy.

#### The Architectural Mapping

| Existing Component | MAF Role | Implementation Method |
|-------------------|----------|------------------------|
| scraper.py | Tool | Wrapped in `@mcp.tool()` via mcp_server.py |
| form_analyzer.py | Logic Layer | Called by the Gemini Brain during reasoning |
| scheduler.py | Workflow Trigger | Replaced by MAF's Workflow or Graph orchestration |
| strike_tips.py | Service Layer | Remains the "Muscles" for placing bets and managing bankroll |
| ai_providers.py | Model Connector | Integrated as a custom ChatCompletion provider in MAF |
| data/ | Resources | Exposed via `@mcp.resource()` (e.g., racing://history) |
| telegram_agent_loop.py | User Interface | Replaced by the MAF ChatLoop which is multi-turn and stateful |

#### Step-by-Step Utilization

1. **The Skills (The "What")**

Your skills/ directory contains the functional code. We don't change this. We simply register them in your mcp_server.py using FastMCP.

```
skills/race_analysis -> mcp.tool("analyze_race")
skills/notifications -> mcp.tool("send_telegram")
```

2. **The Persistence (The "Memory")**

MAF has a native Memory system. Instead of the agent "guessing" if it already analyzed a race, MAF stores the session state. It will use your skills/memory (ChromaDB) as a "Long-term Knowledge Resource."

3. **The Orchestrator (The "Why")**

We create maf_orchestrator.py. This file will:

- Initialize a MAF Agent
- Connect to the StrikeTips MCP Server
- Use Gemini SDK for the Model tier
- Execute the loop currently found in telegram_agent_loop.py but with Graph-based safety checks (e.g., "Always check bankroll before placing a bet")

#### Execution Plan

- **Toolification**: Ensure all files in skills/ have clear entry points for FastMCP
- **Resource Mapping**: Map the contents of data/ to MCP Resources so the LLM can "browse" its own history
- **Graph Definition**: Define the "Betting Lifecycle" as a MAF Workflow to ensure the Governor rules are never bypassed

---

### Microsoft Agent Framework Research (Original Notes)

1. **Native Gemini Connector**

Current status: Not explicitly listed in the native providers (at least based on the official sidebar). Supported natively: Azure OpenAI, OpenAI, Anthropic, Ollama, GitHub Copilot.

Native connector for Gemini? Likely falls under "Custom Provider" or uses an OpenAI-compatible interface if Gemini supports it (which it can via the OpenAI library, though Gemini SDK is preferred).

2. **Gemini via google-genai?**

To confirm: Can we use google-genai (Gemini SDK) via a custom model wrapper? Looking for "Custom Provider" documentation.

3. **Azure Dependency**

State/Memory: "Local session" (in-memory) is supported without Azure. Persistent/Managed memory uses Azure AI Agent Service (Cosmos DB). Custom storage providers are possible.

Multi-agent: The framework's core task orchestration and agent communication should be local, but the "Agent Service" (cloud-hosted agents) is Azure-based.

#### Next Steps:

- Find "Custom Provider" code examples - **DONE**
- Search for Gemini-specific integration - **DONE**
- Check if "Magentic-One" (the multi-agent model) is related to this framework's Gemini support
