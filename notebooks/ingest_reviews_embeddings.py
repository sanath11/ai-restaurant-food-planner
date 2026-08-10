# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Review Ingestion Pipeline Overview
# MAGIC %md
# MAGIC # Restaurant Reviews Data Ingestion & Embeddings Pipeline
# MAGIC
# MAGIC This notebook fetches restaurant reviews from the Yelp Fusion API, stores them in Lakebase (Postgres), and computes semantic embeddings for intelligent search.
# MAGIC
# MAGIC ## Pipeline Steps
# MAGIC
# MAGIC 1. **Load Restaurants** - Get restaurant IDs from the restaurants table
# MAGIC 2. **Fetch Reviews** - Retrieve reviews from Yelp API for each restaurant
# MAGIC 3. **Store** - Insert reviews into Lakebase
# MAGIC 4. **Embed** - Compute semantic embeddings using sentence-transformers
# MAGIC 5. **Index** - Store embeddings in pgvector-enabled table for similarity search
# MAGIC
# MAGIC ## Configuration
# MAGIC
# MAGIC Use the widgets below to configure:
# MAGIC - **Yelp API credentials** - Databricks secret scope and key
# MAGIC - **Lakebase connection** - Secret containing connection string
# MAGIC - **Embedding model** - HuggingFace model for semantic embeddings
# MAGIC - **Reviews per restaurant** - Number of reviews to fetch per restaurant (max 3 per Yelp API)

# COMMAND ----------

# DBTITLE 1,Install Dependencies
# MAGIC %pip uninstall -y psycopg2 psycopg2-binary
# MAGIC %pip install -q 'databricks-sdk>=0.118.0' sentence-transformers trafilatura requests pandas
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

pip install sentence-transformers trafilatura requests pandas

# COMMAND ----------

# DBTITLE 1,Configuration Widgets
# Create input widgets for pipeline configuration
dbutils.widgets.text("yelp_secret_scope", "restaurant-app", "Yelp API Secret Scope")
dbutils.widgets.text("yelp_secret_key", "yelp-api-key", "Yelp API Secret Key")
dbutils.widgets.text("lakebase_secret_scope", "restaurant-app", "Lakebase Secret Scope")
dbutils.widgets.text("lakebase_secret_key", "lakebase-url", "Lakebase Secret Key")
dbutils.widgets.text("embedding_model", "sentence-transformers/all-MiniLM-L6-v2", "Embedding Model")
dbutils.widgets.text("batch_size", "50", "Restaurants per batch")

# Read widget values
yelp_secret_scope = dbutils.widgets.get("yelp_secret_scope")
yelp_secret_key = dbutils.widgets.get("yelp_secret_key")
lakebase_secret_scope = dbutils.widgets.get("lakebase_secret_scope")
lakebase_secret_key = dbutils.widgets.get("lakebase_secret_key")
embedding_model_name = dbutils.widgets.get("embedding_model")
batch_size = int(dbutils.widgets.get("batch_size"))

print(f"🔑 Yelp secrets: {yelp_secret_scope}/{yelp_secret_key}")
print(f"🗄️  Lakebase secrets: {lakebase_secret_scope}/{lakebase_secret_key}")
print(f"🤖 Embedding model: {embedding_model_name}")
print(f"📦 Batch size: {batch_size}")

# COMMAND ----------

# DBTITLE 1,Parse Lakebase Connection
from urllib.parse import urlparse

# Retrieve connection string from Databricks secrets
connection_string = dbutils.secrets.get(scope=lakebase_secret_scope, key=lakebase_secret_key)

# Parse connection string (format: postgresql://user:pass@host:port/database)
parsed = urlparse(connection_string)

if parsed.scheme != 'postgresql':
    raise ValueError(f"Invalid scheme: {parsed.scheme}. Expected: postgresql")

db_config = {
    'host': parsed.hostname,
    'port': parsed.port or 5432,
    'database': parsed.path.lstrip('/'),
    'user': parsed.username,
    'password': parsed.password
}

print(f"✅ Parsed connection to {db_config['user']}@{db_config['host']}:{db_config['port']}/{db_config['database']}")

# COMMAND ----------

# DBTITLE 1,Test Database Connection
import psycopg2

# Test connection and verify tables exist
with psycopg2.connect(**db_config) as conn:
    with conn.cursor() as cur:
        # Check if restaurants table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'restaurants'
            );
        """)
        restaurants_exists = cur.fetchone()[0]
        
        # Check if review_embeddings table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'review_embeddings'
            );
        """)
        embeddings_exists = cur.fetchone()[0]
        
        # Check if pgvector extension is installed
        cur.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector');")
        vector_exists = cur.fetchone()[0]
        
