-- Setup script for favorites table
-- Run this after creating restaurants table
-- Stores user favorite restaurants

-- Drop existing table if it exists (to ensure clean schema)
DROP TABLE IF EXISTS favorites CASCADE;

-- Create favorites table
CREATE TABLE IF NOT EXISTS favorites (
    user_id TEXT NOT NULL,
    restaurant_id TEXT NOT NULL,
    restaurant_name TEXT NOT NULL,  -- Cached restaurant name for quick display
    saved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- One favorite per user per restaurant
    PRIMARY KEY (user_id, restaurant_id)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_restaurant_id ON favorites(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_favorites_saved_at ON favorites(saved_at DESC);

-- Verify table structure
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'favorites'
ORDER BY ordinal_position;
