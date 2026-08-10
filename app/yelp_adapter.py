"""Yelp Fusion API adapter."""
import base64
import os
import requests
from typing import List, Dict, Optional
from databricks.sdk import WorkspaceClient


class YelpClient:
    """Minimal Yelp Fusion API client."""
    
    def __init__(self):
        # Try environment variable first (for local development)
        self.api_key = os.getenv("YELP_API_KEY")
        
        # If not in env, fetch from Databricks secret scope (for deployed apps)
        if not self.api_key:
            try:
                w = WorkspaceClient()
                scope = os.getenv("YELP_SECRET_SCOPE", "restaurant-app")
                key = os.getenv("YELP_SECRET_KEY", "yelp-api-key")
                secret = w.secrets.get_secret(scope=scope, key=key)
                # Secrets may be base64 encoded
                try:
                    self.api_key = base64.b64decode(secret.value).decode("utf-8")
                except:
                    # If not base64, use as-is
                    self.api_key = secret.value
            except Exception as e:
                raise ValueError(
                    f"Failed to load YELP_API_KEY: {e}\n"
                    f"Tried Databricks secret scope='{scope}', key='{key}'\n"
                    "Ensure the secret exists with: databricks secrets put --scope restaurant-app --key yelp-api-key"
                )
        
        self.base_url = "https://api.yelp.com/v3"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
    
    def search_restaurants(
        self,
        location: str,
        term: Optional[str] = None,
        limit: int = 20,
        **kwargs
    ) -> List[Dict]:
        """Search for restaurants by location."""
        params = {
            "location": location,
            "categories": "restaurants",
            "limit": limit,
            **kwargs
        }
        if term:
            params["term"] = term
        
        response = requests.get(
            f"{self.base_url}/businesses/search",
            headers=self.headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("businesses", [])
    
    def get_restaurant_details(self, business_id: str) -> Dict:
        """Get detailed restaurant information by Yelp business ID."""
        response = requests.get(
            f"{self.base_url}/businesses/{business_id}",
            headers=self.headers,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
