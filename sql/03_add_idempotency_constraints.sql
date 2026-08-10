-- Migration script to add idempotency constraints to existing databases
-- Run this ONLY if your database was created before the idempotency fix
-- This prevents duplicate reviews and embeddings on pipeline reruns

-- Check if constraints already exist
DO $$
BEGIN
    -- Add unique constraint to reviews table if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'reviews_unique_review'
    ) THEN
        ALTER TABLE reviews 
            ADD CONSTRAINT reviews_unique_review 
            UNIQUE (restaurant_id, review_text);
        RAISE NOTICE 'Added unique constraint to reviews table';
    ELSE
        RAISE NOTICE 'Unique constraint already exists on reviews table';
    END IF;
    
    -- Add unique constraint to review_embeddings table if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'review_embeddings_unique_review'
    ) THEN
        ALTER TABLE review_embeddings 
            ADD CONSTRAINT review_embeddings_unique_review 
            UNIQUE (restaurant_id, review_text);
        RAISE NOTICE 'Added unique constraint to review_embeddings table';
    ELSE
        RAISE NOTICE 'Unique constraint already exists on review_embeddings table';
    END IF;
END $$;

-- Verify constraints were added
SELECT 
    conname AS constraint_name,
    conrelid::regclass AS table_name,
    pg_get_constraintdef(oid) AS constraint_definition
FROM pg_constraint
WHERE conname IN ('reviews_unique_review', 'review_embeddings_unique_review')
ORDER BY table_name;