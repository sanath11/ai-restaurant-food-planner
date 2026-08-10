# 🍽️ AI Restaurant & Food Planner

> Restaurant search with semantic embeddings, multi-factor scoring, and review Q&A.

[![Databricks](https://img.shields.io/badge/Databricks-Apps%20V2-FF3621?logo=databricks)](https://www.databricks.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Web%20App-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Lakebase](https://img.shields.io/badge/Lakebase-Postgres-336791?logo=postgresql&logoColor=white)](https://www.databricks.com/product/lakebase)

## Overview

A Flask web application that searches restaurants using pgvector embeddings and scores them with transparent multi-factor weighting. Deployed on Databricks Apps V2.

**What it does**:
* Searches restaurants by natural language: "romantic Italian with outdoor seating"
* Compares 2-5 restaurants with AI-generated insights
* Scores recommendations: rating (35%), popularity (25%), cuisine (30%), price (10%)
* Answers questions about reviews using Llama 3.1 70B
* Saves personal notes with tags and ratings

**Data flow**:
* Yelp Fusion API → Lakebase Postgres (restaurants + reviews)
* SentenceTransformer generates 384-dim embeddings
* pgvector `<=>` operator for cosine similarity search
* Foundation Models for review-based Q&A

## 🎯 Key Features

### 🍽️ Web Interface
Single-page application with two tabs:
* **Restaurant Assistant**: Unified natural language input for search, recommendations, meal planning, and preferences
* **Favorites**: Saved restaurants (backend ready, UI not implemented)

Restaurant cards are selectable. When 2+ are selected, a floating compare bar appears.

### 🔍 Restaurant Search
Semantic search using pgvector cosine similarity:
* **Input**: Natural language ("romantic Italian with outdoor seating")
* **Query**: Generates 384-dim embedding, searches via `<=>` operator
* **Output**: Restaurant cards with ratings, reviews, categories, similarity scores
* **KPIs**: Total count, average rating, price range, top category
* **Q&A**: Select restaurants and ask questions about their reviews (Llama 3.1 70B)

### ⚖️ Comparison
Analyze 2-5 selected restaurants:
* **KPI cards**: Highest rated, most popular, average rating, price range
* **AI insights**: Rating patterns, price diversity, cuisine variety
* **Comparison table**: Side-by-side ratings, review counts, prices, categories

### 📝 Personal Notes
CRUD operations for restaurant notes:
* **Tags**: Postgres ARRAY type ("favorite", "date-night", "must-try")
* **Personal rating**: 0-5 scale, independent of Yelp
* **Visit date**: DATE field for tracking visits
* **Schema**: `restaurant_notes` table with SERIAL primary key

### 🎯 Recommendations
Top 3 results with transparent scoring:

**Weights**:
* Rating: 35% (Yelp stars / 5.0)
* Popularity: 25% (log-scaled review count)
* Cuisine match: 30% (exact match)
* Price match: 10% (distance from budget)

**Output**:
* Total score (0-100%)
* Factor breakdown per restaurant
* Evidence explaining each score
* Medal indicators (🥇/🥈/🥉)

## 🔮 Future Scope

**Backend tables exist, frontend not implemented**:

* Favorites management UI (`favorites` table ready)
* Meal planning calendar (`meal_plans` table with ARRAY of restaurant IDs)
* User preferences UI (`user_preferences` table for cuisines, dietary restrictions, budget)
* Search history tracking (no table)
* Budget tracking (no table)
* Spending analytics (no table)
* Cuisine diversity visualization (no table)
* Restaurant alerts (no table)
* Price change tracking (no table)

## 🏛️ Architecture

### System Architecture

```
Browser (HTML/JS)
  ↓ HTTPS fetch()
Flask App (app/app.py)
  ├─ /api/search       → Lakebase pgvector <=> cosine similarity
  ├─ /api/compare      → Fetch 2-5 restaurants, generate text insights
  ├─ /api/recommend    → recommendation_engine.py (4-factor scoring)
  ├─ /api/details      → Single restaurant lookup
  ├─ /api/ask          → Review Q&A via Llama 3.1 70B
  └─ /api/favorites    → CRUD on favorites table
  ↓
Lakebase Postgres
  ├─ restaurants (Yelp data)
  ├─ restaurant_embeddings (384-dim vectors)
  ├─ review_embeddings (review text + vectors)
  ├─ restaurant_notes (user notes, tags ARRAY, ratings)
  ├─ favorites (user_id, restaurant_id)
  ├─ meal_plans (plan_id, restaurant_ids ARRAY)
  └─ user_preferences (cuisines, dietary restrictions, budget)
```

**Components**:
* **Frontend**: Single-page app (index.html), vanilla JS, fetch() for API calls
* **Backend**: Flask with 17 REST endpoints (app/app.py)
* **Database**: Lakebase Postgres with pgvector extension (7 tables)
* **Scoring**: recommendation_engine.py (rating 35%, popularity 25%, cuisine 30%, price 10%)
* **LLM**: Databricks Foundation Models API (Llama 3.1 70B) for review Q&A

### Project Structure

```
ai-restaurant-food-planner/
├── app/                           # Flask web application
│   ├── app.py                     # Main Flask server with API routes
│   ├── templates/                 # HTML templates directory
│   │   └── index.html             # Frontend UI (single-page app)
│   ├── yelp_adapter.py            # Yelp Fusion API integration
│   ├── secret_utils.py            # Databricks secrets helper
│   ├── app.yaml                   # Databricks App configuration
│   ├── requirements.txt           # Python dependencies
│   └── README.md                  # App-specific documentation
│
├── mcp_server/                    # MCP server implementation
│   ├── restaurant_mcp_server.py   # MCP server for restaurant data
│   ├── lakebase_client.py         # Lakebase Postgres client with pgvector and auto-reconnect
│   ├── recommendation_engine.py   # Multi-factor recommendation scoring
│   ├── secret_utils.py            # Secrets management
│   ├── app.yaml                   # MCP server configuration
│   └── requirements.txt           # Python dependencies
│
├── notebooks/                     # Data ingestion notebooks
│   ├── ingest_restaurants_embeddings  # Yelp → Lakebase pipeline
│   └── ingest_reviews_embeddings      # Reviews + embeddings generation
│
├── agent/                         # Agent Bricks integration
│   ├── agent_server/              # Agent server implementation
│   ├── scripts/                   # Agent scripts
│   ├── .github/                   # GitHub workflows
│   ├── databricks.yml             # Databricks bundle config
│   ├── manifest.yaml              # Agent manifest
│   └── README.md                  # Agent documentation
│
├── pipeline/                      # Data pipeline configurations
│   └── ingest_yelp_data.yaml      # Yelp data ingestion pipeline
│
├── sql/                           # SQL scripts and queries
│
├── README.md                      # This file (project overview)
├── setup_secrets.py               # Secrets configuration helper
└── agent_bricks_system_prompt.md  # Agent Bricks system prompt
```

## 📡 API Endpoints Reference

The Flask backend exposes **6 REST API endpoints** for restaurant operations:

### 1. `GET /api/search`

**Semantic search** with filters - uses Lakebase Postgres with pgvector cosine similarity (`<=>` operator) on 384-dimensional embeddings.

```json
{
  "location": "San Francisco, CA",
  "cuisine": "pizza",
  "keyword": "italian",
  "price_level": "2",
  "open_now": true,
  "limit": 20
}
```

**Returns**:
```json
{
  "restaurants": [
    {
      "id": "restaurant-id",
      "name": "Restaurant Name",
      "rating": 4.5,
      "review_count": 230,
      "price": "$",
      "categories": ["Italian", "Pizza"],
      "location": {"address": "123 Main St", "city": "San Francisco"},
      "phone": "+14155551234",
      "image_url": "https://..."
    }
  ],
  "kpis": {
    "total_count": 15,
    "avg_rating": 4.3,
    "price_range": "$-$$",
    "top_category": "Italian"
  }
}

---

### 2. `GET /api/details/<restaurant_id>`

**Detailed information** for a specific restaurant including hours, photos, and attributes.

**URL Parameters**:
* `restaurant_id`: Yelp business ID (e.g., `okaeri-japanese-bistro-san-francisco-3`)

**Returns**:
```json
{
  "id": "restaurant-id",
  "name": "Restaurant Name",
  "rating": 4.5,
  "review_count": 230,
  "price": "$",
  "categories": ["Italian", "Pizza"],
  "location": {...},
  "phone": "+14155551234",
  "hours": [{"day": 0, "start": "1100", "end": "2200"}],
  "photos": ["https://..."],
  "transactions": ["delivery", "pickup"]
}

---

### 3. `POST /api/compare`

**Side-by-side comparison** of 2-5 restaurants with AI-generated insights.

```json
{
  "restaurant_ids": [
    "okaeri-japanese-bistro-san-francisco-3",
    "toyama-sushi-san-francisco"
  ]
}
```

**Returns**:
```json
{
  "restaurants": [{...}, {...}],
  "kpis": {
    "highest_rated": {"name": "...", "rating": 4.5},
    "most_popular": {"name": "...", "reviews": 450},
    "average_rating": 4.3,
    "price_range": "$-$$"
  },
  "insights": {
    "summary": "AI-generated analysis highlighting rating patterns, price diversity, and cuisine variety",
    "rating_analysis": "...",
    "price_diversity": "...",
    "cuisine_variety": "..."
  }
}

---

### 4. `POST /api/recommend`

**AI-powered recommendations** using multi-factor transparent scoring. Returns top 3 personalized picks.

```json
{
  "location": "San Francisco, CA",
  "cuisines": ["Italian", "French"],
  "max_price": 3,
  "min_rating": 4.0,
  "limit": 3
}
```

**Scoring factors**:
* **Rating** (35%) - Yelp star rating quality
* **Popularity** (25%) - Review count as social proof
* **Cuisine Match** (30%) - Alignment with preferences
* **Price Match** (10%) - Budget compatibility

**Returns**:
```json
{
  "recommendations": [
    {
      "restaurant": {...},
      "score": 85.5,
      "scoring_factors": {
        "rating_score": 90.0,
        "popularity_score": 82.0,
        "cuisine_match_score": 100.0,
        "price_match_score": 70.0
      },
      "evidence": [
        "High rating: 4.5/5 stars based on 230 reviews",
        "Popular: 230 reviews",
        "Cuisine match: Italian",
        "Price level: $ (within budget)"
      ]
    }
  ]
}
```

---

### 5. `POST /api/ask`

**Review-based question answering** powered by Databricks Foundation Models.

```json
{
  "restaurant_ids": ["restaurant-id-1", "restaurant-id-2"],
  "question": "What do people say about the service?"
}
```

**Returns**:
```json
{
  "success": true,
  "answer": "Based on reviews, customers consistently praise the attentive and friendly service...",
  "num_reviews": 25
}
```

**How it works**:
1. Retrieves reviews for selected restaurants from `review_embeddings` table in Lakebase
2. Constructs context from review text with up to 5 reviews per restaurant
3. Uses Databricks Foundation Model (Meta Llama 3.1 70B) to answer questions
4. Returns natural language answer with source attribution

---

### 6. `GET /api/favorites/get`

**User favorites management** - retrieve saved favorite restaurants.

**Returns**:
```json
{
  "success": true,
  "total": 5,
  "favorites": [
    {
      "restaurant_id": "restaurant-id",
      "restaurant_name": "Restaurant Name",
      "saved_at": "2024-03-15T10:30:00Z"
    }
  ]
}
```

### 7. `POST /api/favorites/save`

**Add restaurant to favorites**.

```json
{
  "restaurant_id": "restaurant-id",
  "restaurant_name": "Restaurant Name"
}
```

### 8. `POST /api/favorites/remove`

**Remove restaurant from favorites**.

```json
{
  "restaurant_id": "restaurant-id"
}
```

### 9. `GET /api/meal-plans/get`

**Retrieve user's meal plans**.

**Returns**:
```json
{
  "success": true,
  "meal_plans": [
    {
      "id": 1,
      "plan_name": "Weekend Brunch Tour",
      "description": "Best brunch spots",
      "restaurant_ids": ["id1", "id2", "id3"],
      "date": "2024-03-23",
      "created_at": "2024-03-15T10:00:00Z",
      "updated_at": "2024-03-15T10:00:00Z"
    }
  ]
}
```

### 10. `POST /api/meal-plans/create`

**Create a new meal plan**.

```json
{
  "plan_name": "Weekend Food Tour",
  "description": "Italian restaurants",
  "restaurant_ids": ["id1", "id2"],
  "date": "2024-03-30"
}
```

### 11. `POST /api/meal-plans/delete`

**Delete a meal plan**.

```json
{
  "plan_id": 1
}
```

### 12. `GET /api/preferences/get`

**Retrieve user dining preferences**.

**Returns**:
```json
{
  "success": true,
  "preferences": {
    "preferred_cuisines": "Italian, Japanese",
    "dietary_restrictions": "Vegetarian",
    "budget_range": "$",
    "preferred_ambiance": "Casual, Romantic"
  }
}
```

### 13. `POST /api/preferences/save`

**Save or update user preferences**.

```json
{
  "preferred_cuisines": "Italian, French",
  "dietary_restrictions": "Vegetarian",
  "budget_range": "$",
  "preferred_ambiance": "Casual"
}
```

### 14. `GET /api/notes/get`

**Retrieve user's restaurant notes**.

**Query Parameters**:
* `restaurant_id` (optional): Filter by specific restaurant

**Returns**:
```json
{
  "success": true,
  "notes": [
    {
      "note_id": 1,
      "note_text": "Great ambiance!",
      "tags": ["favorite", "date-night"],
      "personal_rating": 5.0,
      "visit_date": "2024-03-10",
      "restaurant_name": "Bella Italia",
      "created_at": "2024-03-15T10:00:00Z",
      "updated_at": "2024-03-15T10:00:00Z"
    }
  ]
}
```

### 15. `POST /api/notes/create`

**Create a restaurant note**.

```json
{
  "restaurant_id": "restaurant-id",
  "note_text": "Amazing food!",
  "tags": ["favorite"],
  "personal_rating": 5.0,
  "visit_date": "2024-03-10"
}
```

### 16. `POST /api/notes/update/<note_id>`

**Update an existing note**.

```json
{
  "note_text": "Still amazing!",
  "tags": ["favorite", "must-visit"],
  "personal_rating": 5.0
}
```

### 17. `POST /api/notes/delete/<note_id>`

**Delete a note** (no body required).

---

## 🧑‍💻 MCP Tools Reference

The MCP server (`mcp_server/restaurant_mcp_server.py`) exposes **15 tools** for AI agents:

### Restaurant Discovery Tools

1. **`search_restaurants`** - Semantic search with pgvector cosine similarity
   * Parameters: location, cuisine, keyword, price_level, open_now, limit
   * Returns: List of restaurants with similarity scores

2. **`get_restaurant_details`** - Get full details for a single restaurant
   * Parameters: restaurant_id
   * Returns: Complete restaurant information including hours and photos

3. **`recommend_restaurant`** - AI-powered recommendations with transparent scoring
   * Parameters: location, cuisines, max_price, min_rating, limit
   * Returns: Top N scored restaurants with factor breakdown and evidence

### Notes Management Tools

4. **`save_restaurant_note`** - Create a new note for a restaurant
   * Parameters: restaurant_id, note_text, tags (optional), personal_rating (optional), visit_date (optional)
   * Returns: Created note with note_id

5. **`get_restaurant_notes`** - Retrieve user's notes
   * Parameters: restaurant_id (optional), limit
   * Returns: List of notes, optionally filtered by restaurant

6. **`update_restaurant_note`** - Update an existing note
   * Parameters: note_id, note_text (optional), tags (optional), personal_rating (optional), visit_date (optional)
   * Returns: Updated note

7. **`delete_restaurant_note`** - Delete a note
   * Parameters: note_id
   * Returns: Success confirmation

### Review Analysis Tool

8. **`ask_about_reviews`** - Answer questions about restaurant reviews using Foundation Models
   * Parameters: restaurant_ids (list), question
   * Returns: AI-generated answer based on review content

### Favorites Management Tools

9. **`save_favorite`** - Add a restaurant to favorites
   * Parameters: user_id, restaurant_id, notes (optional)
   * Returns: Success confirmation

10. **`get_favorites`** - Retrieve user's favorite restaurants
    * Parameters: user_id
    * Returns: List of favorites with restaurant details

11. **`delete_favorite`** - Remove a restaurant from favorites
    * Parameters: user_id, restaurant_id
    * Returns: Success confirmation

### Meal Plan Tools

12. **`create_meal_plan`** - Create a meal plan with multiple restaurants
    * Parameters: user_id, plan_name, restaurant_ids (array), description (optional), date (optional)
    * Returns: Created plan with plan_id

13. **`get_meal_plans`** - Retrieve user's meal plans
    * Parameters: user_id
    * Returns: List of meal plans with restaurant IDs and metadata

14. **`update_meal_plan`** - Update an existing meal plan
    * Parameters: plan_id, user_id, plan_name (optional), description (optional), restaurant_ids (optional), date (optional)
    * Returns: Success confirmation

15. **`delete_meal_plan`** - Delete a meal plan
    * Parameters: plan_id, user_id
    * Returns: Success confirmation

### User Preferences Tools

16. **`save_preferences`** - Save or update user dining preferences
    * Parameters: user_id, preferred_cuisines, dietary_restrictions, budget_range, preferred_ambiance
    * Returns: Success confirmation

17. **`get_preferences`** - Retrieve user's saved preferences
    * Parameters: user_id
    * Returns: Preferences object with cuisines, restrictions, budget, ambiance

**Database Schemas**: Lakebase Postgres table structures

```sql
-- Restaurant notes with ARRAY tags
CREATE TABLE restaurant_notes (
    note_id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    restaurant_id TEXT NOT NULL,
    note_text TEXT NOT NULL,
    tags TEXT[],  -- Postgres ARRAY type
    personal_rating NUMERIC(2, 1) CHECK (personal_rating >= 0 AND personal_rating <= 5),
    visit_date DATE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- User favorites
CREATE TABLE favorites (
    user_id TEXT NOT NULL,
    restaurant_id TEXT NOT NULL,
    restaurant_name TEXT NOT NULL,
    saved_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, restaurant_id)
);

-- Meal plans
CREATE TABLE meal_plans (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    plan_name TEXT NOT NULL,
    description TEXT,
    restaurant_ids TEXT[],  -- Postgres ARRAY type
    date DATE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- User preferences
CREATE TABLE user_preferences (
    user_id TEXT PRIMARY KEY,
    preferred_cuisines TEXT,
    dietary_restrictions TEXT,
    budget_range TEXT,
    preferred_ambiance TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 🚀 Quick Start

### Prerequisites

* Databricks workspace with Apps V2
* Python 3.11+
* Yelp Fusion API key (free tier: 5000 req/day)

### Step 1: Get Yelp API Key

1. Go to [Yelp Fusion](https://www.yelp.com/developers/v3/manage_app)
2. Create app (name + description)
3. Copy API Key (format: `AbCdEf123...`)
4. Authentication uses Bearer token:
   ```bash
   Authorization: Bearer YOUR_API_KEY
   ```

### Step 2: Set Up Lakebase Postgres

**Required tables**:
- `restaurants` - core restaurant data
- `restaurant_embeddings` - 384-dim vectors for semantic search
- `review_embeddings` - review text with embeddings
- `restaurant_notes` - user notes (tags, ratings, visit dates)
- `favorites` - user favorites
- `meal_plans` - meal planning data
- `user_preferences` - user dietary preferences

**Data ingestion**:
1. Run `notebooks/ingest_restaurants_embeddings` to fetch from Yelp API and generate embeddings (SentenceTransformer)
2. Run `notebooks/ingest_reviews_embeddings` for review data

**Configure connection**:
```bash
databricks secrets put-secret restaurant-app lakebase-connection-url
# Format: postgres://user:pass@host:port/database
```

### Step 3: Configure Databricks Secrets

```bash
# Create secret scope
databricks secrets create-scope restaurant-app

# Store Yelp API key (plain text)
databricks secrets put-secret restaurant-app yelp-api-key
# Paste your Yelp Fusion API key when prompted
```

### Step 4: Deploy Flask Web Application

1. **Navigate to app directory**:
   ```bash
   cd app
   ```

2. **Review app.yaml configuration**:
   ```yaml
   command:
     - python
     - app.py
   env:
     - name: YELP_API_KEY
       valueFrom: "{{secrets/restaurant-app/yelp-api-key}}"
   ```

3. **Deploy via Databricks Apps**:
   ```bash
   # Create the app
   databricks apps create ai-restaurant-planner \
     --description "AI Restaurant & Food Planner Web App" \
     --source-code-path ./
   
   # Deploy
   databricks apps deploy ai-restaurant-planner
   
   # Check status
   databricks apps get ai-restaurant-planner
   # Should show status: RUNNING
   ```

4. **Access the application**:
   * URL: `https://<workspace>.cloud.databricks.com/apps/ai-restaurant-planner`
   * The web interface will load automatically

**UI Tabs**:
* **Restaurant Assistant**: Natural language input → calls /api/search, /api/recommend, /api/meal-plans, /api/preferences
* **Favorites**: Saved restaurants (backend ready, frontend not implemented)

---

### Step 5: Verify Deployment

**Test semantic search**:
1. Restaurant Assistant tab
2. Type: "Find Italian restaurants in San Francisco"
3. Click Go
4. Verify: Restaurant cards appear with ratings, categories

**Test comparison**:
1. Click 2-5 restaurant cards (highlights them)
2. Click "Compare" in floating bar
3. Verify: KPI cards, insights text, side-by-side table

**Test recommendations**:
1. Type: "Recommend romantic dinner spots"
2. Click Go
3. Verify: Top 3 scored results with 🥇/🥈/🥉 medals

## 🛠️ Technical Deep Dive

### External API: Yelp Fusion

**Base URL**: `https://api.yelp.com/v3`

**Authentication**: Bearer token via `Authorization` header
```bash
Authorization: Bearer YOUR_API_KEY_HERE
```

**Endpoints used**:
1. **Search** - `GET /businesses/search`
   * Params: location, term, categories, price, open_now, limit
   * Rate: Main endpoint for keyword search

2. **Business Details** - `GET /businesses/{id}`
   * Returns: Full details including hours, photos, transactions

3. **Reviews** - `GET /businesses/{id}/reviews`
   * Returns: Up to 3 user reviews per restaurant

**Rate Limits**:
* Free tier: **5,000 requests/day**
* Paid tier: 25,000+ requests/day
* Per-second: Not specified (client implements polite delays)

**Error handling**:
* 429 Too Many Requests → exponential backoff
* 400 Bad Request → location validation hints
* Network errors → graceful degradation

---

### Scoring Engine

**File**: `mcp_server/recommendation_engine.py`

**Algorithm**: Weighted multi-factor scoring with transparent evidence generation

```python
class ScoringEngine:
    def __init__(self,
        w_rating=0.35,      # Yelp star rating (0-5)
        w_popularity=0.25,  # Review count (log-scaled)
        w_cuisine=0.30,     # Cuisine match
        w_price=0.10        # Budget alignment
    )
    
    def score_restaurants(self, restaurants, preferences):
        # Score each restaurant 0-100 per factor
        # Weighted sum → total_score (percentage)
        # Generate evidence array explaining each score
        return sorted(scored_restaurants, key=lambda x: x['score'], reverse=True)
```

**Scoring formulas**:
* **Rating**: `(rating / 5.0) * 100` (linear percentage)
* **Popularity**: `(log(review_count + 1) / log(max_reviews + 1)) * 100` (log-scaled percentage)
* **Cuisine**: `100` if match, `0` if no match (exact matching)
* **Price**: `100 - (abs(user_max - restaurant_price) * 33.3)` (distance from budget)

**Output structure**:
```json
{
  "restaurant": {"name": "Bella Italia", "rating": 4.5, ...},
  "score": 87.5,
  "scoring_factors": {
    "rating_score": 90.0,
    "popularity_score": 82.0,
    "cuisine_match_score": 100.0,
    "price_match_score": 70.0
  },
  "evidence": [
    "High rating: 4.5/5 stars based on 230 reviews",
    "Popular: 230 reviews",
    "Cuisine match: Italian",
    "Price level: $ (within budget)"
  ]
}
```

---

### Comparison Analysis Engine

**File**: `app/app.py` (in `/api/compare` endpoint)

**AI-Generated Insights**: The comparison endpoint generates contextual analysis:

```python
def generate_comparison_summary(restaurants):
    # Analyze rating patterns
    highest_rated = max(restaurants, key=lambda r: r['rating'])
    
    # Analyze popularity
    most_reviewed = max(restaurants, key=lambda r: r['review_count'])
    
    # Analyze price diversity
    price_levels = set(r['price'] for r in restaurants)
    price_diversity = "varied" if len(price_levels) > 1 else "similar"
    
    # Analyze cuisine variety
    all_categories = set()
    for r in restaurants:
        all_categories.update(r['categories'])
    
    # Generate natural language summary
    return f"Among these options, {highest_rated['name']} stands out with the highest rating..."
```

**Generated Insights Include**:
* **Rating Analysis**: Identifies highest-rated restaurant and rating patterns
* **Popularity Assessment**: Highlights most-reviewed (most popular) options
* **Price Diversity**: Notes price range and budget considerations
* **Cuisine Variety**: Describes cuisine diversity across selections


## 🛍️ Usage Examples

### Example 1: Semantic Search

**Input**: "Find Italian restaurants in San Francisco under $20"

**Backend flow**:
1. SentenceTransformer generates 384-dim embedding from query text
2. SQL: `SELECT * FROM restaurants WHERE ... ORDER BY embedding <=> query_embedding LIMIT 20`
3. pgvector computes cosine similarity (smaller `<=>` = more similar)
4. Returns restaurant cards with similarity scores

**Frontend display**: Grid of cards with ratings, reviews, categories, similarity scores

---

### Example 2: Side-by-Side Comparison

**Actions**:
1. Search "pizza in SF"
2. Click 3 restaurant cards (they highlight)
3. Click "Compare" button in floating bar

**Backend flow** (`POST /api/compare`):
1. Fetch full details for 3 restaurants
2. Generate KPIs: highest_rated, most_popular, avg_rating, price_range
3. Generate text: "Among these, [X] has highest rating (4.7), [Y] most reviews (450)..."
4. Return JSON with restaurants, kpis, insights

**Frontend display**: KPI cards, text summary, side-by-side table

---

### Example 3: Scored Recommendations

**Input**: "Recommend romantic dinner spots"

**Backend flow** (`POST /api/recommend`):
1. Extract preferences: cuisines=["Italian", "French"], ambiance="romantic"
2. Search matching restaurants
3. Score each with 4-factor formula:
   * rating_score = (4.5 / 5.0) × 100 = 90%
   * popularity_score = log(230) / log(max_reviews) × 100 = 82%
   * cuisine_match_score = 100% (exact match)
   * price_match_score = 70% (within budget)
   * **total_score** = 0.35×90 + 0.25×82 + 0.30×100 + 0.10×70 = 85.5%
4. Sort by total_score descending, return top 3

**Frontend display**: 🥇/🥈/🥉 medals, score percentages, factor breakdown, evidence

---

## 📚 Documentation

* `README.md`: This file (setup, API reference, architecture)
* `app/app.yaml`: Databricks Apps configuration
* `app/app.py`: Flask routes with inline docstrings

## 🐛 Known Limitations

1. **Static data**: Restaurants/reviews ingested once daily, not live from Yelp
2. **US-centric**: Yelp Fusion API optimized for US locations
3. **5-restaurant Q&A cap**: `/api/ask` accepts maximum 5 restaurant_ids
4. **No auth**: Single-user mode (user_id='anonymous'). Multi-user needs Databricks auth header
5. **Review lag**: Q&A answers only from reviews in `review_embeddings` table

---

## 📜 License

MIT License - feel free to use for learning and reference.

---

## 📊 Project Stats

* **Stack**: Flask + vanilla JS + Lakebase Postgres
* **API**: 17 REST endpoints (Flask) + 17 MCP tools (Python)
* **Tables**: 7 (restaurants, restaurant_embeddings, review_embeddings, restaurant_notes, favorites, meal_plans, user_preferences)
* **Embeddings**: SentenceTransformer all-MiniLM-L6-v2 (384-dim)
* **Vector search**: pgvector `<=>` operator (cosine similarity)
* **LLM**: Databricks Foundation Models API (Meta Llama 3.1 70B)
* **Scoring**: 4-factor weighted sum (rating 35%, popularity 25%, cuisine 30%, price 10%)
* **Deployment**: Databricks Apps V2 (container runtime)

---