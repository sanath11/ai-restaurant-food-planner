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

Flask backend with 17 REST endpoints.

### Search & Discovery

**`GET /api/search`** - Semantic search with pgvector cosine similarity

Query parameters: `location`, `cuisine`, `keyword`, `price_level`, `open_now`, `limit`

Returns restaurants with ratings, reviews, categories, plus KPIs (count, avg rating, price range, top category).

**`GET /api/details/<restaurant_id>`** - Single restaurant lookup

Returns full details: hours, photos, transactions.

**`POST /api/compare`** - Side-by-side comparison of 2-5 restaurants

Body: `{"restaurant_ids": [...]}`

Returns KPI cards (highest rated, most popular) and AI-generated insights (rating patterns, price diversity, cuisine variety).

**`POST /api/recommend`** - Multi-factor scored recommendations

Body: `{"location", "cuisines", "max_price", "min_rating", "limit"}`

Returns top 3 with transparent scoring:
* Rating 35%, Popularity 25%, Cuisine match 30%, Price match 10%
* Total score 0-100%, factor breakdown, evidence per restaurant

**`POST /api/ask`** - Review-based Q&A via Llama 3.1 70B

Body: `{"restaurant_ids": [...], "question": "..."}`

Retrieves reviews from `review_embeddings`, constructs context (max 5 reviews/restaurant), returns natural language answer.

### Favorites Management

**`GET /api/favorites/get`** - List saved restaurants

**`POST /api/favorites/save`** - Add to favorites

Body: `{"restaurant_id", "restaurant_name"}`

**`POST /api/favorites/remove`** - Remove from favorites

Body: `{"restaurant_id"}`

### Meal Planning

**`GET /api/meal-plans/get`** - List meal plans

**`POST /api/meal-plans/create`** - Create plan with restaurant array

Body: `{"plan_name", "description", "restaurant_ids": [...], "date"}`

**`POST /api/meal-plans/delete`** - Delete plan

Body: `{"plan_id"}`

### User Preferences

**`GET /api/preferences/get`** - Retrieve dining preferences

Returns: `preferred_cuisines`, `dietary_restrictions`, `budget_range`, `preferred_ambiance`

**`POST /api/preferences/save`** - Save or update preferences

### Personal Notes

**`GET /api/notes/get`** - List notes, optional filter by `restaurant_id`

**`POST /api/notes/create`** - Create note

Body: `{"restaurant_id", "note_text", "tags": [...], "personal_rating", "visit_date"}`

Tags stored as Postgres ARRAY. Personal rating 0-5, independent of Yelp.

**`POST /api/notes/update/<note_id>`** - Update note

**`POST /api/notes/delete/<note_id>`** - Delete note

---

## 🧑‍💻 MCP Tools Reference

MCP server (`mcp_server/restaurant_mcp_server.py`) with 17 tools for AI agents.

### Discovery

* `search_restaurants` - Semantic search (pgvector cosine similarity)
* `get_restaurant_details` - Single restaurant lookup
* `recommend_restaurant` - Multi-factor scoring (rating 35%, popularity 25%, cuisine 30%, price 10%)

### Notes

* `save_restaurant_note` - Create note (text, tags array, personal rating 0-5, visit date)
* `get_restaurant_notes` - List notes, optional filter by restaurant_id
* `update_restaurant_note` - Update note
* `delete_restaurant_note` - Delete note

### Review Q&A

* `ask_about_reviews` - Answer questions using Foundation Models (Llama 3.1 70B)

### Favorites

* `save_favorite` - Add restaurant to favorites
* `get_favorites` - List favorites
* `delete_favorite` - Remove from favorites

### Meal Plans

* `create_meal_plan` - Create plan with restaurant array
* `get_meal_plans` - List plans
* `update_meal_plan` - Update plan
* `delete_meal_plan` - Delete plan

### Preferences

* `save_preferences` - Save cuisines, dietary restrictions, budget, ambiance
* `get_preferences` - Retrieve saved preferences

### Database Schema

