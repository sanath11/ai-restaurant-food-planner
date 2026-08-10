# Lakebase SQL Schema

Database schema for the Restaurant Food Planner MCP Server.

## Files

Run in order:

1. **01_setup_restaurants_table.sql** - Main restaurants table with Yelp data
2. **02_setup_embeddings_table.sql** - Vector embeddings for semantic search (requires pgvector)
3. **03_add_idempotency_constraints.sql** - Idempotency constraints for data ingestion
4. **04_setup_favorites_table.sql** - User favorite restaurants
5. **05_setup_meal_plans_table.sql** - Meal planning with multiple restaurants
6. **06_setup_notes_table.sql** - Personal notes and observations about restaurants
7. **07_setup_preferences_table.sql** - User dining preferences and dietary restrictions
8. **08_setup_reviews_table.sql** - Restaurant reviews from Yelp

## Quick Setup

Run all schemas in order:

```bash
# From the sql/ directory
psql $LAKEBASE_URL -f 00_setup_all.sql
```

Or run individually:

```bash
psql $LAKEBASE_URL -f 01_setup_restaurants_table.sql
psql $LAKEBASE_URL -f 02_setup_embeddings_table.sql
psql $LAKEBASE_URL -f 03_add_idempotency_constraints.sql
psql $LAKEBASE_URL -f 04_setup_favorites_table.sql
psql $LAKEBASE_URL -f 05_setup_meal_plans_table.sql
psql $LAKEBASE_URL -f 06_setup_notes_table.sql
psql $LAKEBASE_URL -f 07_setup_preferences_table.sql
psql $LAKEBASE_URL -f 08_setup_reviews_table.sql
```

## Tables Overview

### Core Tables
- **restaurants** - Restaurant data from Yelp API
- **reviews** - Customer reviews for restaurants
- **restaurant_embeddings** - Vector embeddings for semantic search

### User Data Tables
- **user_favorites** - Saved favorite restaurants per user
- **meal_plans** - Multi-restaurant meal plans with dates
- **user_preferences** - Dietary restrictions and cuisine preferences
- **restaurant_notes** - Personal notes, ratings, and visit dates

## MCP Tools Supported

These schemas support all 18 MCP tools:

**Restaurant Discovery** (5 tools)
- search_restaurants
- semantic_restaurant_search
- get_restaurant_details
- compare_restaurants
- recommend_restaurant

**Personal Notes** (4 tools)
- save_restaurant_note
- get_restaurant_notes
- update_restaurant_note
- delete_restaurant_note

**Favorites** (3 tools)
- save_favorite
- get_favorites
- delete_favorite

**Meal Plans** (4 tools)
- create_meal_plan
- get_meal_plans
- update_meal_plan
- delete_meal_plan

**User Preferences** (2 tools)
- save_preferences
- get_preferences

## Patterns Followed

- Numbered files (01_, 02_, etc.) for execution order
- One table group per file
- Proper indexes for common queries
- Foreign keys with CASCADE for data integrity
- JSONB for flexible data (categories, preferences)
- Array types for multi-value fields (cuisines, tags, restaurant IDs)
- pgvector extension for semantic search
- Auto-updating timestamp triggers
- Verification queries at end of each file

## Requirements

- PostgreSQL 13+ (Lakebase Postgres)
- pgvector extension (for embeddings table)
- Sentence transformer model: all-MiniLM-L6-v2 (384 dimensions)

## Connection

Set your Lakebase connection URL:

```bash
export LAKEBASE_URL="postgresql://user:password@host:port/database"
```

Or retrieve from Databricks secrets:

```python
from secret_utils import get_secret
lakebase_url = get_secret(
    env_var_name="LAKEBASE_URL",
    secret_scope="restaurant-app",
    secret_key="lakebase-connection-url"
)
```
