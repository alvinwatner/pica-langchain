"""
Platform-specific rules for Pica LangChain integration.

This module contains rules and guidelines for handling edge cases
specific to each platform supported by Pica.
"""

from typing import Dict, Optional, List
import os
import json
import importlib.resources as pkg_resources
from ..logger import get_logger

logger = get_logger()

# Dictionary to store loaded platform rules
_platform_rules_cache: Dict[str, str] = {}

def get_platform_rules(platform: str) -> Optional[str]:
    """
    Get rules specific to a platform.
    
    Args:
        platform: The platform to get rules for.
        
    Returns:
        Platform-specific rules as a string, or None if no rules exist.
    """
    # Check cache first
    if platform in _platform_rules_cache:
        return _platform_rules_cache[platform]
    
    # Try to load rules from JSON file
    try:
        # Use importlib.resources to access package data
        rules_text = None
        
        # First try platform-specific file
        try:
            rules_text = pkg_resources.read_text(__package__, f"{platform}.json")
            logger.debug(f"Loaded platform rules for {platform}")
        except FileNotFoundError:
            # Fall back to default rules if available
            try:
                rules_text = pkg_resources.read_text(__package__, "default.json")
                logger.debug(f"No specific rules for {platform}, using default rules")
            except FileNotFoundError:
                logger.debug(f"No rules found for {platform} and no default rules available")
                pass
        
        if rules_text:
            rules_data = json.loads(rules_text)
            rules_str = rules_data.get("rules", "")
            _platform_rules_cache[platform] = rules_str
            return rules_str
        
        return None
    except Exception as e:
        logger.error(f"Error loading platform rules for {platform}: {e}", exc_info=True)
        return None

def get_all_platforms_with_rules() -> List[str]:
    """
    Get a list of all platforms that have specific rules.
    
    Returns:
        List of platform names.
    """
    platforms = []
    
    try:
        # Get all JSON files in the package
        for resource in pkg_resources.contents(__package__):
            if resource.endswith('.json') and resource != 'default.json':
                platform_name = resource.replace('.json', '')
                platforms.append(platform_name)
        logger.debug(f"Found platform rules for: {', '.join(platforms)}")
    except Exception as e:
        logger.error(f"Error listing platform rules: {e}", exc_info=True)
    
    return platforms
