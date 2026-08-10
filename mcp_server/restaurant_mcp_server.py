"""AI Restaurant & Food Planner MCP Server.

Exposes restaurant planning tools over MCP (Model Context Protocol) for
Databricks Agent Bricks agents.

Restaurant Discovery & Search:
    - search_restaurants(location, term, categories, price, open_now, limit)
    - get_restaurant_details(restaurant_id, include_reviews)
    - compare_restaurants(restaurant_ids, comparison_factors)
    - semantic_restaurant_search(query, location, min_rating, max_price_level, limit)
    - recommend_restaurant(user_id, location, preferences, user_location)

Personal Notes:
    - save_restaurant_note(user_id, restaurant_id, note_text, tags, personal_rating, visit_date)
    - get_restaurant_notes(user_id, restaurant_id, limit)
    - update_restaurant_note(note_id, user_id, note_text, tags, personal_rating, visit_date)
    - delete_restaurant_note(note_id, user_id)

Favorites:
    - save_favorite(user_id, restaurant_id, notes)
    - get_favorites(user_id)
    - delete_favorite(user_id, restaurant_id)

Meal Plans:
    - create_meal_plan(user_id, plan_name, restaurant_ids, description, date)
    - get_meal_plans(user_id)
    - update_meal_plan(plan_id, user_id, plan_name, description, restaurant_ids, date)
    - delete_meal_plan(plan_id, user_id)

User Preferences:
    - save_preferences(user_id, preferred_cuisines, dietary_restrictions, budget_range, preferred_ambiance)
    - get_preferences(user_id)

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
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.lakebase_client import LakebaseClient
from recommendation_engine import RecommendationEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Note: FastMCP handles schema generation automatically.
# If Databricks Agent Bricks requires specific schema properties,
# those can be configured through FastMCP's built-in mechanisms.

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
@mcp.tool
def save_restaurant_note(
    user_id: str,
    restaurant_id: str,
    note_text: str,
    tags: list = None,
    personal_rating: float = None,
    visit_date: str = None
) -> dict:
    """
    Save a personal note for a restaurant.
    
    Use this to record observations, memories, or recommendations about a restaurant visit.
    Notes are private to each user and can include tags, personal ratings, and visit dates.
    
    Args:
        user_id: Your user identifier
        restaurant_id: Yelp business ID (from search results)
        note_text: Your note content (e.g., "Great ambiance, but a bit pricey")
        tags: Optional tags (e.g., ["favorite", "date-night", "vegetarian-friendly"])
        personal_rating: Optional personal rating 0-5 (independent of Yelp rating)
        visit_date: Optional visit date in YYYY-MM-DD format (e.g., "2024-03-15")
    
    Returns:
        Dict with success status and note_id if successful.
    
    Example:
        save_restaurant_note(
            user_id="user123",
            restaurant_id="okaeri-japanese-bistro-san-francisco-3",
            note_text="Amazing omakase experience! Chef was very friendly.",
            tags=["favorite", "special-occasion"],
            personal_rating=5.0,
            visit_date="2024-03-10"
        )
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Notes feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable notes"
        }
    
    if not note_text or not note_text.strip():
        return {
            "success": False,
            "error": "note_text cannot be empty"
        }
    
    # Validate personal_rating if provided
    if personal_rating is not None:
        if not (0 <= personal_rating <= 5):
            return {
                "success": False,
                "error": "personal_rating must be between 0 and 5"
            }
    
    try:
        note_id = lakebase_client.save_note(
            user_id=user_id,
            restaurant_id=restaurant_id,
            note_text=note_text.strip(),
            tags=tags,
            personal_rating=personal_rating,
            visit_date=visit_date
        )
        
        if note_id:
            return {
                "success": True,
                "note_id": note_id,
                "message": f"Note saved successfully for restaurant {restaurant_id}"
            }
        else:
            return {
                "success": False,
                "error": "Failed to save note to database"
            }
    
    except Exception as e:
        logger.error(f"Error saving note: {e}")
        return {
            "success": False,
            "error": f"Failed to save note: {str(e)}"
        }