```sql
-- Notes with ARRAY tags
CREATE TABLE restaurant_notes (
    note_id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    restaurant_id TEXT NOT NULL,
    note_text TEXT NOT NULL,
    tags TEXT[],
    personal_rating NUMERIC(2, 1) CHECK (personal_rating >= 0 AND personal_rating <= 5),
    visit_date DATE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Favorites
CREATE TABLE favorites (
    user_id TEXT NOT NULL,
    restaurant_id TEXT NOT NULL,
    restaurant_name TEXT NOT NULL,
    saved_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, restaurant_id)
);

-- Meal plans with ARRAY
CREATE TABLE meal_plans (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    plan_name TEXT NOT NULL,
    description TEXT,
    restaurant_ids TEXT[],
    date DATE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Preferences
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
* Yelp Fusion API key (free tier: 5000 requests/day)

### 1. Yelp API Key

1. Create app at [Yelp Fusion](https://www.yelp.com/developers/v3/manage_app)
2. Copy API key
3. Authentication: Bearer token in `Authorization` header

### 2. Lakebase Postgres Setup

Create 7 tables: `restaurants`, `restaurant_embeddings`, `review_embeddings`, `restaurant_notes`, `favorites`, `meal_plans`, `user_preferences`.

Ingest data:
* `notebooks/ingest_restaurants_embeddings` - Yelp API → 384-dim SentenceTransformer embeddings
* `notebooks/ingest_reviews_embeddings` - Review text with embeddings

Store connection URL:
```bash
databricks secrets put-secret restaurant-app lakebase-connection-url
# Format: postgres://user:pass@host:port/database
```

### 3. Databricks Secrets

```bash
databricks secrets create-scope restaurant-app
databricks secrets put-secret restaurant-app yelp-api-key
```

### 4. Deploy App

```bash
cd app
databricks apps create ai-restaurant-planner --description "AI Restaurant Planner" --source-code-path ./
databricks apps deploy ai-restaurant-planner
databricks apps get ai-restaurant-planner  # Check status: RUNNING
```

Access: `https://<workspace>.cloud.databricks.com/apps/ai-restaurant-planner`

### 5. Verify

**Search**: Type "Italian restaurants in San Francisco" → restaurant cards appear

**Compare**: Select 2-5 cards → click "Compare" → KPIs + insights + table

**Recommend**: Type "romantic dinner spots" → top 3 with 🥇/🥈/🥉 medals

## 🛠️ Technical Deep Dive

### Yelp Fusion API

Base: `https://api.yelp.com/v3`

Endpoints:
* `GET /businesses/search` - Location, term, categories, price, open_now
* `GET /businesses/{id}` - Full details (hours, photos, transactions)
* `GET /businesses/{id}/reviews` - Up to 3 reviews per restaurant

Rate limits: 5,000 req/day (free), 25,000+ (paid)

Error handling: 429 → exponential backoff, 400 → validation hints, network → graceful degradation

### Scoring Engine

`mcp_server/recommendation_engine.py` - Weighted multi-factor scoring

**Formulas**:
* Rating: `(rating / 5.0) * 100` (linear)
* Popularity: `(log(reviews + 1) / log(max + 1)) * 100` (log-scaled)
* Cuisine: 100 if match, 0 otherwise
* Price: `100 - (abs(user_max - restaurant_price) * 33.3)`

**Weights**: Rating 35%, Popularity 25%, Cuisine 30%, Price 10%

Output: Total score 0-100%, factor breakdown, evidence array

### Comparison Analysis

`app/app.py` `/api/compare` endpoint

Generates insights:
* Highest-rated restaurant
* Most popular (review count)
* Price diversity (varied vs similar)
* Cuisine variety

Returns natural language summary with rating patterns, price range, cuisine diversity


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

* `README.md` - Setup, API reference, architecture
* `app/app.yaml` - Databricks Apps configuration
* `app/app.py` - Flask routes with docstrings

## 🐛 Known Limitations

1. **Static data** - Daily ingestion, not live from Yelp
2. **US-centric** - Yelp Fusion API optimized for US
3. **5-restaurant Q&A cap** - `/api/ask` maximum 5 IDs
4. **No auth** - Single-user mode (`user_id='anonymous'`)
5. **Review lag** - Q&A from `review_embeddings` table only

---

## 📜 License

MIT

---

## 📊 Project Stats

* Stack: Flask + vanilla JS + Lakebase Postgres
* API: 17 REST endpoints + 17 MCP tools
* Tables: 7 (restaurants, restaurant_embeddings, review_embeddings, restaurant_notes, favorites, meal_plans, user_preferences)
* Embeddings: SentenceTransformer all-MiniLM-L6-v2 (384-dim)
* Vector search: pgvector `<=>` cosine similarity
* LLM: Databricks Foundation Models (Llama 3.1 70B)
* Scoring: 4-factor weighted (rating 35%, popularity 25%, cuisine 30%, price 10%)
* Deployment: Databricks Apps V2

---