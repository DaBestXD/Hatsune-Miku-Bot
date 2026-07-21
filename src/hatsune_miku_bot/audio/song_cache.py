import asyncio
import logging
import time
from urllib.parse import parse_qs, urlsplit

logger = logging.getLogger(__name__)


class SongCache:
    def __init__(self) -> None:
        self.cache: dict[str, CachedSong] = {}
        self._lock = asyncio.Lock()

    async def get(self, cache_key: str) -> str | None:
        async with self._lock:
            cached_song = self.cache.get(cache_key)
            if cached_song and cached_song.expiry < time.time():
                logger.debug("Song cache returned expired song, deleting key")
                del self.cache[cache_key]
                return None
            if cached_song:
                logger.debug("Song cache get returned %s", cache_key)
                return cached_song.source
            else:
                logger.debug("Song cache get returned none for %s", cache_key)
                return None

    async def add_key(self, cached_song: str, source: CachedSong) -> None:
        async with self._lock:
            logger.debug("Added %s to song cache", cached_song)
            self.cache[cached_song] = source

    async def delete_key(self, cache_key: str) -> None:
        async with self._lock:
            key = self.cache.pop(cache_key, None)
            if not key:
                logger.debug("Failed to remove %s", cache_key)

    async def get_size(self) -> int:
        async with self._lock:
            return len(self.cache)

    async def clear_expired_songs(self) -> str | None:
        async with self._lock:
            for k, v in self.cache.copy().items():
                if v.expiry < time.time():
                    del self.cache[k]


class CachedSong:
    def __init__(self, source: str) -> None:
        self.source = source
        """
        Source taken from yt dlp direct link to stream from
        """
        self.expiry = self.get_expiry()

    def get_expiry(self) -> float:
        _DEFAULT_CACHE_LIFETIME_SECONDS = time.time() + 1800
        _CACHE_BUFFER = 300
        query = parse_qs(urlsplit(self.source).query)
        expiry_values = query.get("expire") or query.get("expires")
        if not expiry_values:
            return _DEFAULT_CACHE_LIFETIME_SECONDS
        try:
            expiry = int(expiry_values[0])
        except ValueError:
            logger.debug("Expiry returned non int value")
            return _DEFAULT_CACHE_LIFETIME_SECONDS
        return expiry - _CACHE_BUFFER
