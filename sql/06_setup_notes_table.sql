-- Setup script for restaurant_notes table
-- Run this after creating restaurants table
-- Stores user notes and personal observations about restaurants

-- Drop existing table if it exists (to ensure clean schema)
DROP TABLE IF EXISTS restaurant_notes CASCADE;

-- Create restaurant notes table
CREATE TABLE IF NOT EXISTS restaurant_notes (
    note_id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    restaurant_id TEXT NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    note_text TEXT NOT NULL,
    tags TEXT[],  -- Optional tags like ['favorite', 'vegetarian-friendly', 'good-service']
    personal_rating NUMERIC(2, 1),  -- Optional personal rating (0-5)
    visit_date DATE,  -- Optional date of visit
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Prevent duplicate notes from same user for same restaurant at same time
    UNIQUE (user_id, restaurant_id, created_at)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_notes_user_id ON restaurant_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_notes_restaurant_id ON restaurant_notes(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_notes_user_restaurant ON restaurant_notes(user_id, restaurant_id);
CREATE INDEX IF NOT EXISTS idx_notes_created_at ON restaurant_notes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notes_tags ON restaurant_notes USING GIN(tags);  -- GIN index for array search

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_notes_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to call the function before UPDATE
DROP TRIGGER IF EXISTS update_notes_timestamp ON restaurant_notes;
CREATE TRIGGER update_notes_timestamp
BEFORE UPDATE ON restaurant_notes
FOR EACH ROW
EXECUTE FUNCTION update_notes_updated_at();

-- Verify table structure
SELECT 
    table_name,
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'restaurant_notes'
ORDER BY ordinal_position;
