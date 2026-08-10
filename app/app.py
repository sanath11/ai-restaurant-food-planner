"""AI Restaurant Planner - Flask App with Lakebase backend."""
import os
import logging
from flask import Flask, jsonify, render_template, request
from functools import wraps
from sentence_transformers import SentenceTransformer
import numpy as np

from lakebase_client import LakebaseClient
import secret_utils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Lazy client initialization - secrets aren't available at module load time
_lakebase_client = None
_embedding_model = None

def get_lakebase_client():
    """Get or create LakebaseClient instance (lazy initialization)."""
    global _lakebase_client
    if _lakebase_client is None:
        lakebase_url = secret_utils.get_secret(
            env_var_name="LAKEBASE_URL",
            secret_scope="restaurant-app",
            secret_key="lakebase-url",
            base64_encoded=False
        )
        if not lakebase_url:
            raise ValueError("LAKEBASE_URL not configured")
        _lakebase_client = LakebaseClient(lakebase_url)
        logger.info("Lakebase client initialized")
    return _lakebase_client

def get_embedding_model():
    """Get or create SentenceTransformer model (lazy initialization)."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading embedding model...")
        _embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        logger.info("Embedding model loaded")
    return _embedding_model

# Databricks Apps authentication helper
def get_user_from_request():
    """Extract user info from Databricks request headers."""
    user_email = request.headers.get('X-Forwarded-Email', 'anonymous')
    return {'email': user_email}

def require_auth(f):
    """Simple auth decorator - Databricks Apps proxy handles authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function

@app.route("/healthz")
def healthz():
    """Health check endpoint."""
    return jsonify({"status": "ok"})

@app.errorhandler(Exception)
def handle_exception(err):
    """Return JSON errors."""
    status_code = getattr(err, "code", 500)
    if not isinstance(status_code, int):
        status_code = 500
    return jsonify({"error": str(err)}), status_code

@app.route("/")
def index():
    """Main dashboard UI."""
    return render_template("index.html")

@app.route("/api/search")
@require_auth
def api_search():
    """Search restaurants from Lakebase using semantic similarity."""
    term = request.args.get("term", "")
    cuisine = request.args.get("cuisine", "")
    price = request.args.get("price")  # e.g., "1,2,3"
    
    try:
        client = get_lakebase_client()
        model = get_embedding_model()
        
        # Build search query from term and cuisine for semantic search
        search_query = f"{term} {cuisine}".strip()
        if not search_query:
            search_query = "restaurant food dining"
        
        # Generate embedding for semantic search
        logger.info(f"Semantic search for: {search_query}")
        query_embedding = model.encode(search_query, convert_to_numpy=True)
        
        # Parse price filter
        max_price_level = None
        if price:
            price_levels = [int(p) for p in price.split(",") if p.isdigit()]
            if price_levels:
                max_price_level = max(price_levels)
        
        # Semantic search using cosine similarity (no location filter)
        restaurants = client.semantic_search_restaurants(
            query_embedding=query_embedding,
            max_price_level=max_price_level,
            limit=30
        )
        
        # Log results
        logger.info(f"Found {len(restaurants)} restaurants for query: {search_query}")
        if not restaurants:
            logger.warning(f"No restaurants found for semantic query: {search_query}, term={term}, cuisine={cuisine}")
        
        # Format for frontend
        formatted_restaurants = []
        for r in restaurants:
            formatted_restaurants.append({
                "id": r.get("yelp_id", ""),
                "name": r.get("name", ""),
                "rating": r.get("rating", 0),
                "review_count": r.get("review_count", 0),
                "price": "$" * (r.get("price_level", 1) or 1),
                "categories": [{"title": cat} for cat in (r.get("categories", []) or [])],
                "location": {
                    "display_address": [r.get("address", ""), r.get("city", ""), r.get("state", "")]
                },
                "image_url": "",
                "url": r.get("url", ""),
                "is_closed": r.get("is_closed", False),
                "similarity": round(r.get("similarity", 0), 3)
            })
        
        return jsonify({
            "success": True,
            "restaurants": formatted_restaurants,
            "count": len(formatted_restaurants)
        })
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/api/debug/db_status")
@require_auth
def api_debug_db_status():
    """Debug endpoint to check database status."""
    try:
        client = get_lakebase_client()
        conn = client._get_connection()
        cursor = conn.cursor()
        
        # Check total restaurants
        cursor.execute("SELECT COUNT(*) FROM restaurants")
        total_count = cursor.fetchone()[0]
        
        # Check restaurants with embeddings
        cursor.execute("SELECT COUNT(*) FROM restaurants WHERE embedding IS NOT NULL")
        embedding_count = cursor.fetchone()[0]
        
        # Get sample cities
        cursor.execute("SELECT DISTINCT city FROM restaurants LIMIT 10")
        cities = [row[0] for row in cursor.fetchall()]
        
        # Get sample restaurant
        cursor.execute("SELECT name, city, state, rating FROM restaurants LIMIT 1")
        sample = cursor.fetchone()
        
        cursor.close()
        
        return jsonify({
            "status": "connected",
            "total_restaurants": total_count,
            "restaurants_with_embeddings": embedding_count,
            "sample_cities": cities,
            "sample_restaurant": {
                "name": sample[0] if sample else None,
                "city": sample[1] if sample else None,
                "state": sample[2] if sample else None,
                "rating": sample[3] if sample else None
            } if sample else None
        })
    except Exception as e:
        logger.error(f"Database status check error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/api/details/<business_id>")
