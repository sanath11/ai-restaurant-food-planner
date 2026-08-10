"""AI Restaurant & Food Planner MCP Server.

Exposes restaurant planning tools over MCP (Model Context Protocol) for
Databricks Agent Bricks agents:
    - search_restaurants(location, term, categories, price, open_now, limit)
    - get_restaurant_details(restaurant_id, include_reviews)
    - compare_restaurants(restaurant_ids, comparison_factors)
    - semantic_restaurant_search(query, location, min_rating, max_price_level, limit)
    - recommend_restaurant(user_id, location, preferences, user_location)

Backed by Yelp Fusion API and Lakebase Postgres with pgvector embeddings.

Deploy as Databricks App via app.yaml. Run locally: python restaurant_mcp_server.py
"""

import os
import logging
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
import requests
from sentence_transformers import SentenceTransformer
import numpy as np

import secret_utils
from lakebase_client import LakebaseClient
from recommendation_engine import RecommendationEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== DATABRICKS SCHEMA COMPATIBILITY PATCH =====
# WHY: Databricks Agent Bricks requires "additionalProperties": false on ALL
# JSON schema objects with "properties" fields. FastMCP generates schemas without this,
# causing tool registration to fail. This patch intercepts schema generation and adds
# the required field.
#
# MUST run BEFORE creating the mcp instance so the patch is active during registration.

def fix_databricks_schemas(obj):
    """Recursively set additionalProperties: false in all schema objects."""
    if isinstance(obj, dict):
        if 'properties' in obj:
            obj['additionalProperties'] = False
        for value in obj.values():
            fix_databricks_schemas(value)
    elif isinstance(obj, list):
        for item in obj:
            fix_databricks_schemas(item)

# Monkey-patch FastMCP._get_tools to inject the fix
from fastmcp.server.server import FastMCP as FastMCPClass
original_get_tools = FastMCPClass._get_tools

def patched_get_tools(self):
    """Intercept tool schema generation and fix for Databricks."""
    tools = original_get_tools(self)
    for tool in tools:
        if hasattr(tool, 'inputSchema') and tool.inputSchema:
            fix_databricks_schemas(tool.inputSchema)
    return tools

FastMCPClass._get_tools = patched_get_tools
logger.info("✅ Installed Databricks schema compatibility patch on FastMCP")
# ===== END PATCH =====

mcp = FastMCP("restaurant-planner")

# Get API keys - secrets are stored as plain text (NOT base64-encoded)
YELP_API_KEY = secret_utils.get_secret(
    env_var_name="YELP_API_KEY",
    secret_scope="restaurant-app",
    secret_key="yelp-api-key",
    base64_encoded=False  # Yelp secrets are plain text
)

LAKEBASE_URL = secret_utils.get_secret(
    env_var_name="LAKEBASE_URL",
    secret_scope="restaurant-app",
    secret_key="lakebase-url",
    base64_encoded=False  # Lakebase URL is plain text
)

logger.info(f"YELP_API_KEY configured: {'Yes' if YELP_API_KEY else 'No'}")
logger.info(f"LAKEBASE_URL configured: {'Yes' if LAKEBASE_URL else 'No'}")

# Initialize Lakebase client for semantic search and recommendations
lakebase_client = None
if LAKEBASE_URL:
    try:
        lakebase_client = LakebaseClient(LAKEBASE_URL)
        logger.info("Lakebase client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Lakebase client: {e}")

# Initialize sentence transformer for semantic embeddings
# Using the same model as data ingestion pipeline
try:
    embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    logger.info("Embedding model loaded: all-MiniLM-L6-v2")
except Exception as e:
    logger.error(f"Failed to load embedding model: {e}")
    embedding_model = None

# Initialize recommendation engine with default weights
recommendation_engine = RecommendationEngine(
    w_rating=0.20,
    w_popularity=0.15,
    w_preference=0.20,
    w_semantic=0.25,
    w_price=0.10,
    w_distance=0.10
)