@mcp.tool
def get_restaurant_notes(
    user_id: str,
    restaurant_id: str = None,
    limit: int = 100
) -> dict:
    """
    Get your saved notes for restaurants.
    
    Retrieve all your notes or filter by a specific restaurant.
    Notes include the note text, tags, personal rating, visit date, and restaurant details.
    
    Args:
        user_id: Your user identifier
        restaurant_id: Optional restaurant ID to filter by specific restaurant
        limit: Maximum number of notes to return (default 100, max 500)
    
    Returns:
        Dict with success status and array of notes.
        Each note includes: note_id, note_text, tags, personal_rating, visit_date,
        created_at, updated_at, restaurant_name, restaurant_rating, categories.
    
    Example:
        # Get all notes
        get_restaurant_notes(user_id="user123")
        
        # Get notes for specific restaurant
        get_restaurant_notes(
            user_id="user123",
            restaurant_id="okaeri-japanese-bistro-san-francisco-3"
        )
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Notes feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable notes"
        }
    
    try:
        notes = lakebase_client.get_user_notes(
            user_id=user_id,
            restaurant_id=restaurant_id,
            limit=min(limit, 500)
        )
        
        return {
            "success": True,
            "total": len(notes),
            "user_id": user_id,
            "restaurant_id": restaurant_id,
            "notes": notes
        }
    
    except Exception as e:
        logger.error(f"Error getting notes: {e}")
        return {
            "success": False,
            "error": f"Failed to get notes: {str(e)}"
        }


@mcp.tool
def update_restaurant_note(
    note_id: int,
    user_id: str,
    note_text: str = None,
    tags: list = None,
    personal_rating: float = None,
    visit_date: str = None
) -> dict:
    """
    Update an existing restaurant note.
    
    Only the note owner (matching user_id) can update a note.
    Provide only the fields you want to update; others remain unchanged.
    
    Args:
        note_id: Note ID to update (from get_restaurant_notes)
        user_id: Your user identifier (must match note owner)
        note_text: New note text (optional)
        tags: New tags (optional)
        personal_rating: New personal rating 0-5 (optional)
        visit_date: New visit date YYYY-MM-DD (optional)
    
    Returns:
        Dict with success status.
    
    Example:
        update_restaurant_note(
            note_id=42,
            user_id="user123",
            note_text="Updated: Still my favorite sushi spot!",
            tags=["favorite", "date-night", "must-try"]
        )
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Notes feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable notes"
        }
    
    # Validate personal_rating if provided
    if personal_rating is not None:
        if not (0 <= personal_rating <= 5):
            return {
                "success": False,
                "error": "personal_rating must be between 0 and 5"
            }
    
    # Check at least one field is provided
    if all(v is None for v in [note_text, tags, personal_rating, visit_date]):
        return {
            "success": False,
            "error": "At least one field must be provided to update",
            "hint": "Provide note_text, tags, personal_rating, or visit_date"
        }
    
    try:
        success = lakebase_client.update_note(
            note_id=note_id,
            user_id=user_id,
            note_text=note_text.strip() if note_text else None,
            tags=tags,
            personal_rating=personal_rating,
            visit_date=visit_date
        )
        
        if success:
            return {
                "success": True,
                "note_id": note_id,
                "message": f"Note {note_id} updated successfully"
            }
        else:
            return {
                "success": False,
                "error": f"Note {note_id} not found or you don't have permission to update it"
            }
    
    except Exception as e:
        logger.error(f"Error updating note: {e}")
        return {
            "success": False,
            "error": f"Failed to update note: {str(e)}"
        }


@mcp.tool
def delete_restaurant_note(
    note_id: int,
    user_id: str
) -> dict:
    """
    Delete a restaurant note.
    
    Only the note owner (matching user_id) can delete a note.
    This action is permanent and cannot be undone.
    
    Args:
        note_id: Note ID to delete (from get_restaurant_notes)
        user_id: Your user identifier (must match note owner)
    
    Returns:
        Dict with success status.
    
    Example:
        delete_restaurant_note(note_id=42, user_id="user123")
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Notes feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable notes"
        }
    
    try:
        success = lakebase_client.delete_note(
            note_id=note_id,
            user_id=user_id
        )
        
        if success:
            return {
                "success": True,
                "note_id": note_id,
                "message": f"Note {note_id} deleted successfully"
            }
        else:
            return {
                "success": False,
                "error": f"Note {note_id} not found or you don't have permission to delete it"
            }
    
    except Exception as e:
        logger.error(f"Error deleting note: {e}")
        return {
            "success": False,
            "error": f"Failed to delete note: {str(e)}"
        }




# ===== FAVORITES TOOLS =====

@mcp.tool
def save_favorite(
    user_id: str,
    restaurant_id: str,
    notes: str = None
) -> dict:
    """
    Save a restaurant as a favorite.
    
    Mark a restaurant as a favorite for quick access later. You can optionally
    add notes about why you like it or what to remember.
    
    Args:
        user_id: Your user identifier
        restaurant_id: Yelp business ID (from search results)
        notes: Optional notes about this favorite (e.g., "Best pizza in town", "Great date spot")
    
    Returns:
        Dict with success status.
    
    Example:
        save_favorite(
            user_id="user123",
            restaurant_id="okaeri-japanese-bistro-san-francisco-3",
            notes="Amazing omakase! Must try the chef's special."
        )
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Favorites feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable favorites"
        }
    
    try:
        success = lakebase_client.save_favorite(
            user_id=user_id,
            restaurant_id=restaurant_id,
            notes=notes
        )
        
        if success:
            return {
                "success": True,
                "restaurant_id": restaurant_id,
                "message": f"Restaurant {restaurant_id} added to favorites"
            }
        else:
            return {
                "success": False,
                "error": "Failed to save favorite to database"
            }
    
    except Exception as e:
        logger.error(f"Error saving favorite: {e}")
        return {
            "success": False,
            "error": f"Failed to save favorite: {str(e)}"
        }


