-- Setup script for user_preferences table
-- Run this after creating restaurants table
-- Stores user dining preferences and dietary restrictions

-- Drop existing table if it exists (to ensure clean schema)
DROP TABLE IF EXISTS user_preferences CASCADE;

-- Create user preferences table
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT PRIMARY KEY,
    preferred_cuisines TEXT,      -- Comma-separated list: "Italian, Japanese, Thai, Mexican"
    dietary_restrictions TEXT,    -- Comma-separated list: "Vegetarian, Gluten-free, Nut allergy"
    budget_range TEXT,            -- "$", "$", "$", "$"
    preferred_ambiance TEXT,      -- "Casual, Romantic, Family-friendly"
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_preferences_user_id ON user_preferences(user_id);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_preferences_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to call the function before UPDATE
DROP TRIGGER IF EXISTS update_preferences_timestamp ON user_preferences;
CREATE TRIGGER update_preferences_timestamp
BEFORE UPDATE ON user_preferences
FOR EACH ROW
EXECUTE FUNCTION update_preferences_updated_at();

-- Verify table structure
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'user_preferences'
ORDER BY ordinal_position;
