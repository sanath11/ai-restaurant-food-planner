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

    
    # ============= WRITE OPERATIONS =============
    
    def save_favorite(self, user_id: str, restaurant_id: str, notes: str = None) -> bool:
        """
        Save a restaurant as a user favorite.
        
        Args:
            user_id: User identifier
            restaurant_id: Restaurant ID from restaurants table
            notes: Optional user notes
        
        Returns:
            True if successful, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO user_favorites (user_id, restaurant_id, notes)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, restaurant_id) 
            DO UPDATE SET notes = EXCLUDED.notes
        """
        
        try:
            cursor.execute(query, (user_id, restaurant_id, notes))
            conn.commit()
            logger.info(f"Saved favorite: user={user_id}, restaurant={restaurant_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving favorite: {e}", exc_info=True)
            conn.rollback()
            return False
        finally:
            cursor.close()
    
    def remove_favorite(self, user_id: str, restaurant_id: str) -> bool:
        """Remove a restaurant from user favorites."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "DELETE FROM user_favorites WHERE user_id = %s AND restaurant_id = %s"
        
        try:
            cursor.execute(query, (user_id, restaurant_id))
            conn.commit()
            logger.info(f"Removed favorite: user={user_id}, restaurant={restaurant_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing favorite: {e}", exc_info=True)
            conn.rollback()
            return False
        finally:
            cursor.close()
    
    def get_user_favorites(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all favorites for a user with restaurant details."""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                f.restaurant_id, f.notes, f.created_at,
                r.name, r.rating, r.price, r.categories, r.address, r.city
            FROM user_favorites f
            JOIN restaurants r ON f.restaurant_id = r.id
            WHERE f.user_id = %s
            ORDER BY f.created_at DESC
        """
        
        try:
            cursor.execute(query, (user_id,))
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error fetching favorites: {e}", exc_info=True)
            conn.rollback()
            return []
        finally:
            cursor.close()
    
    def create_meal_plan(self, user_id: str, plan_name: str, restaurant_ids: List[str], 
                         description: str = None, date: str = None) -> int:
        """Create a meal plan. Returns plan ID or -1 on error."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO meal_plans (user_id, plan_name, description, restaurant_ids, date)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        
        try:
            cursor.execute(query, (user_id, plan_name, description, restaurant_ids, date))
            plan_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"Created meal plan: id={plan_id}, user={user_id}, name={plan_name}")
            return plan_id
        except Exception as e:
            logger.error(f"Error creating meal plan: {e}", exc_info=True)
            conn.rollback()
            return -1
        finally:
            cursor.close()
    
    def get_user_meal_plans(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all meal plans for a user."""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT id, plan_name, description, restaurant_ids, date, created_at, updated_at
            FROM meal_plans
            WHERE user_id = %s
            ORDER BY date DESC NULLS LAST, created_at DESC
        """
        
        try:
            cursor.execute(query, (user_id,))
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error fetching meal plans: {e}", exc_info=True)
            conn.rollback()
            return []
        finally:
            cursor.close()
    
    def update_meal_plan(self, plan_id: int, user_id: str, plan_name: str = None,
                         description: str = None, restaurant_ids: List[str] = None,
                         date: str = None) -> bool:
        """
        Update an existing meal plan. Only the plan owner can update.
        
        Args:
            plan_id: Meal plan ID to update
            user_id: User identifier (for ownership verification)
            plan_name: New plan name (optional)
            description: New description (optional)
            restaurant_ids: New list of restaurant IDs (optional)
            date: New date YYYY-MM-DD (optional)
        
        Returns:
            True if updated, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Build dynamic UPDATE query based on provided fields
        update_fields = []
        params = []
        
        if plan_name is not None:
            update_fields.append("plan_name = %s")
            params.append(plan_name)
        
        if description is not None:
            update_fields.append("description = %s")
            params.append(description)
        
        if restaurant_ids is not None:
            update_fields.append("restaurant_ids = %s")
            params.append(restaurant_ids)
        
        if date is not None:
            update_fields.append("date = %s")
            params.append(date)
        
        if not update_fields:
            logger.warning("No fields to update for meal plan")
            return False
        
        # Add WHERE clause params
        params.extend([plan_id, user_id])
        
        query = f"""
            UPDATE meal_plans
            SET {', '.join(update_fields)}
            WHERE id = %s AND user_id = %s
        """
        
        try:
            cursor.execute(query, params)
            rows_affected = cursor.rowcount
            conn.commit()
            
            if rows_affected > 0:
                logger.info(f"Updated meal plan {plan_id} for user {user_id}")
                return True
            else:
                logger.warning(f"No meal plan found with id {plan_id} for user {user_id}")
                return False
        except Exception as e:
            logger.error(f"Error updating meal plan {plan_id}: {e}", exc_info=True)
            conn.rollback()
            return False
        finally:
            cursor.close()
    
    def delete_meal_plan(self, plan_id: int, user_id: str) -> bool:
        """
        Delete a meal plan. Only the plan owner can delete.
        
        Args:
            plan_id: Meal plan ID to delete
            user_id: User identifier (for ownership verification)
        
        Returns:
            True if deleted, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "DELETE FROM meal_plans WHERE id = %s AND user_id = %s"
        
        try:
            cursor.execute(query, (plan_id, user_id))
            rows_affected = cursor.rowcount
            conn.commit()
            
            if rows_affected > 0:
                logger.info(f"Deleted meal plan {plan_id} for user {user_id}")
                return True
            else:
                logger.warning(f"No meal plan found with id {plan_id} for user {user_id}")
                return False
        except Exception as e:
            logger.error(f"Error deleting meal plan {plan_id}: {e}", exc_info=True)
            conn.rollback()
            return False
        finally:
            cursor.close()
    
    def save_user_preferences(self, user_id: str, preferred_cuisines: List[str] = None,
                             avoided_cuisines: List[str] = None, max_price_level: int = None,
                             dietary_restrictions: List[str] = None, default_location: str = None) -> bool:
        """Save or update user dining preferences."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO user_preferences 
                (user_id, preferred_cuisines, avoided_cuisines, max_price_level, dietary_restrictions, default_location)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                preferred_cuisines = COALESCE(EXCLUDED.preferred_cuisines, user_preferences.preferred_cuisines),
                avoided_cuisines = COALESCE(EXCLUDED.avoided_cuisines, user_preferences.avoided_cuisines),
                max_price_level = COALESCE(EXCLUDED.max_price_level, user_preferences.max_price_level),
                dietary_restrictions = COALESCE(EXCLUDED.dietary_restrictions, user_preferences.dietary_restrictions),
                default_location = COALESCE(EXCLUDED.default_location, user_preferences.default_location),
                updated_at = now()
        """
        
        try:
            cursor.execute(query, (user_id, preferred_cuisines, avoided_cuisines, 
                                 max_price_level, dietary_restrictions, default_location))
            conn.commit()
            logger.info(f"Saved preferences for user={user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving preferences: {e}", exc_info=True)
            conn.rollback()
            return False
        finally:
            cursor.close()
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user dining preferences."""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = "SELECT * FROM user_preferences WHERE user_id = %s"
        
        try:
            cursor.execute(query, (user_id,))
            result = cursor.fetchone()
            return dict(result) if result else {}
        except Exception as e:
            logger.error(f"Error fetching preferences: {e}", exc_info=True)
            conn.rollback()
            return {}
        finally:
            cursor.close()

    def save_note(
        self,
        user_id: str,
        restaurant_id: str,
        note_text: str,
        tags: List[str] = None,
        personal_rating: float = None,
        visit_date: str = None
    ) -> Optional[int]:
        """
        Save a note for a restaurant.
        
        Args:
            user_id: User identifier
            restaurant_id: Restaurant ID (Yelp business ID)
            note_text: The note content
            tags: Optional list of tags (e.g., ['favorite', 'vegetarian-friendly'])
            personal_rating: Optional personal rating 0-5
            visit_date: Optional visit date (YYYY-MM-DD format)
        
        Returns:
            note_id if successful, None otherwise
        """
        conn = self._get_connection()
        if not conn:
            logger.error("Failed to get database connection")
            return None
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO restaurant_notes (
                        user_id, restaurant_id, note_text, tags, personal_rating, visit_date
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s
                    )
                    RETURNING note_id;
                """, (
                    user_id,
                    restaurant_id,
                    note_text,
                    tags,
                    personal_rating,
                    visit_date
                ))
                
                note_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Saved note {note_id} for user {user_id} on restaurant {restaurant_id}")
                return note_id
        
        except Exception as e:
            logger.error(f"Error saving note: {e}")
            conn.rollback()
            return None


    def get_user_notes(
        self,
        user_id: str,
        restaurant_id: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get notes for a user, optionally filtered by restaurant.
        
        Args:
            user_id: User identifier
            restaurant_id: Optional restaurant ID to filter by
            limit: Maximum number of notes to return
        
        Returns:
            List of note dictionaries with all fields
        """
        conn = self._get_connection()
        if not conn:
            logger.error("Failed to get database connection")
            return []
        
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if restaurant_id:
                    cur.execute("""
                        SELECT 
                            n.note_id,
                            n.user_id,
                            n.restaurant_id,
                            n.note_text,
                            n.tags,
                            n.personal_rating,
                            n.visit_date,
                            n.created_at,
                            n.updated_at,
                            r.name as restaurant_name,
                            r.rating as restaurant_rating,
                            r.categories
                        FROM restaurant_notes n
                        JOIN restaurants r ON n.restaurant_id = r.id
                        WHERE n.user_id = %s AND n.restaurant_id = %s
                        ORDER BY n.created_at DESC
                        LIMIT %s;
                    """, (user_id, restaurant_id, limit))
                else:
                    cur.execute("""
                        SELECT 
                            n.note_id,
                            n.user_id,
                            n.restaurant_id,
                            n.note_text,
                            n.tags,
                            n.personal_rating,
                            n.visit_date,
                            n.created_at,
                            n.updated_at,
                            r.name as restaurant_name,
                            r.rating as restaurant_rating,
                            r.categories
                        FROM restaurant_notes n
                        JOIN restaurants r ON n.restaurant_id = r.id
                        WHERE n.user_id = %s
                        ORDER BY n.created_at DESC
                        LIMIT %s;
                    """, (user_id, limit))
                
                notes = cur.fetchall()
                return [dict(note) for note in notes]
        
        except Exception as e:
            logger.error(f"Error getting notes for user {user_id}: {e}")
            return []


    def update_note(
        self,
        note_id: int,
        user_id: str,
        note_text: str = None,
        tags: List[str] = None,
        personal_rating: float = None,
        visit_date: str = None
    ) -> bool:
        """
        Update an existing note. Only the note owner can update.
        
        Args:
            note_id: Note ID to update
            user_id: User identifier (for ownership verification)
            note_text: New note text (optional)
            tags: New tags (optional)
            personal_rating: New personal rating (optional)
            visit_date: New visit date (optional)
        
        Returns:
            True if updated, False otherwise
        """
        conn = self._get_connection()
        if not conn:
            logger.error("Failed to get database connection")
            return False
        
        try:
            # Build dynamic UPDATE query based on provided fields
            update_fields = []
            params = []
            
            if note_text is not None:
                update_fields.append("note_text = %s")
                params.append(note_text)
            
            if tags is not None:
                update_fields.append("tags = %s")
                params.append(tags)
            
            if personal_rating is not None:
                update_fields.append("personal_rating = %s")
                params.append(personal_rating)
            
            if visit_date is not None:
                update_fields.append("visit_date = %s")
                params.append(visit_date)
            
            if not update_fields:
                logger.warning("No fields to update")
                return False
            
            # Add WHERE clause params
            params.extend([note_id, user_id])
            
            query = f"""
                UPDATE restaurant_notes
                SET {', '.join(update_fields)}
                WHERE note_id = %s AND user_id = %s;
            """
            
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows_affected = cur.rowcount
                conn.commit()
                
                if rows_affected > 0:
                    logger.info(f"Updated note {note_id} for user {user_id}")
                    return True
                else:
                    logger.warning(f"No note found with id {note_id} for user {user_id}")
                    return False
        
        except Exception as e:
            logger.error(f"Error updating note {note_id}: {e}")
            conn.rollback()
            return False


    def delete_note(
        self,
        note_id: int,
        user_id: str
    ) -> bool:
        """
        Delete a note. Only the note owner can delete.
        
        Args:
            note_id: Note ID to delete
            user_id: User identifier (for ownership verification)
        
        Returns:
            True if deleted, False otherwise
        """
        conn = self._get_connection()
        if not conn:
            logger.error("Failed to get database connection")
            return False
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM restaurant_notes
                    WHERE note_id = %s AND user_id = %s;
                """, (note_id, user_id))
                
                rows_affected = cur.rowcount
                conn.commit()
                
                if rows_affected > 0:
                    logger.info(f"Deleted note {note_id} for user {user_id}")
                    return True
                else:
                    logger.warning(f"No note found with id {note_id} for user {user_id}")
                    return False
        
        except Exception as e:
            logger.error(f"Error deleting note {note_id}: {e}")
            conn.rollback()
            return False