@mcp.tool
def get_favorites(
    user_id: str
) -> dict:
    """
    Get all your saved favorite restaurants.
    
    Retrieve your complete list of favorite restaurants with their details,
    notes, and when you added them.
    
    Args:
        user_id: Your user identifier
    
    Returns:
        Dict with success status and array of favorites.
        Each favorite includes: restaurant_id, name, rating, price, categories,
        address, city, notes, created_at.
    
    Example:
        get_favorites(user_id="user123")
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Favorites feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable favorites"
        }
    
    try:
        favorites = lakebase_client.get_user_favorites(user_id=user_id)
        
        return {
            "success": True,
            "total": len(favorites),
            "user_id": user_id,
            "favorites": favorites
        }
    
    except Exception as e:
        logger.error(f"Error getting favorites: {e}")
        return {
            "success": False,
            "error": f"Failed to get favorites: {str(e)}"
        }


@mcp.tool
def delete_favorite(
    user_id: str,
    restaurant_id: str
) -> dict:
    """
    Remove a restaurant from your favorites.
    
    This action is permanent and cannot be undone.
    
    Args:
        user_id: Your user identifier
        restaurant_id: Yelp business ID to remove from favorites
    
    Returns:
        Dict with success status.
    
    Example:
        delete_favorite(user_id="user123", restaurant_id="some-restaurant-id")
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Favorites feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable favorites"
        }
    
    try:
        success = lakebase_client.remove_favorite(
            user_id=user_id,
            restaurant_id=restaurant_id
        )
        
        if success:
            return {
                "success": True,
                "restaurant_id": restaurant_id,
                "message": f"Restaurant {restaurant_id} removed from favorites"
            }
        else:
            return {
                "success": False,
                "error": f"Restaurant {restaurant_id} not found in favorites"
            }
    
    except Exception as e:
        logger.error(f"Error deleting favorite: {e}")
        return {
            "success": False,
            "error": f"Failed to delete favorite: {str(e)}"
        }


# ===== MEAL PLAN TOOLS =====

