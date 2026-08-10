# 🍽️ AI Restaurant & Food Planner

> *Intelligent restaurant discovery with semantic search, powered by Lakebase Postgres, pgvector cosine similarity, and transparent AI scoring on Databricks*

[![Databricks](https://img.shields.io/badge/Databricks-Apps%20V2-FF3621?logo=databricks)](https://www.databricks.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Web%20App-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Lakebase](https://img.shields.io/badge/Lakebase-Postgres-336791?logo=postgresql&logoColor=white)](https://www.databricks.com/product/lakebase)

## Overview

The **AI Restaurant & Food Planner** is a modern web application built on Databricks that helps users discover and compare restaurants through an intuitive interface. This project demonstrates:

* **Modern web UI** with Flask backend and responsive frontend design
* **Semantic search** using pgvector cosine similarity for intelligent restaurant discovery
* **Daily data ingestion** from Yelp API into Lakebase Postgres with vector embeddings
* **Review-based Q&A** powered by Databricks Foundation Models for insights
* **Intelligent comparison** with AI-generated analysis
* **Transparent AI recommendations** with explainable multi-factor scoring
* **Lakebase Postgres** for restaurant data, reviews, and embeddings
* **Databricks Apps V2** deployment with secret management

## 🎯 Key Features

### 🍽️ Modern Web Interface
* **Contemporary design** with vibrant red color scheme
* **Single unified section** with three tabs: Search, Recommend, Compare
* **Responsive layout** optimized for desktop and mobile
* **Real-time updates** with smooth animations and transitions
* **Click-to-select** restaurants with visual feedback
* **Floating action bar** for quick comparison access

### 🔍 Smart Restaurant Search
* **Semantic search** using pgvector cosine similarity on restaurant embeddings
* **Natural language queries** - search for "romantic Italian with outdoor seating"
* **Daily data refresh** from Yelp API ingestion job into Lakebase Postgres
* **Rich restaurant cards** with ratings, reviews, categories, and similarity scores
* **Interactive selection** - click any card to select for questions
* **Ask questions** about selected restaurants using their reviews with Foundation Models
* **Real-time KPIs**: Total restaurants, average rating, price range, top category

### ⚖️ Intelligent Comparison
* **Select 2-5 restaurants** by clicking cards
* **AI-generated analysis** with contextual insights:
  * Identifies highest-rated and most popular options
  * Analyzes rating patterns and price diversity
  * Highlights cuisine variety across selections
* **Visual KPI cards**: Highest Rated, Most Popular, Average Rating, Price Range
* **Detailed comparison table** with ratings, reviews, prices, and categories
* **Floating compare bar** shows selection count and quick actions

### 🎯 AI-Powered Recommendations

**Top 3 Personalized Picks** with premium visual design:
* 🥇 Gold medal for #1 recommendation with special highlighting
* 🥈 Silver and 🥉 Bronze medals for #2 and #3
* Large, prominent score display with gradient styling
* Enhanced card design with hover effects and top accent bars

**Multi-Factor Transparent Scoring**:

1. **Rating** (35%) - Yelp star rating quality indicator
2. **Popularity** (25%) - Review count as social proof
3. **Cuisine Match** (30%) - Alignment with user preferences
4. **Price Match** (10%) - Budget compatibility

**Explainable Results**: Every recommendation includes:
* Total score percentage (0-100%) displayed prominently
* Factor-by-factor breakdown in clean grid layout
* Evidence list explaining why each restaurant was picked
* Ranked by relevance with medal indicators

## 🔮 Future Scope

The following features are planned for future releases:

### 👥 User & Group Favorites
* **Personal favorites** - Save and organize favorite restaurants
* **Group favorites** - Create shared lists with friends and family
* **Collaborative planning** - Group members can vote on dining options
* **Social recommendations** - Get suggestions based on group preferences
* **Shared dining history** - Track restaurants visited together

### 🎯 Enhanced Personalization
* **Dietary restrictions** - Filter by vegetarian, vegan, gluten-free, etc.
* **Cuisine preferences** - Learn from past searches and selections
* **Budget tracking** - Set and monitor dining budgets
* **Visit history** - Remember restaurants you've tried

### 📊 Advanced Analytics
* **Spending insights** - Track dining expenses over time
* **Cuisine diversity** - Visualize eating patterns
* **Group activity** - See most active members and popular picks
* **Recommendation accuracy** - Learn which factors matter most to you

### 🔔 Notifications & Reminders
* **New restaurant alerts** - Get notified about openings in favorite areas
* **Price changes** - Track updates to restaurant pricing
* **Special events** - Be informed about restaurant promotions
* **Dining reminders** - Schedule and coordinate group dinners

*Note: The backend `/api/favorites` endpoint is already implemented and ready for integration once the frontend features are developed.*

## 🏛️ Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    USER BROWSER                               │
│                                                               │
│     ┌─────────────────────────────────────────┐             │
│     │   Frontend (HTML + JavaScript)          │             │
│     │   - Modern responsive UI                │             │
│     │   - Tabbed interface (Search/Recommend/ │             │
│     │     Compare)                            │             │
│     │   - Interactive restaurant cards        │             │
│     │   - Real-time KPI updates               │             │
│     └───────────────┬─────────────────────────┘             │
│                     │                                         │
│                     │ HTTPS (AJAX Requests)                  │
│                     v                                         │
└─────────────────────────────────────────────────────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────────────┐
│              DATABRICKS APP (Flask Backend)                   │
│                                                               │
│     ┌─────────────────────────────────────────┐             │
│     │   Flask Routes (app/app.py)             │             │
│     │   - /api/search         (semantic)      │             │
│     │   - /api/compare        (2-5 IDs)       │             │
│     │   - /api/recommend      (AI scoring)    │             │
│     │   - /api/details        (single ID)     │             │
│     │   - /api/ask            (review Q&A)    │             │
│     │   - /api/favorites      (user prefs)    │             │
│     └───────────┬──────────────┬──────────────┘             │
│                 │              │                              │
└─────────────────┼──────────────┼──────────────────────────────┘
                  │              │
        ┌─────────┴──────┐   ┌───┴──────────┐
        │                │   │              │
        v                v   v              v
┌────────────┐   ┌──────────────┐   ┌──────────────┐
│ Lakebase   │   │ Scoring      │   │ Foundation   │
│ Postgres   │   │ Engine       │   │ Models       │
│            │   │              │   │              │
│ - Restau-  │   │ Multi-factor │   │ - Review Q&A │
│   rants    │   │ scoring:     │   │ - LLaMA 3.1  │
│ - Reviews  │   │   • Rating   │   │   70B        │
│ - pgvector │   │   • Popular  │   │              │
│   embed-   │   │   • Cuisine  │   │              │
│   dings    │   │   • Price    │   │              │
│            │   │              │   │              │
│ Cosine     │   │ - Evidence   │   │              │
│ similarity │   │   generation │   │              │
└────────────┘   └──────────────┘   └──────────────┘
```

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

### 6. `GET/POST /api/favorites`

**User favorites management** (future implementation with Lakebase).

**GET**: Retrieve user's favorite restaurants
**POST**: Add/remove restaurants from favorites

*Note: Endpoint structure is ready; Lakebase integration is in future scope.*

---

## 🚀 Quick Start

### Prerequisites

* **Databricks workspace** with Apps V2 enabled
* **Yelp Fusion API key** - [Get one here](https://www.yelp.com/developers/v3/manage_app) (Free tier: 5000 requests/day)
* **Python 3.11+** runtime
* **Flask** and dependencies (see `requirements.txt`)

### Step 1: Get Yelp Fusion API Key

1. Go to [Yelp Fusion](https://www.yelp.com/developers/v3/manage_app)
2. Create a new app (provide name + description)
3. Copy your **API Key** (looks like: `AbCdEf123...`)
4. **Authentication**: Bearer token in `Authorization` header
   ```bash
   Authorization: Bearer YOUR_API_KEY
   ```
5. **Rate limits**: 5000 requests/day (free tier)

### Step 2: Set Up Lakebase Postgres

**Lakebase is now integrated** for restaurant data, reviews, and vector embeddings:

1. Create Lakebase database for restaurant data:
   - `restaurants` table: Core restaurant information
   - `restaurant_embeddings` table: pgvector embeddings for semantic search
   - `review_embeddings` table: Review text with embeddings

2. Run data ingestion notebooks:
   - `notebooks/ingest_restaurants_embeddings`: Fetches from Yelp API and generates 384-dim embeddings using SentenceTransformer
   - `notebooks/ingest_reviews_embeddings`: Ingests reviews with embeddings into `review_embeddings` table

3. Configure Lakebase connection in Databricks Secrets:
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

**Application Features**:
* 🔍 **Search Tab** - Find restaurants by location, cuisine, and filters
* 🎯 **Recommend Tab** - Get AI-powered suggestions based on preferences
* ⚖️ **Compare Tab** - Select and compare 2-5 restaurants side-by-side
* 💡 **Real-time KPIs** - View statistics and insights
* 📊 **Visual Scoring** - See transparent AI recommendation factors

---

### Step 5: Test the Application

**Test Search**:
1. Navigate to Search tab
2. Enter location: "San Francisco, CA"
3. Optional: Add cuisine (e.g., "Italian") or keywords
4. Click Search
5. View results with ratings, reviews, and categories

**Test Comparison**:
1. Search for restaurants
2. Click on 2-5 restaurant cards to select them
3. Click "Compare" in the floating action bar
4. View AI-generated insights and side-by-side table

**Test Recommendations**:
1. Navigate to Recommend tab
2. Enter location and preferences
3. Click Get Recommendations
4. View ranked results with score breakdowns and evidence

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

### Example 1: Search for Italian Restaurants

**Steps**:
1. Navigate to **Search** tab
2. Enter location: "San Francisco, CA"
3. Enter cuisine: "Italian"
4. Select price filter: "$"
5. Toggle "Open Now" if needed
6. Click **Search**

**Result**: Grid of Italian restaurants with ratings, reviews, categories, and interactive selection

---

### Example 2: Compare Top-Rated Options

**Steps**:
1. Search for restaurants (any criteria)
2. Click on 3-4 restaurant cards to select them
3. Floating compare bar appears showing selection count
4. Click **Compare** button
5. View AI-generated insights and comparison table

**Result**: 
* KPI cards showing highest rated, most popular, averages
* Natural language summary highlighting key differences
* Side-by-side table with ratings, reviews, prices, categories
* Clear identification of best options for different criteria

---

### Example 3: Get AI Recommendations

**Steps**:
1. Navigate to **Recommend** tab
2. Enter location: "Seattle, WA"
3. Select cuisines: "Italian", "French"
4. Set max price: "$"
5. Set min rating: 4.0
6. Click **Get Recommendations**

**Result**: Top 3 personalized picks displayed as premium cards:
* 🥇 Gold medal winner with special gold border
* 🥈 Silver and 🥉 bronze for #2 and #3
* Large prominent score percentages with gradient styling
* Factor breakdown in clean grid: rating, popularity, cuisine match, price match
* Evidence explaining why each restaurant was selected
* Enhanced card design with hover effects and smooth animations

---

## 📚 Documentation

* **This README**: Comprehensive guide covering setup, deployment, API reference, and usage
* **app.yaml**: Databricks App configuration (in `/app` directory)
* **In-code documentation**: Flask routes and functions include docstrings

## 🐛 Known Limitations

1. **Daily Data Refresh**: Restaurant data updated once daily via ingestion job (not real-time)
2. **User Favorites**: Backend endpoint exists but frontend integration not yet implemented
3. **Geographic Scope**: Optimized for US locations (Yelp Fusion API constraint)
4. **Selection Limit**: Maximum 5 restaurants can be selected for questions at once
5. **No Authentication**: Single-user mode; multi-user features require auth implementation
6. **Review Coverage**: Q&A limited to reviews already ingested in Lakebase

---

## 📜 License

MIT License - feel free to use for learning and reference.

---

## 📊 Project Stats

* **Architecture**: Flask web application with REST API and Lakebase backend
* **Frontend**: Single-page app with vanilla JavaScript
* **Backend**: Python Flask with 6 API endpoints
* **Data Layer**: Lakebase Postgres with pgvector extension for cosine similarity semantic search
* **AI Models**: SentenceTransformer (embeddings), Databricks Foundation Models (Q&A)
* **Scoring Factors**: 4 (rating, popularity, cuisine match, price match)
* **Deployment**: Databricks Apps V2
* **UI Components**: Tabbed interface, interactive cards, comparison table, Q&A modal, KPI dashboard
* **Design**: Modern responsive design with vibrant color scheme

---