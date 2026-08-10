# Shared Module Directory

This directory contains shared modules used across multiple components of the AI Restaurant Food Planner application.

## Purpose

Previously, duplicate implementations of `lakebase_client.py` existed in both `app/` and `mcp_server/` directories, leading to:
- **Conflicting method signatures** (e.g., `get_restaurant_by_id` expected `int` in app vs `str` in mcp_server)
- **Inconsistent connection handling** (mcp_server had auto-reconnect, app didn't)
- **Runtime errors** depending on which version was imported

## Solution

The canonical implementation is now maintained in `shared/lakebase_client.py` with:
- ✅ **Correct type signatures** matching the database schema (`id TEXT PRIMARY KEY`)
- ✅ **Robust auto-reconnect logic** for connection resilience
- ✅ **Comprehensive error handling**
- ✅ **Single source of truth** - no more conflicts

## Usage

Both `app/app.py` and `mcp_server/restaurant_mcp_server.py` now import from the shared module:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.lakebase_client import LakebaseClient
```

## Key Methods

### Restaurant Queries
- `search_restaurants_by_location(location, categories, min_rating, max_price_level, limit)` - Location-based search
- `semantic_search_restaurants(query_embedding, min_rating, max_price_level, limit)` - Vector similarity search
- `get_restaurant_by_id(restaurant_id: str)` - Get details by Yelp ID (string)
- `get_restaurant_reviews(restaurant_id: str, limit)` - Fetch reviews

### User Data
- `save_favorite(user_id, restaurant_id, notes)` - Save to favorites
- `remove_favorite(user_id, restaurant_id)` - Remove from favorites
- `get_user_favorites(user_id)` - List favorites
- `create_meal_plan(user_id, plan_name, restaurant_ids, description, date)` - Create meal plan
- `get_user_meal_plans(user_id)` - List meal plans
- `update_meal_plan(plan_id, ...)` - Update meal plan

## Database Schema Alignment

The implementation matches the Lakebase Postgres schema defined in `sql/01_setup_restaurants_table.sql`:
- Restaurant IDs are **TEXT** (Yelp IDs like "xyz123"), not integers
- All method signatures reflect this correctly

## Maintenance

⚠️ **Important**: Always update this shared version. Do NOT create duplicate implementations in other directories.