print(f"✅ Connection successful")
print(f"📊 restaurants table: {'✓' if restaurants_exists else '✗ MISSING'}")
print(f"🔢 review_embeddings table: {'✓' if embeddings_exists else '✗ MISSING'}")
print(f"📐 pgvector extension: {'✓' if vector_exists else '✗ MISSING'}")

if not (restaurants_exists and embeddings_exists and vector_exists):
    print("\n⚠️  Run sql/lakebase_schema.sql first to create required tables")

# COMMAND ----------

# DBTITLE 1,Load Restaurants Needing Reviews
import pandas as pd

# Load restaurants that don't have reviews embedded yet
query = """
    SELECT DISTINCT r.id, r.name, r.city, r.state, r.rating, r.review_count
    FROM restaurants r
    WHERE NOT EXISTS (
        SELECT 1 FROM review_embeddings re 
        WHERE re.restaurant_id = r.id
    )
    ORDER BY r.rating DESC, r.review_count DESC
    LIMIT %s;
"""

with psycopg2.connect(**db_config) as conn:
    df_restaurants = pd.read_sql_query(query, conn, params=(batch_size,))

print(f"📊 Loaded {len(df_restaurants)} restaurants to fetch reviews for")
if len(df_restaurants) > 0:
    display(df_restaurants.head())

# COMMAND ----------

# DBTITLE 1,Fetch Reviews from Yelp API
import requests
import time
from typing import List, Dict

# Get Yelp API key
yelp_api_key = dbutils.secrets.get(scope=yelp_secret_scope, key=yelp_secret_key)

def fetch_reviews_for_restaurant(restaurant_id: str, restaurant_name: str) -> List[Dict]:
    """Fetch reviews from Yelp API for a single restaurant."""
    url = f"https://api.yelp.com/v3/businesses/{restaurant_id}/reviews"
    headers = {"Authorization": f"Bearer {yelp_api_key}"}
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 429:  # Rate limit
            print(f"⏳ Rate limited, waiting 60s...")
            time.sleep(60)
            response = requests.get(url, headers=headers)
        
        if response.status_code == 404:
            print(f"⚠️  Restaurant not found: {restaurant_name}")
            return []
            
        response.raise_for_status()
        data = response.json()
        reviews = data.get("reviews", [])
        
        return reviews
    except Exception as e:
        print(f"❌ Error fetching reviews for {restaurant_name}: {e}")
        return []

# Fetch reviews for all restaurants
all_reviews = []
for idx, row in df_restaurants.iterrows():
    restaurant_id = row['id']
    restaurant_name = row['name']
    
    reviews = fetch_reviews_for_restaurant(restaurant_id, restaurant_name)
    
    for review in reviews:
        all_reviews.append({
            'restaurant_id': restaurant_id,
            'restaurant_name': restaurant_name,
            'review_text': review.get('text', ''),
            'rating': review.get('rating'),
            'time_created': review.get('time_created'),
            'user_name': review.get('user', {}).get('name')
        })
    
    if (idx + 1) % 10 == 0:
        print(f"  Fetched reviews for {idx + 1}/{len(df_restaurants)} restaurants")
    
    time.sleep(0.2)  # Rate limiting courtesy

print(f"\n📊 Total reviews fetched: {len(all_reviews)}")

# COMMAND ----------

# DBTITLE 1,Prepare Reviews DataFrame
# Convert to DataFrame
df_reviews = pd.DataFrame(all_reviews)

if len(df_reviews) > 0:
    # Filter out empty reviews
    df_reviews = df_reviews[df_reviews['review_text'].str.strip() != '']
    
    print(f"📝 Prepared {len(df_reviews)} reviews for embedding")
    print(f"📊 Average review length: {df_reviews['review_text'].str.len().mean():.0f} characters")
    display(df_reviews.head())
else:
    print("⚠️  No reviews to process")

# COMMAND ----------

# DBTITLE 1,Store Reviews Metadata in Reviews Table
if len(df_reviews) > 0:
    # Insert review metadata into reviews table
    with psycopg2.connect(**db_config) as conn:
        with conn.cursor() as cur:
            inserted = 0
            for _, row in df_reviews.iterrows():
                try:
                    cur.execute("""
                        INSERT INTO reviews (
                            restaurant_id, review_text, rating, time_created, user_name
                        ) VALUES (
                            %s, %s, %s, %s, %s
                        );
                    """, (
                        row['restaurant_id'],
                        row['review_text'],
                        row['rating'],
                        row['time_created'],
                        row['user_name']
                    ))
                    inserted += 1
                    
                    if inserted % 50 == 0:
                        print(f"  Inserted {inserted}/{len(df_reviews)} reviews")
                except Exception as e:
                    print(f"⚠️  Error inserting review metadata: {e}")
                    continue
            
            conn.commit()
            
            # Verify final count
            cur.execute("SELECT COUNT(*) FROM reviews;")
            total_reviews = cur.fetchone()[0]
    
    print(f"\n✅ Review metadata written to reviews table")
    print(f"📊 Total reviews in database: {total_reviews}")
