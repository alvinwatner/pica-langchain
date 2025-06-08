"""
Utility functions for Firecrawl SDK integration.
"""

import logging
import json
from typing import Optional, Any, List
from firecrawl import FirecrawlApp

logger = logging.getLogger(__name__)

def create_firecrawl_wrapper(api_keys: Optional[List[str]] = None) -> Optional[Any]:
    """
    Create a Firecrawl wrapper instance if possible.
    
    Args:
        api_keys: List of Firecrawl API keys to try in order.
        
    Returns:
        FirecrawlWrapper instance or None if not available.
    """
    if not api_keys or not isinstance(api_keys, list) or len(api_keys) == 0:
        return None
        
    try:
        return FirecrawlWrapper(api_keys)
    except Exception as e:
        logger.warning(f"Failed to initialize FirecrawlWrapper: {str(e)}")
        return None


class FirecrawlWrapper:
    """
    A wrapper for the Firecrawl SDK.
    """
    
    def __init__(self, api_keys: List[str]):
        """
        Initialize the Firecrawl wrapper with a list of API keys.
        
        Args:
            api_keys: List of Firecrawl API keys to try in order.
        """
        if FirecrawlApp is None:
            raise ImportError("The 'firecrawl' package is required. Install it with 'pip install firecrawl-py'")
            
        self.api_keys = api_keys 
    def run(self, query: str, limit: int = 10) -> str:
        """
        Run a search query using Firecrawl SDK.
        
        Args:
            query: The search query.
            limit: Maximum number of results to return.
            
        Returns:
            JSON string with the search results.
            
        Raises:
            Exception: If all API keys fail.
        """
        last_error = None
        
        # Try each API key in order
        for api_key in self.api_keys:
            try:
                return self._search_with_key(query, api_key, limit)
            except Exception as e:
                logger.warning(f"Firecrawl search failed with API key: {api_key[:5]}...: {str(e)}")
                last_error = e
                continue
                
        # If we get here, all API keys failed
        raise Exception(f"All Firecrawl API keys failed. Last error: {str(last_error)}")
        
    def _search_with_key(self, query: str, api_key: str, limit: int = 10) -> str:
        """
        Perform a search with a specific API key using the Firecrawl SDK.
        
        Args:
            query: The search query.
            api_key: The Firecrawl API key.
            limit: Maximum number of results to return.
            
        Returns:
            JSON string with the search results.
        """
        # Initialize the Firecrawl client with the API key
        app = FirecrawlApp(api_key=api_key)
        
        # Perform the search
        search_result = app.search(query, limit=limit)
        
        # Convert the search result to a dictionary that can be serialized to JSON
        results = {
            "query": query,
            "results": []
        }
        
        # Add each search result to the results list
        if hasattr(search_result, 'data') and search_result.data:
            for result in search_result.data:
                results["results"].append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "description": result.get("description", ""),
                    "snippet": result.get("snippet", ""),
                    "source": "firecrawl"
                })
                
        return json.dumps(results)
