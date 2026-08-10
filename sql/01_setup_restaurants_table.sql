-- Setup script for restaurants table
-- Run this manually in your Lakebase Postgres database before running the ingestion notebook

-- Create restaurants table to store Yelp business data
CREATE TABLE IF NOT EXISTS restaurants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    rating NUMERIC(2,1),
    review_count INTEGER,
    price TEXT,
    phone TEXT,
    categories JSONB,
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    address TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    country TEXT,
    distance NUMERIC(10,2),
    image_url TEXT,
    url TEXT,
    payload JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_restaurants_city ON restaurants (city);
CREATE INDEX IF NOT EXISTS idx_restaurants_rating ON restaurants (rating DESC);
CREATE INDEX IF NOT EXISTS idx_restaurants_location ON restaurants (latitude, longitude);

-- Verify table
SELECT 
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'restaurants'
ORDER BY ordinal_position;