-- Setup script for restaurant_embeddings table
-- Run this manually in your Lakebase Postgres database after creating restaurants table
-- Replace {{EMBEDDING_DIM}} with 384 for sentence-transformers/all-MiniLM-L6-v2

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create restaurant embeddings table for semantic search
-- IMPORTANT: Replace {{EMBEDDING_DIM}} below with 384 for all-MiniLM-L6-v2
CREATE TABLE IF NOT EXISTS restaurant_embeddings (
    id TEXT PRIMARY KEY REFERENCES restaurants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    categories TEXT,
    embedding VECTOR({{EMBEDDING_DIM}}) NOT NULL,
    model_name TEXT NOT NULL,
    embedded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_restaurant_embeddings_embedding
ON restaurant_embeddings
USING hnsw (embedding vector_cosine_ops);

-- Create reviews table for storing review metadata
CREATE TABLE IF NOT EXISTS reviews (
    review_id SERIAL PRIMARY KEY,
    restaurant_id TEXT NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    review_text TEXT NOT NULL,
    rating NUMERIC(2, 1),
    time_created TIMESTAMPTZ,
    user_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reviews_restaurant_id ON reviews(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_reviews_rating ON reviews(rating);
CREATE INDEX IF NOT EXISTS idx_reviews_time_created ON reviews(time_created);

-- Create review embeddings table for semantic search over reviews
CREATE TABLE IF NOT EXISTS review_embeddings (
    embedding_id SERIAL PRIMARY KEY,
    restaurant_id TEXT NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    review_text TEXT NOT NULL,
    embedding VECTOR({{EMBEDDING_DIM}}) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_embeddings_embedding
ON review_embeddings
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_review_embeddings_restaurant_id ON review_embeddings(restaurant_id);

-- Verify tables
SELECT 
    table_name,
    column_name,
    data_type,
    udt_name
FROM information_schema.columns
WHERE table_name IN ('restaurant_embeddings', 'reviews', 'review_embeddings')
ORDER BY table_name, ordinal_position;