@mcp.tool
def search_restaurants(
    location: str,
    term: str = None,
    categories: str = None,
    price: str = None,
    open_now: bool = False,
    limit: int = 20
) -> dict:
    """
    Search for restaurants using Yelp API.
    
    Args:
        location: MUST be specific! Use formats like:
                  - "New York, NY" or "Manhattan, NY"
                  - "123 Main St, Austin, TX"
                  - "latitude,longitude" (e.g., "40.7128,-74.0060")
                  Vague locations like "Midtown" will fail - add city/state!
        term: Search term (e.g., "pizza", "sushi", "Indian food")
        categories: Comma-separated category aliases (e.g., "italian,pizza")
        price: Price levels (1-4 as string, e.g., "1,2" for $ and $$)
        open_now: Only return currently open restaurants
        limit: Number of results (max 50)
    
    Returns:
        Dict with success, total, restaurants array.
        On error: success=False with error message and helpful guidance.
    """
    if not YELP_API_KEY:
        return {"success": False, "error": "YELP_API_KEY not configured"}
    
    url = "https://api.yelp.com/v3/businesses/search"
    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    params = {
        "location": location,
        "limit": min(limit, 50)
    }
    
    if term:
        params["term"] = term
    if categories:
        params["categories"] = categories
    if price:
        params["price"] = price
    if open_now:
        params["open_now"] = True
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        # Log the actual request for debugging
        logger.info(f"Yelp API request: {response.url}")
        logger.info(f"Status code: {response.status_code}")
        
        if response.status_code != 200:
            error_detail = response.text
            logger.error(f"Yelp API error {response.status_code}: {error_detail}")
            return {
                "success": False,
                "error": f"Yelp API returned {response.status_code}",
                "details": error_detail,
                "url": response.url
            }
        
        data = response.json()
        
        restaurants = []
        for biz in data.get("businesses", []):
            restaurants.append({
                "id": biz.get("id"),
                "name": biz.get("name"),
                "rating": biz.get("rating"),
                "price": biz.get("price", "N/A"),
                "categories": [cat["title"] for cat in biz.get("categories", [])],
                "location": biz.get("location", {}).get("display_address", []),
                "phone": biz.get("phone", "N/A"),
                "distance_meters": biz.get("distance"),
                "url": biz.get("url"),
                "is_closed": biz.get("is_closed", False)
            })
        
        return {
            "success": True,
            "total": data.get("total", 0),
            "location_searched": location,
            "restaurants": restaurants
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Yelp API error: {e}")
        return {"success": False, "error": f"Yelp API error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool
def get_restaurant_details(
    restaurant_id: str,
    include_reviews: bool = True
) -> dict:
    """
    Get detailed information about a specific restaurant.
    
    Args:
        restaurant_id: Yelp business ID
        include_reviews: Whether to include user reviews
    
    Returns:
        Dict with success and complete restaurant details including reviews, hours, photos.
        On error: success=False with error message.
    """
    if not YELP_API_KEY:
        return {"success": False, "error": "YELP_API_KEY not configured"}
    
    url = f"https://api.yelp.com/v3/businesses/{restaurant_id}"
    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        result = {
            "success": True,
            "id": data.get("id"),
            "name": data.get("name"),
            "rating": data.get("rating"),
            "review_count": data.get("review_count"),
            "price": data.get("price", "N/A"),
            "categories": [cat["title"] for cat in data.get("categories", [])],
            "location": data.get("location", {}),
            "phone": data.get("phone", "N/A"),
            "display_phone": data.get("display_phone", "N/A"),
            "hours": data.get("hours", []),
            "photos": data.get("photos", []),
            "url": data.get("url"),
            "is_closed": data.get("is_closed", False),
            "transactions": data.get("transactions", [])
        }
        
        # Get reviews if requested
        if include_reviews:
            reviews_url = f"https://api.yelp.com/v3/businesses/{restaurant_id}/reviews"
            reviews_response = requests.get(reviews_url, headers=headers, timeout=10)
            if reviews_response.status_code == 200:
                reviews_data = reviews_response.json()
                result["reviews"] = reviews_data.get("reviews", [])
            else:
                result["reviews"] = []
        
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Yelp API error: {e}")
        return {"success": False, "error": f"Yelp API error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool
def compare_restaurants(
    restaurant_ids: list,
    comparison_factors: list = None
) -> dict:
    """
    Compare multiple restaurants side-by-side.
    
    Args:
        restaurant_ids: List of Yelp business IDs (2-5 restaurants)
                        Example: ["okaeri-japanese-bistro-san-francisco-3", "toyama-sushi-san-francisco"]
                        Use the 'id' field from search_restaurants results.
        comparison_factors: Factors to compare (rating, price, distance, etc.) - optional
    
    Returns:
        Dict with success, comparison_count, restaurants array, and summary.
        On error: success=False with error message.
    """
    if not isinstance(restaurant_ids, list) or len(restaurant_ids) < 2:
        return {
            "success": False,
            "error": "Need at least 2 restaurant IDs to compare",
            "hint": "Provide a list of Yelp business IDs from search_restaurants results"
        }
    
    if len(restaurant_ids) > 5:
        return {"success": False, "error": "Maximum 5 restaurants for comparison"}
    
    # Validate that these look like Yelp business IDs
    invalid_ids = []
    for rid in restaurant_ids:
        if not isinstance(rid, str) or " " in rid or not rid.replace("-", "").replace("_", "").isalnum():
            invalid_ids.append(rid)
    
    if invalid_ids:
        return {
            "success": False,
            "error": f"Invalid restaurant ID format: {invalid_ids}",
            "hint": "Use the 'id' field from search_restaurants results, not restaurant names. "
                    "Valid IDs are lowercase with hyphens, like: 'okaeri-japanese-bistro-san-francisco-3'"
        }
    
    # Fetch details for each restaurant
    restaurants = []
    failed = []
    
    for rid in restaurant_ids:
        details = get_restaurant_details(rid, include_reviews=False)
        if details.get("success"):
            restaurants.append(details)
        else:
            failed.append({"id": rid, "error": details.get("error")})
    
    if not restaurants:
        return {"success": False, "error": "Could not fetch any restaurant details", "failed": failed}
    
    # Build comparison summary
    valid_ratings = [r for r in restaurants if r.get("rating") is not None]
    valid_review_counts = [r for r in restaurants if r.get("review_count") is not None]
    
    summary = {}
    if valid_ratings:
        highest_rated = max(valid_ratings, key=lambda r: r.get("rating", 0))
        summary["highest_rated"] = {
            "name": highest_rated["name"],
            "rating": highest_rated["rating"]
        }
    
    if valid_review_counts:
        most_reviewed = max(valid_review_counts, key=lambda r: r.get("review_count", 0))
        summary["most_reviewed"] = {
            "name": most_reviewed["name"],
            "review_count": most_reviewed["review_count"]
        }
    
    return {
        "success": True,
        "comparison_count": len(restaurants),
        "restaurants": restaurants,
        "summary": summary,
        "failed": failed if failed else None
    }


@mcp.tool
def semantic_restaurant_search(
    query: str,
    location: str = None,
    min_rating: float = None,
    max_price_level: int = None,
    limit: int = 10
) -> dict:
    """
    Search restaurants using natural language semantic search.
    
    This uses AI embeddings to understand the MEANING of your query,
    not just keyword matching. Great for queries like:
    - "romantic Italian with outdoor seating"
    - "cozy brunch spot with good coffee"
    - "authentic Japanese ramen place"
    
    Args:
        query: Natural language description of what you're looking for
        location: Optional city/location filter (e.g., "San Francisco")
        min_rating: Minimum rating (0-5)
        max_price_level: Maximum price level (1-4)
        limit: Number of results (default 10, max 50)
    
    Returns:
        Dict with success, results array with similarity scores and full restaurant details.
        On error: success=False with error message.
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Semantic search requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable semantic search"
        }
    
    if not embedding_model:
        return {
            "success": False,
            "error": "Embedding model not loaded",
            "hint": "sentence-transformers model failed to initialize"
        }
    
    try:
        # Generate embedding for user query
        logger.info(f"Generating embedding for query: {query}")
        query_embedding = embedding_model.encode(query, convert_to_numpy=True)
        
        # Search using pgvector similarity
        results = lakebase_client.semantic_search_restaurants(
            query_embedding=query_embedding,
            location=location,
            min_rating=min_rating,
            max_price_level=max_price_level,
            limit=min(limit, 50)
        )
        
        if not results:
            return {
                "success": True,
                "total": 0,
                "query": query,
                "location": location,
                "restaurants": [],
                "message": "No restaurants found matching your criteria"
            }
        
        # Format results for output
        formatted_results = []
        for r in results:
            formatted_results.append({
                "id": r.get('yelp_id'),
                "name": r.get('name'),
                "rating": r.get('rating'),
                "review_count": r.get('review_count'),
                "price": '$' * (r.get('price_level') or 1),
                "categories": r.get('categories', []),
                "location": [r.get('address'), r.get('city'), r.get('state')],
                "similarity": round(r.get('similarity', 0), 3),
                "url": r.get('url'),
                "is_closed": r.get('is_closed', False)
            })
        
        return {
            "success": True,
            "total": len(formatted_results),
            "query": query,
            "location": location,
            "restaurants": formatted_results,
            "note": "Results ranked by semantic similarity to your query"
        }
    
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        return {
            "success": False,
            "error": f"Semantic search failed: {str(e)}"
        }


@mcp.tool
def recommend_restaurant(
    user_id: str,
    location: str,
    preferences: dict = None,
    user_location: dict = None,
    use_semantic_search: bool = True,
    semantic_query: str = None,
    limit: int = 5
) -> dict:
    """
    Get personalized restaurant recommendations using multi-factor AI scoring.
    
    This combines 6 factors for transparent, explainable recommendations:
    1. Rating (Yelp stars)
    2. Popularity (review count)
    3. Preference Match (your cuisine preferences)
    4. Semantic Similarity (AI understanding of what you want)
    5. Price Match (within your budget)
    6. Distance (proximity to you)
    
    Args:
        user_id: User identifier for personalization
        location: City or location to search (e.g., "San Francisco, CA")
        preferences: Optional dict with:
            - preferred_cuisines: List[str] (e.g., ["italian", "french"])
            - avoided_cuisines: List[str] (e.g., ["seafood"])
            - max_price_level: int (1-4, where 1=$ and 4=$$$$)
            - min_rating: float (0-5)
        user_location: Optional dict with 'latitude' and 'longitude' for distance scoring
        use_semantic_search: If True and semantic_query provided, uses semantic search first
        semantic_query: Natural language query (e.g., "romantic date spot")
        limit: Number of recommendations (default 5)
    
    Returns:
        Dict with success, recommendations array with scores and transparent evidence.
        Each recommendation includes:
        - restaurant details
        - total_score (0-1)
        - factor breakdown (rating_score, popularity_score, etc.)
        - evidence (why this was recommended)
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Recommendations require Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable recommendations"
        }
    
    preferences = preferences or {}
    
    try:
        # Step 1: Get candidate restaurants
        if use_semantic_search and semantic_query and embedding_model:
            # Use semantic search to find relevant restaurants
            logger.info(f"Using semantic search with query: {semantic_query}")
            query_embedding = embedding_model.encode(semantic_query, convert_to_numpy=True)
            
            candidates = lakebase_client.semantic_search_restaurants(
                query_embedding=query_embedding,
                location=location,
                min_rating=preferences.get('min_rating'),
                max_price_level=preferences.get('max_price_level'),
                limit=limit * 3  # Get more candidates to score
            )
        else:
            # Fall back to location-based search
            logger.info(f"Using location-based search for: {location}")
            candidates = lakebase_client.search_restaurants_by_location(
                location=location,
                categories=preferences.get('preferred_cuisines'),
                min_rating=preferences.get('min_rating'),
                max_price_level=preferences.get('max_price_level'),
                limit=limit * 3
            )
        
        if not candidates:
            return {
                "success": True,
                "total": 0,
                "user_id": user_id,
                "location": location,
                "recommendations": [],
                "message": "No restaurants found matching your criteria"
            }
        
        # Step 2: Score all candidates using multi-factor engine
        logger.info(f"Scoring {len(candidates)} candidates for user {user_id}")
        scored_restaurants = recommendation_engine.rank_restaurants(
            restaurants=candidates,
            user_preferences=preferences,
            user_location=user_location
        )
        
        # Step 3: Take top N
        top_recommendations = scored_restaurants[:limit]
        
        # Step 4: Format for output
        formatted_recommendations = []
        for rec in top_recommendations:
            restaurant = rec['restaurant']
            formatted_recommendations.append({
                "restaurant": {
                    "id": restaurant.get('yelp_id'),
                    "name": restaurant.get('name'),
                    "rating": restaurant.get('rating'),
                    "review_count": restaurant.get('review_count'),
                    "price": '$' * (restaurant.get('price_level') or 1),
                    "categories": restaurant.get('categories', []),
                    "address": restaurant.get('address'),
                    "city": restaurant.get('city'),
                    "state": restaurant.get('state'),
                    "url": restaurant.get('url'),
                    "is_closed": restaurant.get('is_closed', False)
                },
                "score": rec['total_score'],
                "factors": rec['factors'],
                "evidence": rec['evidence']
            })
        
        return {
            "success": True,
            "total": len(formatted_recommendations),
            "user_id": user_id,
            "location": location,
            "preferences": preferences,
            "recommendations": formatted_recommendations,
            "explanation": (
                "Recommendations ranked by multi-factor scoring (rating, popularity, "
                "preference match, semantic similarity, price match, distance). "
                "Each result includes transparent evidence and factor breakdown."
            )
        }
    
    except Exception as e:
        logger.error(f"Recommendation error for user {user_id}: {e}")
        return {
            "success": False,
            "error": f"Recommendation failed: {str(e)}"
        }


if __name__ == "__main__":
    logger.info("Starting AI Restaurant & Food Planner MCP Server...")
    mcp.run(transport="streamable-http")