@mcp.tool
def create_meal_plan(
    user_id: str,
    plan_name: str,
    restaurant_ids: list,
    description: str = None,
    date: str = None
) -> dict:
    """
    Create a meal plan with multiple restaurants.
    
    Organize restaurants into a meal plan for events, trips, or weekly dining.
    Great for planning a food tour, date night itinerary, or group dining events.
    
    Args:
        user_id: Your user identifier
        plan_name: Name for this meal plan (e.g., "SF Food Tour 2024", "Date Night Ideas")
        restaurant_ids: List of Yelp business IDs to include in the plan
        description: Optional description of the plan (e.g., "Best Italian restaurants for anniversary")
        date: Optional date for the plan in YYYY-MM-DD format (e.g., "2024-06-15")
    
    Returns:
        Dict with success status and plan_id if successful.
    
    Example:
        create_meal_plan(
            user_id="user123",
            plan_name="Weekend Brunch Tour",
            restaurant_ids=["cafe-a-sf", "bistro-b-sf", "diner-c-sf"],
            description="Best brunch spots in the Mission",
            date="2024-03-23"
        )
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Meal plans feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable meal plans"
        }
    
    if not plan_name or not plan_name.strip():
        return {
            "success": False,
            "error": "plan_name cannot be empty"
        }
    
    if not restaurant_ids or len(restaurant_ids) == 0:
        return {
            "success": False,
            "error": "restaurant_ids must contain at least one restaurant"
        }
    
    try:
        plan_id = lakebase_client.create_meal_plan(
            user_id=user_id,
            plan_name=plan_name.strip(),
            restaurant_ids=restaurant_ids,
            description=description,
            date=date
        )
        
        if plan_id > 0:
            return {
                "success": True,
                "plan_id": plan_id,
                "message": f"Meal plan '{plan_name}' created successfully"
            }
        else:
            return {
                "success": False,
                "error": "Failed to create meal plan in database"
            }
    
    except Exception as e:
        logger.error(f"Error creating meal plan: {e}")
        return {
            "success": False,
            "error": f"Failed to create meal plan: {str(e)}"
        }


@mcp.tool
def get_meal_plans(
    user_id: str
) -> dict:
    """
    Get all your meal plans.
    
    Retrieve your complete list of meal plans with their restaurant IDs,
    descriptions, and dates.
    
    Args:
        user_id: Your user identifier
    
    Returns:
        Dict with success status and array of meal plans.
        Each plan includes: id, plan_name, description, restaurant_ids (array),
        date, created_at.
    
    Example:
        get_meal_plans(user_id="user123")
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Meal plans feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable meal plans"
        }
    
    try:
        plans = lakebase_client.get_user_meal_plans(user_id=user_id)
        
        return {
            "success": True,
            "total": len(plans),
            "user_id": user_id,
            "meal_plans": plans
        }
    
    except Exception as e:
        logger.error(f"Error getting meal plans: {e}")
        return {
            "success": False,
            "error": f"Failed to get meal plans: {str(e)}"
        }


@mcp.tool
def update_meal_plan(
    plan_id: int,
    user_id: str,
    plan_name: str = None,
    description: str = None,
    restaurant_ids: list = None,
    date: str = None
) -> dict:
    """
    Update an existing meal plan.
    
    Only the plan owner (matching user_id) can update a meal plan.
    Provide only the fields you want to update; others remain unchanged.
    
    Args:
        plan_id: Meal plan ID to update (from get_meal_plans)
        user_id: Your user identifier (must match plan owner)
        plan_name: New plan name (optional)
        description: New description (optional)
        restaurant_ids: New list of restaurant IDs (optional)
        date: New date YYYY-MM-DD (optional)
    
    Returns:
        Dict with success status.
    
    Example:
        update_meal_plan(
            plan_id=5,
            user_id="user123",
            description="Updated: Added vegetarian options",
            restaurant_ids=["restaurant-a", "restaurant-b", "restaurant-c"]
        )
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Meal plans feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable meal plans"
        }
    
    # Check at least one field is provided
    if all(v is None for v in [plan_name, description, restaurant_ids, date]):
        return {
            "success": False,
            "error": "At least one field must be provided to update",
            "hint": "Provide plan_name, description, restaurant_ids, or date"
        }
    
    try:
        success = lakebase_client.update_meal_plan(
            plan_id=plan_id,
            user_id=user_id,
            plan_name=plan_name.strip() if plan_name else None,
            description=description,
            restaurant_ids=restaurant_ids,
            date=date
        )
        
        if success:
            return {
                "success": True,
                "plan_id": plan_id,
                "message": f"Meal plan {plan_id} updated successfully"
            }
        else:
            return {
                "success": False,
                "error": f"Meal plan {plan_id} not found or you don't have permission to update it"
            }
    
    except Exception as e:
        logger.error(f"Error updating meal plan: {e}")
        return {
            "success": False,
            "error": f"Failed to update meal plan: {str(e)}"
        }


@mcp.tool
def delete_meal_plan(
    plan_id: int,
    user_id: str
) -> dict:
    """
    Delete a meal plan.
    
    Only the plan owner (matching user_id) can delete a meal plan.
    This action is permanent and cannot be undone.
    
    Args:
        plan_id: Meal plan ID to delete (from get_meal_plans)
        user_id: Your user identifier (must match plan owner)
    
    Returns:
        Dict with success status.
    
    Example:
        delete_meal_plan(plan_id=5, user_id="user123")
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Meal plans feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable meal plans"
        }
    
    try:
        success = lakebase_client.delete_meal_plan(
            plan_id=plan_id,
            user_id=user_id
        )
        
        if success:
            return {
                "success": True,
                "plan_id": plan_id,
                "message": f"Meal plan {plan_id} deleted successfully"
            }
        else:
            return {
                "success": False,
                "error": f"Meal plan {plan_id} not found or you don't have permission to delete it"
            }
    
    except Exception as e:
        logger.error(f"Error deleting meal plan: {e}")
        return {
            "success": False,
            "error": f"Failed to delete meal plan: {str(e)}"
        }


