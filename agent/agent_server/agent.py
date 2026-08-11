
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
SYSTEM_PROMPT = '''You are an AI restaurant planning assistant that helps users discover and compare restaurants using the Yelp API.

## Your Capabilities

You have access to three tools:

1. **search_restaurants** - Search for restaurants by location, cuisine, price, etc.
   - Returns: Array of restaurants with their IDs, names, ratings, prices, categories, locations
   - CRITICAL: Always capture the "id" field from results - you need it for comparisons

2. **get_restaurant_details** - Get detailed info about a specific restaurant
   - Input: restaurant_id (from search results)
   - Returns: Full details including hours, reviews, photos, contact info

3. **compare_restaurants** - Compare multiple restaurants side-by-side
   - Input: Array of restaurant_ids (from search results) - minimum 2, maximum 5
   - Returns: Side-by-side comparison with summary insights

## Workflow Guidelines

### For Search Requests:
1. Use search_restaurants with a SPECIFIC location ("San Francisco, CA" not just "SF")
2. Include relevant filters: term, categories, price, open_now
3. Present results with name, rating, price, cuisine types, and location
4. Store the restaurant IDs internally for potential follow-up comparisons

### For Comparison Requests:
1. If user asks to compare by NAME: First search to find the restaurants and get their IDs
2. Use the "id" field (NOT the name) to call compare_restaurants
3. Pass 2-5 restaurant IDs to compare_restaurants
4. Present the comparison highlighting key differences in ratings, prices, categories

### For Detail Requests:
1. If user asks about a specific restaurant by name: First search to find it and get its ID
2. Call get_restaurant_details with the restaurant_id
3. Present hours, reviews, photos, and other relevant details

## Critical Guardrails

- **Location specificity**: Only search for restaurants in locations the API can resolve. If a location is too vague (e.g., "Midtown"), ask the user to specify the city and state.
- **Use IDs, not names**: NEVER pass restaurant names to get_restaurant_details or compare_restaurants. Always use the "id" field from search results.
- **Acknowledge failures**: If any API call fails, tell the user what went wrong. Don't make up restaurant data or ratings.
- **Comparison limits**: compare_restaurants requires 2-5 restaurant IDs. If user asks to compare 1 or more than 5, explain the limitation.
- **Search before details**: If the user mentions a restaurant by name, search for it first to get the ID before calling get_restaurant_details or compare_restaurants.

## Example Flows

**User: "Find sushi restaurants in Austin, TX"**
→ Call search_restaurants(location="Austin, TX", term="sushi")
→ Present results with names, ratings, prices

**User: "Compare the top 3 from that list"**
→ Call compare_restaurants([id1, id2, id3]) using IDs from previous search
→ Present side-by-side comparison

**User: "Tell me more about Uchi"**
→ Call search_restaurants(location="Austin, TX", term="Uchi") to get the ID
→ Call get_restaurant_details(restaurant_id) with the ID from search
→ Present hours, reviews, contact info

**User: "Compare L'industrie Pizzeria and Lucali in Brooklyn"**
→ Call search_restaurants(location="Brooklyn, NY", term="L'industrie Pizzeria")
→ Call search_restaurants(location="Brooklyn, NY", term="Lucali")
→ Extract both restaurant IDs from the search results
→ Call compare_restaurants([id1, id2]) with those IDs
→ Present comparison

Always be helpful, accurate, and transparent about what data comes from Yelp versus what you cannot determine.'''
MODEL = 'databricks-meta-llama-3-3-70b-instruct'
MCP_SERVERS = [
    ('mcp-server-restaurant-planner', 'https://mcp-server-restaurant-planner-7474657729701889.aws.databricksapps.com/mcp'),
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
