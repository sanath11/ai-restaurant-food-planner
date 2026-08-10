-- Setup script for reviews table
-- Run this after creating restaurants table
-- Stores Yelp reviews for restaurants

-- Drop existing table if it exists (to ensure clean schema)
DROP TABLE IF EXISTS reviews CASCADE;

-- Create reviews table
CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    restaurant_id TEXT NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    user_name TEXT,
    user_profile_url TEXT,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    review_text TEXT,
    time_created TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_reviews_restaurant_id ON reviews(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_reviews_rating ON reviews(rating DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_time_created ON reviews(time_created DESC);

-- Composite index for common query pattern (restaurant + rating + time)
CREATE INDEX IF NOT EXISTS idx_reviews_restaurant_rating_time 
    ON reviews(restaurant_id, rating DESC, time_created DESC);

-- Verify table structure
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'reviews'
ORDER BY ordinal_position;
