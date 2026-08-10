# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Restaurant Ingestion Pipeline Overview
# MAGIC %md
# MAGIC # Restaurant Data Ingestion & Embeddings Pipeline
# MAGIC
# MAGIC This notebook fetches restaurant data from the Yelp Fusion API, stores it in Lakebase (Postgres), and computes semantic embeddings for intelligent search.
# MAGIC
# MAGIC ## Pipeline Steps
# MAGIC
# MAGIC 1. **Fetch** - Retrieve restaurant data from Yelp API for specified locations
# MAGIC 2. **Store** - Upsert restaurants into Lakebase with deduplication
# MAGIC 3. **Embed** - Compute semantic embeddings using sentence-transformers
# MAGIC 4. **Index** - Store embeddings in pgvector-enabled table for similarity search
# MAGIC
# MAGIC ## Configuration
# MAGIC
# MAGIC Use the widgets below to configure:
# MAGIC - **Locations** - Comma-separated cities to fetch restaurants for
# MAGIC - **Yelp API credentials** - Databricks secret scope and key
# MAGIC - **Lakebase connection** - Secret containing connection string
# MAGIC - **Embedding model** - HuggingFace model for semantic embeddings

# COMMAND ----------

# DBTITLE 1,Install Dependencies
# MAGIC %pip uninstall -y psycopg2 psycopg2-binary
# MAGIC %pip install -q 'databricks-sdk>=0.118.0' sentence-transformers trafilatura requests pandas
# MAGIC dbutils.library.restartPython()
# MAGIC

# COMMAND ----------

# DBTITLE 1,Configuration Widgets
# Create input widgets for pipeline configuration
dbutils.widgets.text("locations", "New York, NY", "Locations to fetch (comma-separated)")
dbutils.widgets.text("yelp_secret_scope", "restaurant-app", "Yelp API Secret Scope")
dbutils.widgets.text("yelp_secret_key", "yelp-api-key", "Yelp API Secret Key")
dbutils.widgets.text("lakebase_secret_scope", "restaurant-app", "Lakebase Secret Scope")
dbutils.widgets.text("lakebase_secret_key", "lakebase-connection", "Lakebase Secret Key")
dbutils.widgets.text("embedding_model", "sentence-transformers/all-MiniLM-L6-v2", "Embedding Model")

# Read widget values
locations = [loc.strip() for loc in dbutils.widgets.get("locations").split(",")]
yelp_secret_scope = dbutils.widgets.get("yelp_secret_scope")
yelp_secret_key = dbutils.widgets.get("yelp_secret_key")
lakebase_secret_scope = dbutils.widgets.get("lakebase_secret_scope")
lakebase_secret_key = dbutils.widgets.get("lakebase_secret_key")
embedding_model_name = dbutils.widgets.get("embedding_model")

print(f"📍 Locations: {locations}")
print(f"🔑 Yelp secrets: {yelp_secret_scope}/{yelp_secret_key}")
print(f"🗄️  Lakebase secrets: {lakebase_secret_scope}/{lakebase_secret_key}")
print(f"🤖 Embedding model: {embedding_model_name}")

# COMMAND ----------

# DBTITLE 1,Parse Lakebase Connection
from urllib.parse import urlparse

# Retrieve connection string from Databricks secrets
connection_string = dbutils.secrets.get(scope="restaurant-app", key="lakebase-url")

