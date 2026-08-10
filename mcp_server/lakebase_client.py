"""Lakebase Postgres client for restaurant data access.

Handles connections to Lakebase and queries for restaurants, reviews, and embeddings.
"""

import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional, Any
import numpy as np

logger = logging.getLogger(__name__)


class LakebaseClient:
    """Client for querying restaurant data from Lakebase Postgres."""
    
    def __init__(self, connection_url: str):
        """
        Initialize Lakebase client.
        
        Args:
            connection_url: Postgres connection string (postgres://user:pass@host:port/db)
        """
        self.connection_url = connection_url
        self._conn = None
    
    def _get_connection(self):
        """Get or create database connection with auto-reconnect."""
        try:
            # Check if connection exists and is usable
            if self._conn is not None and not self._conn.closed:
                # Test connection with a simple query
                cursor = self._conn.cursor()
                cursor.execute('SELECT 1')
                cursor.close()
                return self._conn
        except (psycopg2.OperationalError, psycopg2.InterfaceError, AttributeError):
            # Connection is bad, will reconnect
            logger.info("Database connection lost, reconnecting...")
            if self._conn and not self._conn.closed:
                try:
                    self._conn.close()
                except:
                    pass
            self._conn = None
        
        # Create new connection
        if self._conn is None:
            logger.info("Creating new database connection")
            self._conn = psycopg2.connect(self.connection_url)
            self._conn.autocommit = True  # Auto-commit for read operations
        
        return self._conn
    
    def close(self):
        """Close database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
    
    def search_restaurants_by_location(
        self,
        location: str,
        categories: Optional[List[str]] = None,
        min_rating: Optional[float] = None,
        max_price_level: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search restaurants by location and filters.
        
        Args:
            location: City or location string to search
            categories: List of cuisine categories to filter
            min_rating: Minimum rating (0-5)
            max_price_level: Maximum price level (1-4)
            limit: Max results
        
        Returns:
            List of restaurant dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                id, yelp_id, name, rating, review_count, price_level,
                categories, address, city, state, postal_code,
                latitude, longitude, is_closed, url
            FROM restaurants
            WHERE city ILIKE %s
        """
        params = [f"%{location}%"]
        
        if categories:
            query += " AND categories && %s"
            params.append(categories)
        
        if min_rating is not None:
            query += " AND rating >= %s"
            params.append(min_rating)
        
        if max_price_level is not None:
            query += " AND price_level <= %s"
            params.append(max_price_level)
        
        query += " ORDER BY rating DESC, review_count DESC LIMIT %s"
        params.append(limit)
        
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error searching restaurants: {e}")
            return []
        finally:
            cursor.close()
    
    def semantic_search_restaurants(
        self,
        query_embedding: np.ndarray,
        min_rating: Optional[float] = None,
        max_price_level: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search restaurants using semantic similarity (pgvector).
        Pure semantic search based on query embedding - no location filtering.
        Joins with restaurant_embeddings table for semantic search.
        
        Args:
            query_embedding: Query embedding vector (384-dim for MiniLM)
            min_rating: Minimum rating filter
            max_price_level: Maximum price level (1-4, derived from price string length)
            limit: Max results
        
        Returns:
            List of restaurants with similarity scores, sorted by semantic relevance
        """
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Convert numpy array to list for postgres
        embedding_list = query_embedding.tolist()
        
        # Join with restaurant_embeddings table for semantic search
        # Map actual schema: id (text), price (text), zip_code, etc.
        # restaurant_embeddings has 'id' column (not 'restaurant_id') that matches restaurants.id
        query = """
            SELECT 
                r.id as yelp_id, r.name, r.rating, r.review_count,
                LENGTH(r.price) as price_level, r.price,
                r.categories, r.address, r.city, r.state, r.zip_code as postal_code,
                r.latitude, r.longitude, r.url,
                1 - (e.embedding <=> %s::vector) as similarity
            FROM restaurants r
            INNER JOIN restaurant_embeddings e ON r.id = e.id
            WHERE e.embedding IS NOT NULL
        """
        params = [embedding_list]
        
        if min_rating is not None:
            query += " AND r.rating >= %s"
            params.append(min_rating)
        
        if max_price_level is not None:
            # Filter by price string length (e.g., "$" = length 2)
            query += " AND LENGTH(r.price) <= %s"
            params.append(max_price_level)
        
        query += " ORDER BY e.embedding <=> %s::vector LIMIT %s"
        params.extend([embedding_list, limit])
        
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            logger.info(f"Semantic search returned {len(results)} results")
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error in semantic search: {e}", exc_info=True)
            conn.rollback()
            return []
        finally:
            cursor.close()
    
    def get_restaurant_by_id(self, restaurant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get restaurant details by ID (Yelp ID string).
        
        Args:
            restaurant_id: Restaurant ID (Yelp ID string)
        
        Returns:
            Restaurant dictionary or None
        """
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Map to actual schema: id (text), price (text), zip_code, no price_level/postal_code columns
        query = """
            SELECT 
                id as yelp_id, name, rating, review_count,
                LENGTH(price) as price_level, price,
                categories, address, city, state, zip_code as postal_code,
                latitude, longitude, is_closed, url, phone
            FROM restaurants
            WHERE id = %s
        """
        
        try:
            cursor.execute(query, (restaurant_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error fetching restaurant {restaurant_id}: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return None
        finally:
            try:
                cursor.close()
            except:
                pass
    
    def get_restaurant_reviews(self, restaurant_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get reviews for a restaurant from review_embeddings table.
        
        Args:
            restaurant_id: Restaurant ID (Yelp ID string)
            limit: Max number of reviews
        
        Returns:
            List of review dictionaries with text
        """
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # review_embeddings table has: restaurant_id, review_text, embedding
        query = """
            SELECT 
                restaurant_id,
                review_text as text,
                5 as rating,
                'Reviewer' as user_name
            FROM review_embeddings
            WHERE restaurant_id = %s
            LIMIT %s
        """
        
        try:
            logger.info(f"Querying reviews for restaurant_id: {restaurant_id}")
            cursor.execute(query, (restaurant_id, limit))
            results = cursor.fetchall()
            logger.info(f"Query returned {len(results)} reviews for restaurant {restaurant_id}")
            if len(results) == 0:
                # Check if this restaurant_id exists at all
                cursor.execute("SELECT COUNT(*) FROM review_embeddings WHERE restaurant_id = %s", (restaurant_id,))
                count = cursor.fetchone()[0]
                logger.warning(f"No reviews found. Total reviews for {restaurant_id}: {count}")
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error fetching reviews for restaurant {restaurant_id}: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return []
        finally:
            try:
                cursor.close()
            except:
                pass