else:
    print("ℹ️  No review metadata to write")

# COMMAND ----------

# DBTITLE 1,Compute Embeddings
from sentence_transformers import SentenceTransformer
import numpy as np

if len(df_reviews) == 0:
    print("✅ No reviews to embed")
else:
    # Load embedding model
    print(f"🤖 Loading model: {embedding_model_name}")
    model = SentenceTransformer(embedding_model_name)
    
    # Compute embeddings in batches
    print("🔢 Computing embeddings...")
    embedding_batch_size = 32
    embeddings = []
    
    for i in range(0, len(df_reviews), embedding_batch_size):
        batch = df_reviews['review_text'].iloc[i:i+embedding_batch_size].tolist()
        batch_embeddings = model.encode(batch, show_progress_bar=False)
        embeddings.extend(batch_embeddings)
        if (i + embedding_batch_size) % 100 == 0:
            print(f"  Processed {min(i + embedding_batch_size, len(df_reviews))}/{len(df_reviews)} embeddings")
    
    df_reviews['embedding'] = embeddings
    print(f"✅ Computed {len(embeddings)} embeddings (dimension: {len(embeddings[0])})")

# COMMAND ----------

# DBTITLE 1,Write Reviews and Embeddings to Lakebase
if len(df_reviews) > 0:
    # Insert review embeddings into database
    with psycopg2.connect(**db_config) as conn:
        with conn.cursor() as cur:
            inserted = 0
            for _, row in df_reviews.iterrows():
                try:
                    # Convert numpy array to list for vector type
                    embedding_list = row['embedding'].tolist()
                    
                    cur.execute("""
                        INSERT INTO review_embeddings (
                            restaurant_id, review_text, embedding
                        ) VALUES (
                            %s, %s, %s::vector
                        );
                    """, (
                        row['restaurant_id'],
                        row['review_text'],
                        embedding_list
                    ))
                    inserted += 1
                    
                    if inserted % 50 == 0:
                        print(f"  Inserted {inserted}/{len(df_reviews)} review embeddings")
                except Exception as e:
                    print(f"⚠️  Error inserting review: {e}")
                    continue
            
            conn.commit()
            
            # Verify final count
            cur.execute("SELECT COUNT(*) FROM review_embeddings;")
            total_embeddings = cur.fetchone()[0]
    
    print(f"\n✅ Review embeddings written to database")
    print(f"📊 Total review embeddings in database: {total_embeddings}")
else:
    print("ℹ️  No new review embeddings to write")

# COMMAND ----------

# DBTITLE 1,Pipeline Summary
# Final pipeline statistics
with psycopg2.connect(**db_config) as conn:
    with conn.cursor() as cur:
        # Restaurant count
        cur.execute("SELECT COUNT(*) FROM restaurants;")
        total_restaurants = cur.fetchone()[0]
        
        # Review embedding counts
        cur.execute("SELECT COUNT(*) FROM review_embeddings;")
        total_review_embeddings = cur.fetchone()[0]
        
        # Reviews per restaurant
        cur.execute("""
            SELECT 
                COUNT(DISTINCT restaurant_id) as restaurants_with_reviews,
                AVG(review_count) as avg_reviews_per_restaurant
            FROM (
                SELECT restaurant_id, COUNT(*) as review_count
                FROM review_embeddings
                GROUP BY restaurant_id
            ) subq;
        """)
        result = cur.fetchone()
        restaurants_with_reviews = result[0] or 0
        avg_reviews = result[1] or 0

print("="*60)
print("🎉 PIPELINE COMPLETE")
print("="*60)
print(f"📊 Total restaurants: {total_restaurants}")
print(f"📝 Restaurants with reviews: {restaurants_with_reviews}")
print(f"🔢 Total review embeddings: {total_review_embeddings}")
print(f"📈 Average reviews per restaurant: {avg_reviews:.1f}")
print(f"✅ Coverage: {(restaurants_with_reviews / total_restaurants * 100):.1f}%" if total_restaurants > 0 else "✅ Coverage: 0%")
print("="*60)

# COMMAND ----------

