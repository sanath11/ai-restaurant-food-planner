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
        """Get or create database connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.connection_url)
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
            # Ensure numeric types are properly converted
            formatted_results = []
            for row in results:
                row_dict = dict(row)
                # Convert rating to float
                if row_dict.get('rating'):
                    row_dict['rating'] = float(row_dict['rating'])
                if row_dict.get('review_count'):
                    row_dict['review_count'] = int(row_dict['review_count'])
                if row_dict.get('similarity'):
                    row_dict['similarity'] = float(row_dict['similarity'])
                formatted_results.append(row_dict)
            return formatted_results
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
        finally:
            cursor.close()
    
    def get_restaurant_by_id(self, restaurant_id: int) -> Optional[Dict[str, Any]]:
        """
        Get restaurant details by database ID.
        
        Args:
            restaurant_id: Internal database ID
        
        Returns:
            Restaurant dictionary or None
        """
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                id, yelp_id, name, rating, review_count, price_level,
                categories, address, city, state, postal_code,
                latitude, longitude, is_closed, url, phone
            FROM restaurants
            WHERE id = %s
        """
        
        try:
            cursor.execute(query, (restaurant_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error fetching restaurant {restaurant_id}: {e}")
            return None
        finally:
            cursor.close()
    
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
    
    # ===== USER PREFERENCES =====
    
    def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user preferences."""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT preferred_cuisines, dietary_restrictions, 
                   budget_range, preferred_ambiance, updated_at
            FROM user_preferences
            WHERE user_id = %s
        """
        
        try:
            cursor.execute(query, (user_id,))
            result = cursor.fetchone()
            if result:
                return dict(result)
            return {}
        except Exception as e:
            logger.error(f"Error getting preferences: {e}")
            return {}
        finally:
            cursor.close()
    
    def save_user_preferences(
        self,
        user_id: str,
        preferred_cuisines: Optional[str] = None,
        dietary_restrictions: Optional[str] = None,
        budget_range: Optional[str] = None,
        preferred_ambiance: Optional[str] = None
    ) -> bool:
        """Save or update user preferences."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO user_preferences 
                (user_id, preferred_cuisines, dietary_restrictions, budget_range, preferred_ambiance)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                preferred_cuisines = EXCLUDED.preferred_cuisines,
                dietary_restrictions = EXCLUDED.dietary_restrictions,
                budget_range = EXCLUDED.budget_range,
                preferred_ambiance = EXCLUDED.preferred_ambiance,
                updated_at = CURRENT_TIMESTAMP
        """
        
        try:
            cursor.execute(query, (
                user_id, preferred_cuisines, dietary_restrictions,
                budget_range, preferred_ambiance
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving preferences: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
    
    # ===== FAVORITES =====
    
    def get_user_favorites(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's favorite restaurants."""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT f.restaurant_id, f.notes, f.saved_at,
                   r.name as restaurant_name, r.rating, r.price,
                   r.categories, r.address, r.city
            FROM favorites f
            LEFT JOIN restaurants r ON f.restaurant_id = r.id
            WHERE f.user_id = %s
            ORDER BY f.saved_at DESC
        """
        
        try:
            cursor.execute(query, (user_id,))
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error getting favorites: {e}")
            return []
        finally:
            cursor.close()
    
    def save_favorite(self, user_id: str, restaurant_id: str, notes: Optional[str] = None) -> bool:
        """Save a restaurant as favorite."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO favorites (user_id, restaurant_id, notes)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, restaurant_id) DO UPDATE SET
                notes = EXCLUDED.notes,
                saved_at = NOW()
        """
        
        try:
            cursor.execute(query, (user_id, restaurant_id, notes))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving favorite: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
    
    def remove_favorite(self, user_id: str, restaurant_id: str) -> bool:
        """Remove a favorite restaurant."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "DELETE FROM favorites WHERE user_id = %s AND restaurant_id = %s"
        
        try:
            cursor.execute(query, (user_id, restaurant_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error removing favorite: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
    
    # ===== MEAL PLANS =====
    
    def get_user_meal_plans(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's meal plans."""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT id, plan_name, description, restaurant_ids, date, created_at, updated_at
            FROM meal_plans
            WHERE user_id = %s
            ORDER BY created_at DESC
        """
        
        try:
            cursor.execute(query, (user_id,))
            results = cursor.fetchall()
            # restaurant_ids is already a TEXT[] array in Postgres
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error getting meal plans: {e}")
            return []
        finally:
            cursor.close()
    
    def create_meal_plan(
        self,
        user_id: str,
        plan_name: str,
        restaurant_ids: List[str],
        description: Optional[str] = None,
        date: Optional[str] = None
    ) -> int:
        """Create a new meal plan. Returns plan_id or 0 on failure."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # restaurant_ids is passed as list and stored as TEXT[] in Postgres
        query = """
            INSERT INTO meal_plans (user_id, plan_name, description, restaurant_ids, date)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        
        try:
            cursor.execute(query, (user_id, plan_name, description, restaurant_ids, date))
            plan_id = cursor.fetchone()[0]
            conn.commit()
            return plan_id
        except Exception as e:
            logger.error(f"Error creating meal plan: {e}")
            conn.rollback()
            return 0
        finally:
            cursor.close()
    
    def update_meal_plan(
        self,
        plan_id: int,
        user_id: str,
        plan_name: Optional[str] = None,
        description: Optional[str] = None,
        restaurant_ids: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> bool:
        """Update an existing meal plan."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Build dynamic update query
        updates = []
        params = []
        
        if plan_name is not None:
            updates.append("plan_name = %s")
            params.append(plan_name)
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        if restaurant_ids is not None:
            updates.append("restaurant_ids = %s")
            params.append(restaurant_ids)  # Pass as list, Postgres handles TEXT[]
        if date is not None:
            updates.append("date = %s")
            params.append(date)
        
        if not updates:
            return False
        
        updates.append("updated_at = NOW()")
        params.extend([plan_id, user_id])
        
        query = f"""
            UPDATE meal_plans
            SET {', '.join(updates)}
            WHERE note_id = %s AND user_id = %s
        """
        
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating meal plan: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
    
    def delete_meal_plan(self, plan_id: int, user_id: str) -> bool:
        """Delete a meal plan."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "DELETE FROM meal_plans WHERE note_id = %s AND user_id = %s"
        
        try:
            cursor.execute(query, (plan_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting meal plan: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
    
    # ===== NOTES =====
    
    def save_note(
        self,
        user_id: str,
        restaurant_id: str,
        note_text: str,
        tags: Optional[List[str]] = None,
        personal_rating: Optional[float] = None,
        visit_date: Optional[str] = None
    ) -> Optional[int]:
        """Save a restaurant note. Returns note_id or None on failure."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        tags_str = ','.join(tags) if tags else None
        
        query = """
            INSERT INTO restaurant_notes 
                (user_id, restaurant_id, note_text, tags, personal_rating, visit_date)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        try:
            cursor.execute(query, (user_id, restaurant_id, note_text, tags_str, personal_rating, visit_date))
            note_id = cursor.fetchone()[0]
            conn.commit()
            return note_id
        except Exception as e:
            logger.error(f"Error saving note: {e}")
            conn.rollback()
            return None
        finally:
            cursor.close()
    
    def get_user_notes(
        self,
        user_id: str,
        restaurant_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get user's restaurant notes."""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if restaurant_id:
            query = """
                SELECT n.note_id, n.note_text, n.tags, n.personal_rating,
                       n.visit_date, n.created_at, n.updated_at,
                       r.name as restaurant_name, r.rating, r.categories
                FROM restaurant_notes n
                LEFT JOIN restaurants r ON n.restaurant_id = r.id
                WHERE n.user_id = %s AND n.restaurant_id = %s
                ORDER BY n.created_at DESC
                LIMIT %s
            """
            params = (user_id, restaurant_id, limit)
        else:
            query = """
                SELECT n.note_id, n.note_text, n.tags, n.personal_rating,
                       n.visit_date, n.created_at, n.updated_at,
                       r.name as restaurant_name, r.rating, r.categories
                FROM restaurant_notes n
                LEFT JOIN restaurants r ON n.restaurant_id = r.id
                WHERE n.user_id = %s
                ORDER BY n.created_at DESC
                LIMIT %s
            """
            params = (user_id, limit)
        
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            notes = []
            for row in results:
                note = dict(row)
                # Tags are already an array from Postgres
                if not note.get('tags'):
                    note['tags'] = []
                notes.append(note)
            return notes
        except Exception as e:
            logger.error(f"Error getting notes: {e}")
            return []
        finally:
            cursor.close()
    
    def update_note(
        self,
        note_id: int,
        user_id: str,
        note_text: Optional[str] = None,
        tags: Optional[List[str]] = None,
        personal_rating: Optional[float] = None,
        visit_date: Optional[str] = None
    ) -> bool:
        """Update an existing note."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if note_text is not None:
            updates.append("note_text = %s")
            params.append(note_text)
        if tags is not None:
            updates.append("tags = %s")
            params.append(tags)
        if personal_rating is not None:
            updates.append("personal_rating = %s")
            params.append(personal_rating)
        if visit_date is not None:
            updates.append("visit_date = %s")
            params.append(visit_date)
        
        if not updates:
            return False
        
        updates.append("updated_at = NOW()")
        params.extend([note_id, user_id])
        
        query = f"""
            UPDATE restaurant_notes
            SET {', '.join(updates)}
            WHERE note_id = %s AND user_id = %s
        """
        
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating note: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
    
    def delete_note(self, note_id: int, user_id: str) -> bool:
        """Delete a note."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "DELETE FROM restaurant_notes WHERE note_id = %s AND user_id = %s"
        
        try:
            cursor.execute(query, (note_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting note: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
