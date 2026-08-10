# Lakebase SQL Schema

Numbered SQL files following reference pattern from `databricks-lakebase-app-day-2`.

## Files

Run in order:

1. **01_setup_restaurants_table.sql** - Main restaurants table with Yelp data
2. **02_setup_embeddings_table.sql** - Vector embeddings for semantic search (requires pgvector)
3. **03_setup_user_tables.sql** - Users, preferences, and saved restaurants
4. **04_setup_dining_plan_tables.sql** - Dining plans and plan items
5. **05_setup_query_log_tables.sql** - Agent query logs and weather snapshots

## Setup

Replace placeholders:
- `{{EMBEDDING_DIM}}` → `384` (for sentence-transformers/all-MiniLM-L6-v2)

## Reference

Based on: `/Users/sanath.sanath.11@gmail.com/databricks-lakebase-app-day-2/sql/`

## Patterns Followed

- Numbered files (01_, 02_, etc.)
- One table group per file
- Proper indexes for common queries
- Foreign keys with CASCADE
- JSONB for flexible data (categories, preferences)
- pgvector extension for semantic search
- Verification queries at end of each file