# Parse connection string (format: postgresql://user:pass@host:port/database)
# Use urlparse to handle special characters in password
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
        
        # Check if restaurant_embeddings table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'restaurant_embeddings'
            );
        """)
        embeddings_exists = cur.fetchone()[0]
        
        # Check if pgvector extension is installed
        cur.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector');")
        vector_exists = cur.fetchone()[0]
        
print(f"✅ Connection successful")
print(f"📊 restaurants table: {'✓' if restaurants_exists else '✗ MISSING'}")
print(f"🔢 restaurant_embeddings table: {'✓' if embeddings_exists else '✗ MISSING'}")
print(f"📐 pgvector extension: {'✓' if vector_exists else '✗ MISSING'}")

if not (restaurants_exists and embeddings_exists and vector_exists):
    print("\n⚠️  Run sql/lakebase_schema.sql first to create required tables")

# COMMAND ----------

# DBTITLE 1,Fetch Restaurants from Yelp API
import requests
import time
from typing import List, Dict

# Get Yelp API key
yelp_api_key = dbutils.secrets.get(scope="restaurant-app", key="yelp-api-key")

def fetch_restaurants_for_location(location: str, limit: int = 50) -> List[Dict]:
    """Fetch restaurants from Yelp API for a single location."""
    url = "https://api.yelp.com/v3/businesses/search"
    headers = {"Authorization": f"Bearer {yelp_api_key}"}
    
    all_restaurants = []
    offset = 0
    max_results = 240  # Yelp API limit: offset + limit must be <= 240
    
    while offset < max_results:
        # Ensure offset + limit <= 240
        fetch_limit = min(limit, 50, max_results - offset)
        if fetch_limit <= 0:
            break
            
        params = {
            "location": location,
            "categories": "restaurants",
            "limit": fetch_limit,
            "offset": offset
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 429:  # Rate limit
            print(f"⏳ Rate limited, waiting 60s...")
            time.sleep(60)
            continue
        
        response.raise_for_status()
        data = response.json()
        businesses = data.get("businesses", [])
        
        if not businesses:
            break
            
        all_restaurants.extend(businesses)
        print(f"  Fetched {len(all_restaurants)} restaurants from {location}")
        
        if len(businesses) < limit:
            break
            
        offset += limit
        time.sleep(0.2)  # Rate limiting courtesy
    
    return all_restaurants

# Fetch restaurants for all locations
all_restaurants = []
for location in locations:
    print(f"\n🔍 Fetching restaurants in {location}...")
    restaurants = fetch_restaurants_for_location(location, limit=50)
    all_restaurants.extend(restaurants)
    print(f"✅ Total fetched from {location}: {len(restaurants)}")

print(f"\n📊 Total restaurants fetched across all locations: {len(all_restaurants)}")

# COMMAND ----------

# DBTITLE 1,Transform and Upsert to Lakebase
import json
from datetime import datetime

def upsert_restaurant(cur, restaurant: Dict) -> None:
    """Upsert a single restaurant into the database."""
    # Extract location data
    location = restaurant.get('location', {})
    coordinates = restaurant.get('coordinates', {})
    
    # Prepare data matching actual schema
    data = {
        'id': restaurant['id'],
        'name': restaurant['name'],
        'categories': json.dumps([cat['title'] for cat in restaurant.get('categories', [])]),  # Convert to JSON string for JSONB
        'rating': restaurant.get('rating'),
        'review_count': restaurant.get('review_count', 0),
        'price': restaurant.get('price'),
        'phone': restaurant.get('phone'),
        'address': ', '.join(filter(None, [
            location.get('address1'),
            location.get('address2'),
            location.get('address3')
        ])),
        'city': location.get('city'),
        'state': location.get('state'),
        'zip_code': location.get('zip_code'),
        'country': location.get('country'),
        'latitude': coordinates.get('latitude'),
        'longitude': coordinates.get('longitude'),
        'distance': restaurant.get('distance'),
        'image_url': restaurant.get('image_url'),
        'url': restaurant.get('url'),
        'payload': json.dumps(restaurant)  # Convert to JSON string for JSONB
    }
    
    # Upsert query matching actual schema
    cur.execute("""
        INSERT INTO restaurants (
            id, name, categories, rating, review_count, price, phone,
            address, city, state, zip_code, country, latitude, longitude,
            distance, image_url, url, payload, fetched_at
        ) VALUES (
            %(id)s, %(name)s, %(categories)s::jsonb, %(rating)s, %(review_count)s, %(price)s, %(phone)s,
            %(address)s, %(city)s, %(state)s, %(zip_code)s, %(country)s, %(latitude)s, %(longitude)s,
            %(distance)s, %(image_url)s, %(url)s, %(payload)s::jsonb, NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            categories = EXCLUDED.categories,
            rating = EXCLUDED.rating,
            review_count = EXCLUDED.review_count,
            price = EXCLUDED.price,
            phone = EXCLUDED.phone,
            address = EXCLUDED.address,
            city = EXCLUDED.city,
            state = EXCLUDED.state,
            zip_code = EXCLUDED.zip_code,
            country = EXCLUDED.country,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            distance = EXCLUDED.distance,
            image_url = EXCLUDED.image_url,
            url = EXCLUDED.url,
            payload = EXCLUDED.payload,
            updated_at = NOW();
    """, data)

# Upsert all restaurants
with psycopg2.connect(**db_config) as conn:
    with conn.cursor() as cur:
        for i, restaurant in enumerate(all_restaurants, 1):
            try:
                upsert_restaurant(cur, restaurant)
                if i % 50 == 0:
                    print(f"  Upserted {i}/{len(all_restaurants)} restaurants")
            except Exception as e:
                print(f"⚠️  Error upserting {restaurant.get('name', 'unknown')}: {e}")
                continue
        
        conn.commit()
        
        # Get final count
        cur.execute("SELECT COUNT(*) FROM restaurants;")
        total_count = cur.fetchone()[0]

print(f"\n✅ Upsert complete. Total restaurants in database: {total_count}")

# COMMAND ----------

# DBTITLE 1,Load Restaurants into DataFrame
import pandas as pd

# Load restaurants that don't have embeddings yet
query = """
    SELECT 
        r.id,
        r.name,
        r.categories,
        r.rating,
        r.review_count,
        r.price,
        r.address,
        r.city,
        r.state
    FROM restaurants r
    LEFT JOIN restaurant_embeddings e ON r.id = e.id
    WHERE e.id IS NULL;
"""

with psycopg2.connect(**db_config) as conn:
    df = pd.read_sql_query(query, conn)

print(f"📊 Loaded {len(df)} restaurants needing embeddings")
if len(df) > 0:
    display(df.head())

# COMMAND ----------

# DBTITLE 1,Compute Embeddings
from sentence_transformers import SentenceTransformer
import numpy as np

if len(df) == 0:
    print("✅ All restaurants already have embeddings")
else:
    # Load embedding model
    print(f"🤖 Loading model: {embedding_model_name}")
    model = SentenceTransformer(embedding_model_name)
    
    # Create text representations for each restaurant
    def create_restaurant_text(row) -> str:
        """Create a rich text representation for embedding."""
        parts = [
            f"Restaurant: {row['name']}",
            f"Location: {row['city']}, {row['state']}",
        ]
        
        if row['categories'] is not None and len(row['categories']) > 0:
            # Categories is already a list from JSONB
            parts.append(f"Cuisine: {', '.join(row['categories'])}")
        
        if pd.notna(row['price']):
            parts.append(f"Price level: {row['price']}")
        
        if pd.notna(row['rating']) and pd.notna(row['review_count']):
            parts.append(f"Rating: {row['rating']}/5 ({row['review_count']} reviews)")
        
        return ". ".join(parts)
    
    print("📝 Creating text representations...")
    df['embedding_text'] = df.apply(create_restaurant_text, axis=1)
    
    # Compute embeddings in batches
    print("🔢 Computing embeddings...")
    batch_size = 32
    embeddings = []
    
    for i in range(0, len(df), batch_size):
        batch = df['embedding_text'].iloc[i:i+batch_size].tolist()
        batch_embeddings = model.encode(batch, show_progress_bar=False)
        embeddings.extend(batch_embeddings)
        if (i + batch_size) % 100 == 0:
            print(f"  Processed {min(i + batch_size, len(df))}/{len(df)} embeddings")
    
    df['embedding'] = embeddings
    print(f"✅ Computed {len(embeddings)} embeddings (dimension: {len(embeddings[0])})")

# COMMAND ----------

# DBTITLE 1,Write Embeddings to Lakebase
if len(df) > 0:
    # Insert embeddings into database
    with psycopg2.connect(**db_config) as conn:
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                # Convert numpy array to list for JSON serialization
                embedding_list = row['embedding'].tolist()
                
                cur.execute("""
                    INSERT INTO restaurant_embeddings (
                        id, name, model_name, embedding
                    ) VALUES (
                        %s, %s, %s, %s::vector
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        model_name = EXCLUDED.model_name,
                        embedding = EXCLUDED.embedding;
                """, (
                    row['id'],
                    row['name'],
                    embedding_model_name,
                    embedding_list
                ))
            
            conn.commit()
            
            # Verify final count
            cur.execute("SELECT COUNT(*) FROM restaurant_embeddings;")
            total_embeddings = cur.fetchone()[0]
    
    print(f"✅ Embeddings written to database")
    print(f"📊 Total embeddings in database: {total_embeddings}")
else:
    print("ℹ️  No new embeddings to write")

# COMMAND ----------

# DBTITLE 1,Pipeline Summary
# Final pipeline statistics
with psycopg2.connect(**db_config) as conn:
    with conn.cursor() as cur:
        # Restaurant counts
        cur.execute("SELECT COUNT(*) FROM restaurants;")
        total_restaurants = cur.fetchone()[0]
        
        # Embedding counts
        cur.execute("SELECT COUNT(*) FROM restaurant_embeddings;")
        total_embeddings = cur.fetchone()[0]
        
        # Coverage
        cur.execute("""
            SELECT COUNT(*) FROM restaurants r
            LEFT JOIN restaurant_embeddings e ON r.id = e.id
            WHERE e.id IS NULL;
        """)
        missing_embeddings = cur.fetchone()[0]

print("="*60)
print("🎉 PIPELINE COMPLETE")
print("="*60)
print(f"📊 Total restaurants: {total_restaurants}")
print(f"🔢 Total embeddings: {total_embeddings}")
print(f"⚠️  Missing embeddings: {missing_embeddings}")
print(f"✅ Coverage: {(total_embeddings / total_restaurants * 100):.1f}%" if total_restaurants > 0 else "✅ Coverage: 0%")
print("="*60)

# COMMAND ----------

