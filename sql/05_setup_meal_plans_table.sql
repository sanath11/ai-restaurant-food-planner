-- Setup script for meal_plans table
-- Run this after creating restaurants table
-- Stores user meal planning for restaurant visits

-- Drop existing table if it exists (to ensure clean schema)
DROP TABLE IF EXISTS meal_plans CASCADE;

-- Create meal plans table
CREATE TABLE IF NOT EXISTS meal_plans (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    plan_name TEXT NOT NULL,
    description TEXT,
    restaurant_ids TEXT[] NOT NULL,  -- Array of restaurant IDs
    date DATE,  -- Optional date for the meal plan
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_meal_plans_user_id ON meal_plans(user_id);
CREATE INDEX IF NOT EXISTS idx_meal_plans_date ON meal_plans(date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_meal_plans_created_at ON meal_plans(created_at DESC);

-- GIN index for array search (find plans containing specific restaurant)
CREATE INDEX IF NOT EXISTS idx_meal_plans_restaurant_ids ON meal_plans USING GIN(restaurant_ids);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_meal_plans_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to call the function before UPDATE
DROP TRIGGER IF EXISTS update_meal_plans_timestamp ON meal_plans;
CREATE TRIGGER update_meal_plans_timestamp
BEFORE UPDATE ON meal_plans
FOR EACH ROW
EXECUTE FUNCTION update_meal_plans_updated_at();

-- Verify table structure
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'meal_plans'
ORDER BY ordinal_position;
