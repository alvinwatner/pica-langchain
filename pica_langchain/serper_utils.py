"""
Utility functions for Google Serper integration.
This module isolates the GoogleSerperAPIWrapper import to avoid dependency issues.
"""

import logging
import os
from typing import Optional, Any

logger = logging.getLogger(__name__)

def create_serper_wrapper(api_key: Optional[str] = None) -> Optional[Any]:
    """
    Create a GoogleSerperAPIWrapper instance if possible.
    
    Args:
        api_key: The Google Serper API key.
        
    Returns:
        GoogleSerperAPIWrapper instance or None if not available.
    """
    if not api_key:
        return None
        
    try:
        from langchain_community.utilities import GoogleSerperAPIWrapper
        os.environ["SERPER_API_KEY"] = api_key
        return GoogleSerperAPIWrapper()
    except ImportError:
        logger.warning("GoogleSerperAPIWrapper not available. The langchain-community package might be missing.")
        return None
    except Exception as e:
        logger.warning(f"Failed to initialize GoogleSerperAPIWrapper: {str(e)}")
        return None
