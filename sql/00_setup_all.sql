-- Master setup script - runs all table creation scripts in order
-- Run this with: psql $LAKEBASE_URL -f 00_setup_all.sql

\echo '========================================='
\echo 'Restaurant Food Planner - Database Setup'
\echo '========================================='
\echo ''

\echo 'Step 1/8: Creating restaurants table...'
\i 01_setup_restaurants_table.sql
\echo ''

\echo 'Step 2/8: Creating embeddings table (requires pgvector)...'
\i 02_setup_embeddings_table.sql
\echo ''

\echo 'Step 3/8: Adding idempotency constraints...'
\i 03_add_idempotency_constraints.sql
\echo ''

\echo 'Step 4/8: Creating user favorites table...'
\i 04_setup_favorites_table.sql
\echo ''

\echo 'Step 5/8: Creating meal plans table...'
\i 05_setup_meal_plans_table.sql
\echo ''

\echo 'Step 6/8: Creating restaurant notes table...'
\i 06_setup_notes_table.sql
\echo ''

\echo 'Step 7/8: Creating user preferences table...'
\i 07_setup_preferences_table.sql
\echo ''

\echo 'Step 8/8: Creating reviews table...'
\i 08_setup_reviews_table.sql
\echo ''

\echo '========================================='
\echo 'Setup Complete!'
\echo '========================================='
\echo ''
\echo 'All tables created successfully.'
\echo 'You can now run the MCP server with all 18 tools.'
\echo ''
