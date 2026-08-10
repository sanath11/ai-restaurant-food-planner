"""Multi-factor recommendation scoring engine.

Transparent, explainable restaurant recommendations using 6 scoring factors:
1. Rating - Yelp star rating
2. Popularity - Review count (log-scaled)
3. Preference Match - Cuisine alignment
4. Semantic Similarity - Vector embedding match
5. Price Match - Budget alignment
6. Distance - Proximity to location
"""

import logging
import math
from typing import List, Dict, Optional, Any
import numpy as np

logger = logging.getLogger(__name__)

# Scoring constants - explicit defaults to avoid magic numbers
NEUTRAL_SCORE = 0.5  # Score when data is missing or neutral preference
MAX_YELP_RATING = 5.0  # Yelp's 5-star rating scale
POPULARITY_LOG_THRESHOLD = 3.0  # log10(1000) = 3.0, normalizes review counts to 0-1
DEFAULT_MAX_DISTANCE_KM = 10.0  # Reasonable walking/driving distance in urban areas
EARTH_RADIUS_KM = 6371  # Earth's radius for Haversine distance calculation


class RecommendationEngine:
    """Multi-factor scoring engine for restaurant recommendations."""
    
    def __init__(
        self,
        w_rating: float = 0.20,
        w_popularity: float = 0.15,
        w_preference: float = 0.20,
        w_semantic: float = 0.25,
        w_price: float = 0.10,
        w_distance: float = 0.10
    ):
        """
        Initialize recommendation engine with configurable weights.
        
        Args:
            w_rating: Weight for rating score (default 0.20)
            w_popularity: Weight for popularity score (default 0.15)
            w_preference: Weight for cuisine preference match (default 0.20)
            w_semantic: Weight for semantic similarity (default 0.25)
            w_price: Weight for price match (default 0.10)
            w_distance: Weight for distance score (default 0.10)
        """
        # Normalize weights to sum to 1.0
        total = w_rating + w_popularity + w_preference + w_semantic + w_price + w_distance
        
        self.w_rating = w_rating / total
        self.w_popularity = w_popularity / total
        self.w_preference = w_preference / total
        self.w_semantic = w_semantic / total
        self.w_price = w_price / total
        self.w_distance = w_distance / total
        
        logger.info(f"Recommendation weights: rating={self.w_rating:.3f}, "
                   f"popularity={self.w_popularity:.3f}, preference={self.w_preference:.3f}, "
                   f"semantic={self.w_semantic:.3f}, price={self.w_price:.3f}, distance={self.w_distance:.3f}")
    
    def score_rating(self, rating: float) -> float:
        """
        Score based on Yelp rating (0-5 stars).
        
        Args:
            rating: Restaurant rating (0-5)
        
        Returns:
            Normalized score (0-1)
        """
        if rating is None:
            return 0.5  # Neutral score for missing data
        return min(rating / 5.0, 1.0)
    
    def score_popularity(self, review_count: int) -> float:
        """
        Score based on review count (log-scaled).
        
        Args:
            review_count: Number of reviews
        
        Returns:
            Normalized score (0-1)
        """
        if review_count is None or review_count <= 0:
            return 0.0
        
        # Log-scale: 1 review = 0.0, 1000+ reviews = 1.0
        score = math.log10(review_count) / POPULARITY_LOG_THRESHOLD
        return min(score, 1.0)
    
    def score_preference_match(
        self,
        restaurant_categories: List[str],
        preferred_cuisines: Optional[List[str]] = None,
        avoided_cuisines: Optional[List[str]] = None
    ) -> float:
        """
        Score based on cuisine preference alignment.
        
        Args:
            restaurant_categories: Restaurant's cuisine categories
            preferred_cuisines: User's preferred cuisines (case-insensitive)
            avoided_cuisines: User's avoided cuisines (case-insensitive)
        
        Returns:
            Score (0-1), penalized if avoided cuisine present
        """
        if not restaurant_categories:
            return 0.5  # Neutral
        
        # Normalize to lowercase for comparison
        restaurant_cats_lower = [c.lower() for c in restaurant_categories]
        
        # Check avoided cuisines - heavy penalty
        if avoided_cuisines:
            avoided_lower = [c.lower() for c in avoided_cuisines]
            for avoided in avoided_lower:
                if any(avoided in cat for cat in restaurant_cats_lower):
                    return 0.0  # Hard filter
        
        # Check preferred cuisines - boost score
        if preferred_cuisines:
            preferred_lower = [c.lower() for c in preferred_cuisines]
            matches = sum(
                1 for pref in preferred_lower
                if any(pref in cat for cat in restaurant_cats_lower)
            )
            if matches > 0:
                return min(matches / len(preferred_cuisines), 1.0)
        
        return 0.5  # Neutral if no preferences specified
    
    def score_semantic_similarity(self, similarity: Optional[float]) -> float:
        """
        Score based on semantic similarity from pgvector.
        
        Args:
            similarity: Cosine similarity (0-1) from pgvector
        
        Returns:
            Normalized score (0-1)
        """
        if similarity is None:
            return 0.5  # Neutral
        return max(0.0, min(similarity, 1.0))
    
    def score_price_match(
        self,
        restaurant_price_level: Optional[int],
        max_price_level: Optional[int] = None
    ) -> float:
        """
        Score based on price match to user budget.
        
        Args:
            restaurant_price_level: Restaurant price (1-4, where 1=$ and 4=$$$$)
            max_price_level: User's max acceptable price level
        
        Returns:
            Score (1.0 if within budget, 0.0 if over)
        """
        if restaurant_price_level is None:
            return 0.5  # Neutral
        
        if max_price_level is None:
            return 1.0  # No budget constraint = always match
        
        if restaurant_price_level <= max_price_level:
            # Reward cheaper options slightly
            return 1.0 - (restaurant_price_level - 1) * 0.1
        else:
            return 0.0  # Over budget
    
    def score_distance(
        self,
        restaurant_lat: Optional[float],
        restaurant_lon: Optional[float],
        user_lat: Optional[float],
        user_lon: Optional[float],
        max_distance_km: float = 10.0
    ) -> float:
        """
        Score based on distance from user location.
        
        Args:
            restaurant_lat: Restaurant latitude
            restaurant_lon: Restaurant longitude
            user_lat: User latitude
            user_lon: User longitude
            max_distance_km: Max acceptable distance in km (default 10km)
        
        Returns:
            Score (1.0 for very close, decreases with distance)
        """
        if any(x is None for x in [restaurant_lat, restaurant_lon, user_lat, user_lon]):
            return 0.5  # Neutral if location unknown
        
        # Haversine distance
        distance_km = self._haversine_distance(
            user_lat, user_lon, restaurant_lat, restaurant_lon
        )
        
        if distance_km > max_distance_km:
            return 0.0  # Too far
        
        # Linear decay: 0km = 1.0, max_distance_km = 0.0
        return 1.0 - (distance_km / max_distance_km)
    
    def _haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate distance between two points using Haversine formula.
        
        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth radius in km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def score_restaurant(
        self,
        restaurant: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]] = None,
        user_location: Optional[Dict[str, float]] = None,
        semantic_similarity: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate total recommendation score with transparent evidence.
        
        Args:
            restaurant: Restaurant data dict
            user_preferences: User preference dict with keys:
                - preferred_cuisines: List[str]
                - avoided_cuisines: List[str]
                - max_price_level: int (1-4)
                - min_rating: float (0-5)
            user_location: Dict with 'latitude' and 'longitude' keys
            semantic_similarity: Pre-computed similarity score (0-1)
        
        Returns:
            Dict with total_score, factor scores, and evidence
        """
        prefs = user_preferences or {}
        
        # Calculate individual factor scores
        rating_score = self.score_rating(restaurant.get('rating'))
        popularity_score = self.score_popularity(restaurant.get('review_count'))
        
        preference_score = self.score_preference_match(
            restaurant.get('categories', []),
            prefs.get('preferred_cuisines'),
            prefs.get('avoided_cuisines')
        )
        
        semantic_score = self.score_semantic_similarity(semantic_similarity)
        
        price_score = self.score_price_match(
            restaurant.get('price_level'),
            prefs.get('max_price_level')
        )
        
        distance_score = 0.5  # Default neutral
        if user_location:
            distance_score = self.score_distance(
                restaurant.get('latitude'),
                restaurant.get('longitude'),
                user_location.get('latitude'),
                user_location.get('longitude')
            )
        
        # Calculate weighted total
        total_score = (
            self.w_rating * rating_score +
            self.w_popularity * popularity_score +
            self.w_preference * preference_score +
            self.w_semantic * semantic_score +
            self.w_price * price_score +
            self.w_distance * distance_score
        )
        
        # Build evidence
        price_str = '$' * (restaurant.get('price_level') or 1)
        
        evidence = {
            'rating': f"{restaurant.get('rating', 0)}/5 stars",
            'review_count': f"{restaurant.get('review_count', 0)} reviews",
            'categories': restaurant.get('categories', []),
            'price': price_str,
        }
        
        if user_location and restaurant.get('latitude') and restaurant.get('longitude'):
            dist_km = self._haversine_distance(
                user_location['latitude'],
                user_location['longitude'],
                restaurant['latitude'],
                restaurant['longitude']
            )
            evidence['distance'] = f"{dist_km:.1f} km away"
        
        return {
            'restaurant': restaurant,
            'total_score': round(total_score, 3),
            'factors': {
                'rating_score': round(rating_score, 3),
                'popularity_score': round(popularity_score, 3),
                'preference_match_score': round(preference_score, 3),
                'semantic_similarity_score': round(semantic_score, 3),
                'price_match_score': round(price_score, 3),
                'distance_score': round(distance_score, 3)
            },
            'evidence': evidence
        }
    
    def rank_restaurants(
        self,
        restaurants: List[Dict[str, Any]],
        user_preferences: Optional[Dict[str, Any]] = None,
        user_location: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Score and rank multiple restaurants.
        
        Args:
            restaurants: List of restaurant dicts (must include 'similarity' if from semantic search)
            user_preferences: User preferences
            user_location: User location
        
        Returns:
            Sorted list of scored restaurants (highest score first)
        """
        scored = []
        for restaurant in restaurants:
            # Use pre-computed similarity if available
            similarity = restaurant.get('similarity')
            
            score_result = self.score_restaurant(
                restaurant,
                user_preferences,
                user_location,
                similarity
            )
            scored.append(score_result)
        
        # Sort by total_score descending
        scored.sort(key=lambda x: x['total_score'], reverse=True)
        
        return scored
