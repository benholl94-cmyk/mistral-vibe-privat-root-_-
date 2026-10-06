"""
DataFetcher - Abruf von Live-Daten aus dem Web
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import asdict
from datetime import datetime
from typing import Any, Optional

import aiohttp

from vibe.core.realtime.models import (
    ContentType,
    FetchRequest,
    FetchResponse,
)
from vibe.core.realtime.cache import ResponseCache
from vibe.observability.logging import logger


class DataFetcher:
    """
    Abrufer für Live-Daten aus dem Web.
    
    Features:
    - HTTP/HTTPS-Anfragen
    - Automatische Wiederholungen
    - Caching
    - Timeout-Handling
    - Fehlerbehandlung
    """
    
    def __init__(self, cache: ResponseCache | None = None):
        self.cache = cache or ResponseCache()
        self._session: aiohttp.ClientSession | None = None
        self._default_headers = {
            "User-Agent": "Vibe DataFetcher/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
        }
    
    async def fetch(self, request: FetchRequest | str) -> FetchResponse:
        """
        Führt eine Fetch-Anfrage aus.
        
        Args:
            request: FetchRequest-Objekt oder URL-String
        
        Returns:
            FetchResponse mit den abgerufenen Daten
        """
        if isinstance(request, str):
            request = FetchRequest(url=request)
        
        start_time = time.time()
        
        # Cache prüfen
        cache_key = self._generate_cache_key(request)
        cached_response = self.cache.get(cache_key)
        if cached_response and not request.cache_ttl == 0:
            cached_response.cached = True
            cached_response.cache_key = cache_key
            return cached_response
        
        # Anfrage ausführen
        retries = 0
        last_error = None
        
        while retries <= request.max_retries:
            try:
                response = await self._do_fetch(request)
                
                # Bei Erfolg: Cache speichern und zurückgeben
                if response.status_code == 200:
                    self.cache.set(cache_key, response, ttl=request.cache_ttl)
                
                response.execution_time = time.time() - start_time
                response.cached = False
                response.cache_key = cache_key
                response.retries = retries
                
                return response
            
            except Exception as e:
                last_error = str(e)
                retries += 1
                if retries <= request.max_retries:
                    wait_time = min(2 ** retries, 10)  # Exponentielles Backoff
                    await asyncio.sleep(wait_time)
        
        # Alle Versuche fehlgeschlagen
        return FetchResponse(
            url=request.url,
            status_code=0,
            content="",
            execution_time=time.time() - start_time,
            cached=False,
            cache_key=cache_key,
            error=last_error,
            retries=retries,
        )
    
    async def _do_fetch(self, request: FetchRequest) -> FetchResponse:
        """Führt die eigentliche Fetch-Anfrage aus"""
        async with self._get_session() as session:
            # Header kombinieren
            headers = {**self._default_headers, **request.headers}
            
            # Anfrage ausführen
            async with session.request(
                method=request.method,
                url=request.url,
                headers=headers,
                params=request.params,
                data=request.data,
                timeout=aiohttp.ClientTimeout(total=request.timeout),
            ) as response:
                # Inhalt lesen
                content = await response.text()
                
                # Content-Type bestimmen
                content_type = ContentType.TEXT
                response_content_type = response.headers.get("Content-Type", "").lower()
                if "json" in response_content_type:
                    content_type = ContentType.JSON
                elif "html" in response_content_type:
                    content_type = ContentType.HTML
                elif "xml" in response_content_type:
                    content_type = ContentType.XML
                
                return FetchResponse(
                    url=request.url,
                    status_code=response.status,
                    content=content,
                    content_type=content_type,
                    headers=dict(response.headers),
                    timestamp=datetime.now(),
                )
    
    def _generate_cache_key(self, request: FetchRequest) -> str:
        """Generiert einen Cache-Schlüssel für die Anfrage"""
        key_data = f"{request.method}_{request.url}"
        if request.params:
            key_data += "_" + str(sorted(request.params.items()))
        if request.data:
            key_data += "_" + str(sorted(request.data.items()))
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    @asynccontextmanager
    async def _get_session(self) -> aiohttp.ClientSession:
        """Holt oder erstellt eine aiohttp-Session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60),
                headers=self._default_headers,
            )
        try:
            yield self._session
        except Exception:
            if self._session:
                await self._session.close()
                self._session = None
            raise
    
    async def fetch_multiple(self, urls: list[str], **kwargs) -> list[FetchResponse]:
        """Führt mehrere Fetch-Anfragen parallel aus"""
        tasks = [self.fetch(FetchRequest(url=url, **kwargs)) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def fetch_with_fallback(self, url: str, fallback_urls: list[str], **kwargs) -> FetchResponse:
        """
        Führt eine Fetch-Anfrage mit Fallback-URLs aus.
        
        Falls die Haupt-URL fehlschlägt, werden die Fallback-URLs nacheinander ausprobiert.
        """
        all_urls = [url] + fallback_urls
        
        for fallback_url in all_urls:
            response = await self.fetch(FetchRequest(url=fallback_url, **kwargs))
            if response.status_code == 200:
                return response
        
        # Alle URLs fehlgeschlagen
        return response  # Letzte Antwort (mit Fehler)
    
    async def fetch_json(self, url: str, **kwargs) -> dict | None:
        """Führt eine Fetch-Anfrage aus und parst das Ergebnis als JSON"""
        response = await self.fetch(FetchRequest(url=url, **kwargs))
        if response.status_code == 200 and response.content_type == ContentType.JSON:
            import json
            return json.loads(response.content)
        return None
    
    async def fetch_html(self, url: str, **kwargs) -> str | None:
        """Führt eine Fetch-Anfrage aus und gibt den HTML-Inhalt zurück"""
        response = await self.fetch(FetchRequest(url=url, **kwargs))
        if response.status_code == 200:
            return response.content
        return None
    
    async def fetch_text(self, url: str, **kwargs) -> str | None:
        """Führt eine Fetch-Anfrage aus und gibt den Text-Inhalt zurück"""
        response = await self.fetch(FetchRequest(url=url, **kwargs))
        if response.status_code == 200:
            return response.content
        return None


# Kontextmanager für async
from contextlib import asynccontextmanager
from typing import AsyncGenerator

@asynccontextmanager
async def get_data_fetcher_context() -> DataFetcher:
    """Erstellt einen DataFetcher im Kontextmanager"""
    fetcher = DataFetcher()
    try:
        yield fetcher
    finally:
        if fetcher._session:
            await fetcher._session.close()