@require_auth
def api_details(business_id):
    """Get restaurant details from Lakebase."""
    try:
        client = get_lakebase_client()
        
        # business_id is the Yelp ID (the 'id' field in restaurants table)
        details = client.get_restaurant_by_id(business_id)
        
        if not details:
            return jsonify({"error": "Restaurant not found"}), 404
        
        # Format for frontend
        formatted = {
            "id": details.get("yelp_id"),
            "name": details.get("name"),
            "rating": details.get("rating"),
            "review_count": details.get("review_count"),
            "price": "$" * (details.get("price_level") or 1),
            "categories": [{"title": cat} for cat in (details.get("categories") or [])],
            "location": {
                "address1": details.get("address"),
                "city": details.get("city"),
                "state": details.get("state"),
                "zip_code": details.get("postal_code")
            },
            "phone": details.get("phone"),
            "url": details.get("url"),
            "is_closed": details.get("is_closed")
        }
        
        return jsonify({
            "success": True,
            "restaurant": formatted
        })
    except Exception as e:
        logger.error(f"Details error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/api/weather")
@require_auth
def api_weather():
    """Get weather for a location (stub endpoint)."""
    # Weather integration not yet implemented
    # Return stub data to prevent frontend errors
    return jsonify({
        "success": True,
        "weather": {
            "condition": "Available",
            "temperature": "--",
            "description": "Weather data coming soon"
        }
    })

