"""
Cache utilities for PicaClient to improve initialization performance.
"""
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib
from .logger import get_logger

logger = get_logger()


class PicaCache:
    """Handles file-based caching for PicaClient data."""
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        cache_ttl: int = 86400,  # 24 hours default
        enabled: bool = True
    ):
        """
        Initialize the cache manager.
        
        Args:
            cache_dir: Directory to store cache files. Defaults to ~/.pica_cache
            cache_ttl: Time-to-live for cache entries in seconds
            enabled: Whether caching is enabled
        """
        self.enabled = enabled
        self.cache_ttl = cache_ttl
        
        # Set cache directory
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".pica_cache"
        
        # Create cache directory if it doesn't exist
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Cache directory: {self.cache_dir}")
    
    def _generate_cache_key(self, cache_type: str, **filters) -> str:
        """
        Generate a unique cache key based on type and filters.
        
        Args:
            cache_type: Type of cache (connections, connectors)
            **filters: Filter parameters that affect the cache
            
        Returns:
            A unique cache key string
        """
        # Sort filters for consistent key generation
        filter_str = json.dumps(filters, sort_keys=True)
        hash_digest = hashlib.md5(filter_str.encode()).hexdigest()[:8]
        
        # Build readable cache key
        parts = [cache_type]
        
        # Add important filters to filename for debugging
        if filters.get("identity"):
            parts.append(f"id_{filters['identity'][:8]}")
        if filters.get("identity_type"):
            parts.append(filters["identity_type"])
        if filters.get("authkit"):
            parts.append("authkit")
            
        parts.append(hash_digest)
        
        return "_".join(parts) + ".json"
    
    def _get_cache_path(self, cache_type: str, **filters) -> Path:
        """Get the full path for a cache file."""
        cache_key = self._generate_cache_key(cache_type, **filters)
        return self.cache_dir / cache_key
    
    def _get_metadata_path(self, cache_path: Path) -> Path:
        """Get the metadata file path for a cache file."""
        return cache_path.with_suffix(".meta.json")
    
    def load(self, cache_type: str, **filters) -> Optional[List[Dict[str, Any]]]:
        """
        Load data from cache if valid.
        
        Args:
            cache_type: Type of cache to load
            **filters: Filter parameters used for cache key
            
        Returns:
            Cached data if valid, None otherwise
        """
        if not self.enabled:
            return None
            
        cache_path = self._get_cache_path(cache_type, **filters)
        meta_path = self._get_metadata_path(cache_path)
        
        # Check if cache files exist
        if not cache_path.exists() or not meta_path.exists():
            logger.debug(f"Cache miss: {cache_path.name} not found")
            return None
        
        try:
            # Load metadata
            with open(meta_path, 'r') as f:
                metadata = json.load(f)
            
            # Check TTL
            cache_age = time.time() - metadata["timestamp"]
            if cache_age > self.cache_ttl:
                logger.info(f"Cache expired: {cache_path.name} (age: {cache_age:.1f}s)")
                return None
            
            # Load cached data
            with open(cache_path, 'r') as f:
                data = json.load(f)
            
            logger.info(
                f"Cache hit: {cache_path.name} "
                f"({len(data)} items, age: {cache_age:.1f}s)"
            )
            return data
            
        except Exception as e:
            logger.error(f"Error loading cache {cache_path.name}: {e}")
            return None
    
    def save(self, cache_type: str, data: List[Dict[str, Any]], **filters) -> bool:
        """
        Save data to cache with metadata.
        
        Args:
            cache_type: Type of cache to save
            data: Data to cache
            **filters: Filter parameters used for cache key
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not self.enabled:
            return False
            
        cache_path = self._get_cache_path(cache_type, **filters)
        meta_path = self._get_metadata_path(cache_path)
        
        try:
            # Save data
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Save metadata
            metadata = {
                "timestamp": time.time(),
                "count": len(data),
                "filters": filters,
                "cache_type": cache_type
            }
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Cache saved: {cache_path.name} ({len(data)} items)")
            return True
            
        except Exception as e:
            logger.error(f"Error saving cache {cache_path.name}: {e}")
            return False
    
    def invalidate(self, cache_type: Optional[str] = None, **filters) -> int:
        """
        Invalidate cache entries.
        
        Args:
            cache_type: Type of cache to invalidate, or None for all
            **filters: Filter parameters to match for invalidation
            
        Returns:
            Number of cache entries invalidated
        """
        if not self.enabled:
            return 0
            
        count = 0
        
        try:
            if cache_type and filters:
                # Invalidate specific cache entry
                cache_path = self._get_cache_path(cache_type, **filters)
                meta_path = self._get_metadata_path(cache_path)
                
                if cache_path.exists():
                    cache_path.unlink()
                    count += 1
                if meta_path.exists():
                    meta_path.unlink()
                    
            elif cache_type:
                # Invalidate all entries of a specific type
                for cache_file in self.cache_dir.glob(f"{cache_type}_*.json"):
                    if not cache_file.name.endswith(".meta.json"):
                        cache_file.unlink()
                        count += 1
                        meta_file = self._get_metadata_path(cache_file)
                        if meta_file.exists():
                            meta_file.unlink()
            else:
                # Invalidate all cache
                for cache_file in self.cache_dir.glob("*.json"):
                    cache_file.unlink()
                    count += 1 if not cache_file.name.endswith(".meta.json") else 0
                    
            logger.info(f"Invalidated {count} cache entries")
            return count
            
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        if not self.enabled:
            return {"enabled": False}
            
        stats = {
            "enabled": True,
            "cache_dir": str(self.cache_dir),
            "cache_ttl": self.cache_ttl,
            "entries": {}
        }
        
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                if cache_file.name.endswith(".meta.json"):
                    continue
                    
                meta_path = self._get_metadata_path(cache_file)
                if meta_path.exists():
                    with open(meta_path, 'r') as f:
                        metadata = json.load(f)
                    
                    age = time.time() - metadata["timestamp"]
                    stats["entries"][cache_file.name] = {
                        "count": metadata["count"],
                        "age_seconds": age,
                        "expired": age > self.cache_ttl,
                        "cache_type": metadata.get("cache_type", "unknown")
                    }
                    
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            
        return stats