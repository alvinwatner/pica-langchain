"""
Utility functions for Google Serper integration.
"""

import logging
import os
from typing import Optional, Any, List
from langchain_community.utilities import GoogleSerperAPIWrapper


logger = logging.getLogger(__name__)

def create_serper_wrapper(api_keys: Optional[List[str]] = None) -> Optional[Any]:
    """
    Create a GoogleSerperAPIWrapper instance if possible.
    
    Args:
        api_keys: List of Google Serper API keys to try in order.
        
    Returns:
        SerperWrapper instance or None if not available.
    """
    # Handle both old-style single API key and new-style list of keys
    if api_keys is None:
        return None
    
    # Convert single string to list for backward compatibility
    if isinstance(api_keys, str):
        api_keys = [api_keys]
        
    if not api_keys or len(api_keys) == 0:
        return None
        
    try:
        return SerperWrapper(api_keys)
    except ImportError:
        logger.warning("GoogleSerperAPIWrapper not available. The langchain-community package might be missing.")
        return None
    except Exception as e:
        logger.warning(f"Failed to initialize SerperWrapper: {str(e)}")
        return None


class SerperWrapper:
    """
    A wrapper for Google Serper API that tries multiple API keys.
    """
    
    def __init__(self, api_keys: List[str]):
        """
        Initialize the Serper wrapper with a list of API keys.
        
        Args:
            api_keys: List of Google Serper API keys to try in order.
        """
        if GoogleSerperAPIWrapper is None:
            raise ImportError("GoogleSerperAPIWrapper not available. Install with 'pip install langchain-community'")
            
        self.api_keys = api_keys
            
    def run(self, query: str) -> str:
        """
        Run a search query using Google Serper API.
        
        Args:
            query: The search query.
            
        Returns:
            JSON string with the search results.
            
        Raises:
            Exception: If all API keys fail.
        """
        last_error = None
        
        # Try each API key in order
        for api_key in self.api_keys:
            try:
                return self._search_with_key(query, api_key)
            except Exception as e:
                logger.warning(f"Google Serper search failed with API key: {api_key[:5]}...: {str(e)}")
                last_error = e
                continue
                
        # If we get here, all API keys failed
        raise Exception(f"All Google Serper API keys failed. Last error: {str(last_error)}")
        
    def _search_with_key(self, query: str, api_key: str) -> str:
        """
        Perform a search with a specific API key.
        
        Args:
            query: The search query.
            api_key: The Google Serper API key.
            
        Returns:
            JSON string with the search results.
        """
        # Set the environment variable for this specific search
        os.environ["SERPER_API_KEY"] = api_key
        
        # Create a new wrapper instance with this key
        wrapper = GoogleSerperAPIWrapper()
        
        # Run the search
        return wrapper.run(query)