# ===== USER PREFERENCES TOOLS =====

@mcp.tool
def save_preferences(
    user_id: str,
    preferred_cuisines: str = None,
    dietary_restrictions: str = None,
    budget_range: str = None,
    preferred_ambiance: str = None
) -> dict:
    """
    Save or update your dining preferences.
    
    Set your preferences once and get better personalized recommendations.
    Your preferences persist across sessions.
    
    Args:
        user_id: Your user identifier
        preferred_cuisines: Comma-separated cuisines you like (e.g., "Italian, Japanese, Mexican")
        dietary_restrictions: Comma-separated dietary restrictions (e.g., "Vegetarian, Gluten-free")
        budget_range: Budget range as dollar signs (e.g., "$", "$", "$$", "$$")
        preferred_ambiance: Comma-separated ambiance preferences (e.g., "Casual, Romantic, Family-friendly")
    
    Returns:
        Dict with success status.
    
    Example:
        save_preferences(
            user_id="user123",
            preferred_cuisines="Italian, French, Japanese",
            dietary_restrictions="Vegetarian",
            budget_range="$",
            preferred_ambiance="Casual, Romantic"
        )
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Preferences feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable preferences"
        }
    
    try:
        success = lakebase_client.save_user_preferences(
            user_id=user_id,
            preferred_cuisines=preferred_cuisines,
            dietary_restrictions=dietary_restrictions,
            budget_range=budget_range,
            preferred_ambiance=preferred_ambiance
        )
        
        if success:
            return {
                "success": True,
                "message": "Preferences saved successfully"
            }
        else:
            return {
                "success": False,
                "error": "Failed to save preferences to database"
            }
    
    except Exception as e:
        logger.error(f"Error saving preferences: {e}")
        return {
            "success": False,
            "error": f"Failed to save preferences: {str(e)}"
        }


@mcp.tool
def get_preferences(
    user_id: str
) -> dict:
    """
    Get your saved dining preferences.
    
    Retrieve your current preference settings for cuisines, budget,
    dietary restrictions, and ambiance.
    
    Args:
        user_id: Your user identifier
    
    Returns:
        Dict with success status and preferences object.
        Preferences include: preferred_cuisines, dietary_restrictions,
        budget_range, preferred_ambiance.
    
    Example:
        get_preferences(user_id="user123")
    """
    if not lakebase_client:
        return {
            "success": False,
            "error": "Preferences feature requires Lakebase connection",
            "hint": "Configure LAKEBASE_URL secret to enable preferences"
        }
    
    try:
        preferences = lakebase_client.get_user_preferences(user_id=user_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "preferences": preferences
        }
    
    except Exception as e:
        logger.error(f"Error getting preferences: {e}")
        return {
            "success": False,
            "error": f"Failed to get preferences: {str(e)}"
        }


# ===== USAGE INSTRUCTIONS =====
# After adding these tools, update the module docstring at the top of the file:
#
# """AI Restaurant & Food Planner MCP Server.
# 
# Exposes restaurant planning tools over MCP (Model Context Protocol) for
# Databricks Agent Bricks agents:
#     - search_restaurants(location, term, categories, price, open_now, limit)
#     - get_restaurant_details(restaurant_id, include_reviews)
#     - compare_restaurants(restaurant_ids, comparison_factors)
#     - semantic_restaurant_search(query, location, min_rating, max_price_level, limit)
#     - recommend_restaurant(user_id, location, preferences, user_location)
#     - save_restaurant_note(user_id, restaurant_id, note_text, tags, personal_rating, visit_date)
#     - get_restaurant_notes(user_id, restaurant_id, limit)
#     - update_restaurant_note(note_id, user_id, note_text, tags, personal_rating, visit_date)
#     - delete_restaurant_note(note_id, user_id)
# 
# Backed by Yelp Fusion API and Lakebase Postgres with pgvector embeddings.
# """


if __name__ == "__main__":
    logger.info("Starting AI Restaurant & Food Planner MCP Server...")
    mcp.run(transport="streamable-http")