@app.route("/api/compare", methods=["POST"])
@require_auth
def api_compare():
    """Compare multiple restaurants side-by-side."""
    try:
        data = request.get_json()
        restaurant_ids = data.get("restaurant_ids", [])
        
        if not restaurant_ids or len(restaurant_ids) < 2:
            return jsonify({
                "error": "Please provide at least 2 restaurant IDs to compare"
            }), 400
        
        if len(restaurant_ids) > 5:
            return jsonify({
                "error": "Maximum 5 restaurants can be compared at once"
            }), 400
        
        # Fetch details for each restaurant from Lakebase
        client = get_lakebase_client()
        restaurants = []
        errors = []
        
        for yelp_id in restaurant_ids:
            try:
                # yelp_id is the restaurant ID (the 'id' field)
                details = client.get_restaurant_by_id(yelp_id)
                
                if details:
                    # Format for comparison
                    formatted = {
                        "id": details.get("yelp_id"),
                        "name": details.get("name"),
                        "rating": details.get("rating"),
                        "review_count": details.get("review_count"),
                        "price": "$" * (details.get("price_level") or 1),
                        "categories": [{"title": cat} for cat in (details.get("categories") or [])]
                    }
                    restaurants.append(formatted)
                else:
                    errors.append(f"Could not fetch details for {yelp_id}")
            except Exception as e:
                errors.append(f"Failed to fetch {yelp_id}: {str(e)}")
        
        if not restaurants:
            return jsonify({
                "error": "Could not fetch any restaurant details",
                "details": errors
            }), 500
        
        # Generate comparison insights
        # Format price range as string for frontend
        price_lengths = [len(r.get("price", "$")) for r in restaurants]
        min_price = "$" * min(price_lengths) if price_lengths else "$"
        max_price = "$" * max(price_lengths) if price_lengths else "$"
        price_range_str = min_price if min_price == max_price else f"{min_price} to {max_price}"
        
        highest_rated = max(restaurants, key=lambda r: r.get("rating", 0))
        most_reviewed = max(restaurants, key=lambda r: r.get("review_count", 0))
        avg_rating = sum(r.get("rating", 0) for r in restaurants) / len(restaurants)
        
        # Generate comparison summary text
        summary = f"Comparing {len(restaurants)} restaurants reveals interesting differences. "
        
        if highest_rated["id"] == most_reviewed["id"]:
            summary += f"{highest_rated['name']} stands out as both the highest-rated ({highest_rated.get('rating', 0):.1f}★) and most popular with {most_reviewed.get('review_count', 0):,} reviews, making it a crowd favorite. "
        else:
            summary += f"{highest_rated['name']} leads in ratings with {highest_rated.get('rating', 0):.1f}★, while {most_reviewed['name']} is the most popular with {most_reviewed.get('review_count', 0):,} reviews. "
        
        summary += f"The average rating across all options is {avg_rating:.1f}★. "
        
        if min_price != max_price:
            summary += f"Price points vary from {min_price} to {max_price}, offering options for different budgets. "
        else:
            summary += f"All restaurants are in the {min_price} price range. "
        
        # Analyze cuisine diversity
        all_cuisines = set()
        for r in restaurants:
            for cat in r.get("categories", []):
                all_cuisines.add(cat.get("title", ""))
        
        if len(all_cuisines) > 3:
            summary += f"You'll find diverse cuisines including {', '.join(list(all_cuisines)[:3])}, and more."
        elif len(all_cuisines) > 1:
            summary += f"The selection includes {', '.join(all_cuisines)}."
        
        insights = {
            "highest_rated": highest_rated,
            "most_reviewed": most_reviewed,
            "average_rating": avg_rating,
            "price_range": price_range_str,
            "summary": summary
        }
        
        response_data = {
            "restaurants": restaurants,
            "insights": insights
        }
        
        if errors:
            response_data["partial_errors"] = errors
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/recommend", methods=["POST"])
@require_auth
def api_recommend():
    """Get personalized restaurant recommendations with scoring."""
    try:
        data = request.get_json()
        preferences = data.get("preferences", {})
        limit = min(data.get("limit", 3), 3)
        
        # Extract preferences
        preferred_cuisines = preferences.get("preferred_cuisines", [])
        max_price_level = preferences.get("max_price_level", 4)
        min_rating = preferences.get("min_rating", 0)
        
        # Search restaurants from Lakebase using semantic search
        client = get_lakebase_client()
        model = get_embedding_model()
        
        # Build search query from preferences for semantic search
        search_query = " ".join(preferred_cuisines) if preferred_cuisines else "restaurant food dining"
        query_embedding = model.encode(search_query, convert_to_numpy=True)
        
        # Semantic search with filters (no location)
        restaurants = client.semantic_search_restaurants(
            query_embedding=query_embedding,
            min_rating=min_rating,
            max_price_level=max_price_level,
            limit=limit * 2  # Get more to filter and rank
        )
        
        # Score and rank restaurants
        scored_restaurants = []
        for restaurant in restaurants:
            # Convert decimal.Decimal to float to avoid type errors
            rating = float(restaurant.get("rating", 0))
            review_count = float(restaurant.get("review_count", 0))
            price_level = int(restaurant.get("price_level", 1))
            categories = [cat.lower() for cat in (restaurant.get("categories", []) or [])]
            similarity = float(restaurant.get("similarity", 0.5))
            
            # Skip if below min rating (already filtered by query)
            if rating < min_rating:
                continue
            
            # Calculate scores (0-1 scale)
            rating_score = rating / 5.0
            popularity_score = min(review_count / 500.0, 1.0)  # Normalize by 500 reviews
            
            # Cuisine preference match
            preference_score = 0.0
            if preferred_cuisines:
                matches = sum(1 for pref in preferred_cuisines if any(pref.lower() in cat for cat in categories))
                preference_score = matches / len(preferred_cuisines)
            else:
                preference_score = similarity  # Use semantic similarity if no explicit preferences
            
            # Price match (closer to max is better)
            price_score = 1.0 - abs(max_price_level - price_level) / 3.0
            price_score = max(0, price_score)
            
            # Weighted total score (matching README weights where applicable)
            total_score = (
                rating_score * 0.35 +        # Rating: 35%
                popularity_score * 0.25 +    # Popularity: 25%
                preference_score * 0.30 +    # Preference/Similarity: 30%
                price_score * 0.10           # Price: 10%
            )
            
            # Generate evidence as array for frontend
            evidence = [
                f"{rating}/5 stars",
                f"{review_count} reviews" + (" (well-established)" if review_count > 200 else ""),
            ]
            
            if preferred_cuisines:
                matching_cats = [cat.title() for cat in categories[:2] if any(pref.lower() in cat for pref in preferred_cuisines)]
                if matching_cats:
                    evidence.append(f"Matches: {', '.join(matching_cats)}")
            
            price_display = "$" * price_level
            evidence.append(f"{price_display} price level")
            
            # Format restaurant for frontend
            formatted_restaurant = {
                "id": restaurant.get("yelp_id"),
                "name": restaurant.get("name"),
                "rating": rating,
                "review_count": review_count,
                "price": price_display,
                "categories": [{"title": cat.title()} for cat in categories],
                "location": {
                    "display_address": [restaurant.get("address"), restaurant.get("city"), restaurant.get("state")]
                },
                "url": restaurant.get("url"),
                "is_closed": restaurant.get("is_closed", False)
            }
            
            scored_restaurants.append({
                "restaurant": formatted_restaurant,
                "total_score": round(total_score, 3),
                "scoring_factors": {
                    "rating": round(rating_score, 3),
                    "popularity": round(popularity_score, 3),
                    "cuisine_match": round(preference_score, 3),
                    "price_match": round(price_score, 3)
                },
                "evidence": evidence
            })
        
        # Sort by total score descending
        scored_restaurants.sort(key=lambda x: x["total_score"], reverse=True)
        
        # Return top N
        recommendations = scored_restaurants[:limit]
        
        return jsonify({
            "success": True,
            "recommendations": recommendations,
            "count": len(recommendations),
            "metadata": {
                "preferences": preferences,
                "total_candidates": len(scored_restaurants),
                "search_type": "semantic"
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ask", methods=["POST"])
@require_auth
def api_ask():
    """Answer questions about selected restaurants using their reviews."""
    try:
        data = request.get_json()
        restaurant_ids = data.get("restaurant_ids", [])
        question = data.get("question", "")
        
        if not restaurant_ids:
            return jsonify({"error": "No restaurants selected"}), 400
        
        if not question:
            return jsonify({"error": "No question provided"}), 400
        
        # DEBUG LOGGING
        logger.info(f"🔍 /api/ask called with {len(restaurant_ids)} restaurants")
        logger.info(f"📋 Restaurant IDs: {restaurant_ids}")
        logger.info(f"❓ Question: {question}")
        
        client = get_lakebase_client()
        
        # Get restaurant details and reviews for each selected restaurant
        context_parts = []
        
        for yelp_id in restaurant_ids:
            logger.info(f"  🏪 Processing restaurant: {yelp_id}")
            # Get restaurant name and reviews
            conn = client._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM restaurants WHERE id = %s",
                (yelp_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            
            if not result:
                logger.warning(f"  ⚠️ Restaurant {yelp_id} not found in database")
                continue
            
            restaurant_name = result[0]
            logger.info(f"  ✅ Found restaurant: {restaurant_name}")
            
            # Get reviews (yelp_id is the restaurant_id)
            reviews = client.get_restaurant_reviews(yelp_id, limit=10)
            logger.info(f"  📝 Retrieved {len(reviews)} reviews")
            
            if reviews:
                context_parts.append(f"\n\n=== {restaurant_name} ===")
                context_parts.append(f"Reviews ({len(reviews)} samples):")
                for review in reviews:
                    rating = review.get("rating", 0)
                    text = review.get("text", "")
                    user = review.get("user_name", "Anonymous")
                    context_parts.append(f"- {user} ({rating}★): {text}")
        
        logger.info(f"📊 Total context parts collected: {len(context_parts)}")
        
        if not context_parts:
            logger.warning("⚠️ No context parts - returning 'No reviews found' message")
            return jsonify({
                "success": True,
                "answer": "No reviews found for the selected restaurants."
            })
        
        # Build context from reviews
        context = "\n".join(context_parts)
        
        # Use Databricks Foundation Model API to answer the question
        try:
            from databricks.sdk import WorkspaceClient
            from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
            
            w = WorkspaceClient()
            
            system_prompt = (
                "You are a helpful restaurant assistant. Answer questions based on the provided restaurant reviews. "
                "Be concise, informative, and cite specific reviews when relevant. "
                "If the reviews don't contain enough information to answer the question, say so."
            )
            
            user_prompt = f"""Based on these restaurant reviews:

{context}

Question: {question}

Provide a helpful, concise answer based on the reviews above."""
            
            response = w.serving_endpoints.query(
                name="databricks-meta-llama-3-3-70b-instruct",
                messages=[
                    ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
                    ChatMessage(role=ChatMessageRole.USER, content=user_prompt)
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            answer = response.choices[0].message.content
            
            return jsonify({
                "success": True,
                "answer": answer,
                "num_reviews": len(context_parts) - len(restaurant_ids)  # Approximate
            })
            
        except Exception as e:
            logger.error(f"LLM error: {e}", exc_info=True)
            # Fallback: simple summary
            answer = f"Found {len(context_parts) - len(restaurant_ids)} reviews across {len(restaurant_ids)} restaurant(s). However, I encountered an error processing them with AI. Please try again or rephrase your question."
            return jsonify({
                "success": True,
                "answer": answer,
                "fallback": True
            })
        
    except Exception as e:
        logger.error(f"Ask error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/api/favorites")
@require_auth
def api_favorites():
    """Get user's saved restaurants."""
    user = get_user_from_request()
    
    try:
        client = get_lakebase_client()
        conn = client._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT r.* FROM restaurants r
                JOIN saved_restaurants sr ON r.id = sr.restaurant_id
                WHERE sr.user_id = %s
                ORDER BY sr.saved_at DESC
                LIMIT 50
                """,
                (user['email'],)
            )
            favorites = cursor.fetchall()
            return jsonify({
                "success": True,
                "favorites": favorites
            })
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Favorites error: {e}", exc_info=True)
        return jsonify({
            "error": str(e),
            "hint": "Check that LAKEBASE_URL secret is configured and database tables exist"
        }), 500

if __name__ == "__main__":
    host = os.getenv("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_RUN_PORT", 8000))
    app.run(debug=True, host=host, port=port)
