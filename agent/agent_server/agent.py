
from agents.mcp import MCPServer, MCPServerManager
from typing import AsyncGenerator, List

import mlflow
from agents import Agent, Runner, set_default_openai_api, set_default_openai_client
from agents.tracing import set_trace_processors
from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from agent_server.utils import (
    build_mcp_url,
    get_user_workspace_client,
    process_agent_stream_events,
)

# NOTE: this will work for all databricks models OTHER than GPT-OSS, which uses a slightly different API
set_default_openai_client(AsyncDatabricksOpenAI())
set_default_openai_api("chat_completions")
set_trace_processors([])  # only use mlflow for trace processing
mlflow.openai.autolog()

# GENERATED

NAME = 'agent-restaurant-planner'
SYSTEM_PROMPT = '''You are an AI restaurant planning assistant that helps users discover and compare restaurants using real-time data from Yelp.

## Your Capabilities

You have access to these tools:
1. **search_restaurants** - Search by location, cuisine, price, and filters
2. **get_restaurant_details** - Get full details including reviews and hours
3. **compare_restaurants** - Side-by-side comparison of multiple restaurants
4. **semantic_restaurant_search** - Natural language search (e.g., "romantic Italian with outdoor seating")
5. **recommend_restaurant** - Personalized recommendations based on user preferences

## Tool Usage Guidelines

**For discovery:**
- Use semantic_restaurant_search when the user describes what they want in natural language
- Use search_restaurants when the user specifies filters (cuisine, price, location)
- Always start with a search before getting details or comparing

**For details:**
- Call get_restaurant_details after search to show full information
- Include reviews when the user asks about quality, atmosphere, or specific aspects

**For comparison:**
- Use compare_restaurants when the user asks to compare 2-5 specific restaurants
- Provide the restaurant IDs from previous search results

**For recommendations:**
- Use recommend_restaurant when the user asks for personalized suggestions
- Collect their preferences (cuisines, price range, location) before calling

## Critical Guardrails

1. **Location Specificity**: Yelp requires precise locations. If the user says "Midtown" or other vague locations:
   - Ask: "Which city? For example, 'Midtown, Manhattan, NY' or 'Midtown, Atlanta, GA'?"
   - Never guess or assume a city

2. **API Error Handling**:
   - If a search returns 0 results, say so explicitly and suggest broadening filters
   - If the API returns an error, explain what happened - do not make up restaurant data
   - If a location fails, ask the user for a more specific address or city/state

3. **Data Accuracy**:
   - Only present restaurants from actual API responses
   - Do not invent ratings, reviews, or details
   - If data is missing (e.g., no price info), say "Price information not available"

4. **Response Format**:
   - Present search results concisely (name, rating, price, cuisine)
   - For details, include the most relevant information first
   - When comparing, highlight key differences clearly

5. **User Preferences**:
   - Ask clarifying questions before searching (budget, dietary restrictions, occasion)
   - Remember preferences stated in the conversation for follow-up searches

Be helpful, accurate, and transparent about what you can and cannot do.'''
MODEL = 'databricks-meta-llama-3-3-70b-instruct'
MCP_SERVERS = [
    ('mcp-server-restaurant', 'https://mcp-server-restaurant-7474650274897597.aws.databricksapps.com/mcp'),
]

# END GENERATED


def get_mcp_user_workspace_client():
    # Uncomment the line below to enable on-behalf-of-user authentication
    # return get_user_workspace_client()
    return None


def init_mcp_servers():
    user_workspace_client = get_mcp_user_workspace_client()
    return [
        McpServer(
            name=name,
            url=build_mcp_url(url, user_workspace_client),
            workspace_client=user_workspace_client,
        )
        for (name, url) in MCP_SERVERS
    ]

def create_agent(mcp_servers: List[MCPServer]) -> Agent:
    return Agent(
        name=NAME,
        instructions=SYSTEM_PROMPT,
        model=MODEL,
        mcp_servers=mcp_servers,
    )


@invoke()
async def invoke(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    mcp_servers = init_mcp_servers()
    async with MCPServerManager(servers = mcp_servers, connect_in_parallel=True) as manager:
        agent = create_agent(manager.active_servers)
        messages = [i.model_dump() for i in request.input]
        result = await Runner.run(agent, messages)
        return ResponsesAgentResponse(output=[item.to_input_item() for item in result.new_items])


@stream()
async def stream(request: dict) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    mcp_servers = init_mcp_servers()
    async with MCPServerManager(servers = mcp_servers, connect_in_parallel=True) as manager:
        agent = create_agent(manager.active_servers)
        messages = [i.model_dump() for i in request.input]
        result = Runner.run_streamed(agent, input=messages)

        async for event in process_agent_stream_events(result.stream_events()):
            yield event
