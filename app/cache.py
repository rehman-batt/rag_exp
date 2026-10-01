"""
In-Memory cache implementation for storing and retrieving data quickly.
"""

import hashlib
import time
from typing import Optional

class ResponseCache:
    def __init__(self, ttl: int = 300):
        self._cache = {}
        self.ttl = ttl
        self.hits = 0
        self.misses = 0

    def _generate_key(self, prompt: str) -> str:
        """
        Generate a unique key for the given prompt using SHA256 hashing.
        """
        return hashlib.sha256(prompt.lower().strip().encode()).hexdigest()

    def get(self, prompt: str) -> Optional[str]:
        """
        Retrieve the cached response for the given prompt if it exists and is not expired.
        """
        key = self._generate_key(prompt)
        entry = self._cache.get(key)

        if entry:
            response, timestamp, _ = entry
            if time.time() - timestamp < self.ttl:
                self.hits += 1
                return response
            else:
                # Remove expired entry
                del self._cache[key]

        self.misses += 1

        return None

    def set(self, prompt: str, response: str) -> None:
        """
        Store the response for the given prompt in the cache with the current timestamp.
        """
        key = self._generate_key(prompt)
        self._cache[key] = (response, time.time(), prompt)  # Store the prompt for reference

    def stats(self) -> dict:
        """
        Return cache statistics including hits, misses, and current cache size.
        """
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": len(self._cache)
        }
