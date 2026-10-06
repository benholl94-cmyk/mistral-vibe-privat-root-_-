"""
Echtzeit-Suche - Implementierung für Live-Websuchen
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import asdict
from datetime import datetime
from typing import Any, Optional

from vibe.core.realtime.models import (
    ContentType,
    SearchEngine,
    SearchQuery,
    SearchResult,
    SearchResultItem,
)
from vibe.core.realtime.cache import ResponseCache
from vibe.observability.logging import logger


class SearchProvider:
    """Basisklasse für Suchanbieter"""
    
    def __init__(self, engine: SearchEngine):
        self.engine = engine
        self.cache = ResponseCache()
    
    async def search(self, query: SearchQuery) -> SearchResult:
        """Führt eine Suche aus"""
        raise NotImplementedError(f"Search not implemented for {self.engine}")
    
    def _generate_cache_key(self, query: SearchQuery) -> str:
        """Generiert einen Cache-Schlüssel für die Abfrage"""
        key_data = f"{query.query}_{query.engine.value}_{query.language}_{query.region}"
        if query.site_filter:
            key_data += "_" + "_".join(sorted(query.site_filter))
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _calculate_trust_score(self, result: SearchResultItem, position: int) -> float:
        """Berechnet den Vertrauenswert für ein Suchergebnis"""
        # Basiswert basierend auf Position
        position_score = max(0.1, 1.0 - (position * 0.1))
        
        # Bonus für bestimmte Domains
        trusted_domains = [
            "github.com", "pypi.org", "python.org", "mistral.ai",
            "wikipedia.org", "eur-lex.europa.eu", "bundesregierung.de",
            "heise.de", "golem.de", "spiegel.de"
        ]
        domain_bonus = 0.2 if any(domain in result.url for domain in trusted_domains) else 0.0
        
        # Kombinierter Score
        return min(1.0, position_score + domain_bonus)


class GoogleSearchProvider(SearchProvider):
    """Google-Suchanbieter (über Custom Search JSON API)"""
    
    API_URL = "https://www.googleapis.com/customsearch/v1"
    
    def __init__(self, api_key: str | None = None, search_engine_id: str | None = None):
        super().__init__(SearchEngine.GOOGLE)
        self.api_key = api_key
        self.search_engine_id = search_engine_id
    
    async def search(self, query: SearchQuery) -> SearchResult:
        """Führt eine Google-Suche aus"""
        start_time = time.time()
        
        # Cache prüfen
        cache_key = self._generate_cache_key(query)
        cached_result = self.cache.get(cache_key)
        if cached_result and query.max_results <= len(cached_result.results):
            cached_result.cached = True
            cached_result.cache_key = cache_key
            return cached_result
        
        # API-Parameter
        params = {
            "key": self.api_key or "",
            "cx": self.search_engine_id or "",
            "q": query.query,
            "num": min(query.max_results, 10),  # Google erlaubt max. 10
            "lr": f"lang_{query.language}",
            "cr": query.region,
            "safe": "active" if query.safe_search else "off",
        }
        
        if query.time_range:
            params["dateRestrict"] = query.time_range
        
        if query.site_filter:
            params["siteSearch"] = " OR ".join(query.site_filter)
        
        # Suche ausführen
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(self.API_URL, params=params) as response:
                    if response.status != 200:
                        raise ValueError(f"Google API error: {response.status}")
                    
                    data = await response.json()
                    
                    # Ergebnisse verarbeiten
                    results = []
                    for idx, item in enumerate(data.get("items", [])):
                        result_item = SearchResultItem(
                            title=item.get("title", ""),
                            url=item.get("link", ""),
                            snippet=item.get("snippet", ""),
                            position=idx + 1,
                            engine=self.engine,
                            trust_score=self._calculate_trust_score(
                                SearchResultItem(
                                    title=item.get("title", ""),
                                    url=item.get("link", ""),
                                    snippet=item.get("snippet", ""),
                                    position=idx + 1,
                                    engine=self.engine,
                                ),
                                idx + 1
                            ),
                            metadata={
                                "displayLink": item.get("displayLink", ""),
                                "formattedUrl": item.get("formattedUrl", ""),
                            },
                        )
                        results.append(result_item)
                    
                    # Cache speichern
                    result = SearchResult(
                        query=query.query,
                        engine=self.engine,
                        results=results,
                        total_results=data.get("searchInformation", {}).get("totalResults", len(results)),
                        execution_time=time.time() - start_time,
                        cached=False,
                        cache_key=cache_key,
                        avg_trust_score=sum(r.trust_score for r in results) / len(results) if results else 0.0,
                        verified_count=sum(1 for r in results if r.is_verified),
                    )
                    
                    self.cache.set(cache_key, result, ttl=3600)  # 1 Stunde
                    return result
        
        except Exception as e:
            logger.error("Google search failed: %s", e, exc_info=True)
            # Fallback: Leere Ergebnisse
            return SearchResult(
                query=query.query,
                engine=self.engine,
                results=[],
                total_results=0,
                execution_time=time.time() - start_time,
                cached=False,
                error=str(e),
            )


class DuckDuckGoSearchProvider(SearchProvider):
    """DuckDuckGo-Suchanbieter (ohne API-Key erforderlich)"""
    
    API_URL = "https://api.duckduckgo.com/"
    
    def __init__(self):
        super().__init__(SearchEngine.DUCKDUCKGO)
    
    async def search(self, query: SearchQuery) -> SearchResult:
        """Führt eine DuckDuckGo-Suche aus"""
        start_time = time.time()
        
        # Cache prüfen
        cache_key = self._generate_cache_key(query)
        cached_result = self.cache.get(cache_key)
        if cached_result:
            cached_result.cached = True
            cached_result.cache_key = cache_key
            return cached_result
        
        try:
            import aiohttp
            params = {
                "q": query.query,
                "format": "json",
                "pretty": 1,
                "kl": query.language + "-" + query.region,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.API_URL, params=params) as response:
                    if response.status != 200:
                        raise ValueError(f"DuckDuckGo API error: {response.status}")
                    
                    data = await response.json()
                    
                    # Ergebnisse verarbeiten
                    results = []
                    for idx, item in enumerate(data.get("Results", [])):
                        result_item = SearchResultItem(
                            title=item.get("Title", ""),
                            url=item.get("Url", ""),
                            snippet=item.get("Abstract", ""),
                            position=idx + 1,
                            engine=self.engine,
                            trust_score=self._calculate_trust_score(
                                SearchResultItem(
                                    title=item.get("Title", ""),
                                    url=item.get("Url", ""),
                                    snippet=item.get("Abstract", ""),
                                    position=idx + 1,
                                    engine=self.engine,
                                ),
                                idx + 1
                            ),
                        )
                        results.append(result_item)
                    
                    result = SearchResult(
                        query=query.query,
                        engine=self.engine,
                        results=results,
                        total_results=len(results),
                        execution_time=time.time() - start_time,
                        cached=False,
                        cache_key=cache_key,
                        avg_trust_score=sum(r.trust_score for r in results) / len(results) if results else 0.0,
                        verified_count=sum(1 for r in results if r.is_verified),
                    )
                    
                    self.cache.set(cache_key, result, ttl=3600)
                    return result
        
        except Exception as e:
            logger.error("DuckDuckGo search failed: %s", e, exc_info=True)
            return SearchResult(
                query=query.query,
                engine=self.engine,
                results=[],
                total_results=0,
                execution_time=time.time() - start_time,
                cached=False,
                error=str(e),
            )


class RealTimeSearch:
    """
    Hauptklasse für Echtzeit-Suchen.
    
    Unterstützt mehrere Suchanbieter mit Fallback-Logik.
    """
    
    def __init__(self):
        self.providers = {
            SearchEngine.GOOGLE: GoogleSearchProvider(),
            SearchEngine.DUCKDUCKGO: DuckDuckGoSearchProvider(),
        }
        self.cache = ResponseCache()
    
    async def search(self, query: SearchQuery | str) -> SearchResult:
        """
        Führt eine Suche aus.
        
        Args:
            query: Suchanfrage (String oder SearchQuery-Objekt)
        
        Returns:
            SearchResult mit den Suchergebnissen
        """
        if isinstance(query, str):
            query = SearchQuery(query=query)
        
        # Primären Anbieter verwenden
        provider = self.providers.get(query.engine)
        if provider:
            return await provider.search(query)
        
        # Fallback: DuckDuckGo
        fallback_provider = self.providers.get(SearchEngine.DUCKDUCKGO)
        if fallback_provider:
            query.engine = SearchEngine.DUCKDUCKGO
            return await fallback_provider.search(query)
        
        # Kein Anbieter verfügbar
        return SearchResult(
            query=query.query,
            engine=query.engine,
            results=[],
            total_results=0,
            execution_time=0.0,
            error="Kein Suchanbieter verfügbar",
        )
    
    async def search_multiple_engines(self, query: str, engines: list[SearchEngine] | None = None) -> dict[SearchEngine, SearchResult]:
        """Führt eine Suche mit mehreren Suchmaschinen aus"""
        if engines is None:
            engines = list(self.providers.keys())
        
        results = {}
        for engine in engines:
            provider = self.providers.get(engine)
            if provider:
                result = await provider.search(SearchQuery(query=query, engine=engine))
                results[engine] = result
        
        return results
    
    async def get_consensus_result(self, query: str, min_engines: int = 2) -> SearchResult:
        """
        Erhält ein Konsens-Ergebnis von mehreren Suchmaschinen.
        
        Nur Ergebnisse, die in mindestens min_engines vorkommen, werden zurückgegeben.
        """
        # Suche mit allen verfügbaren Engines
        all_results = await self.search_multiple_engines(query)
        
        if len(all_results) < min_engines:
            return SearchResult(
                query=query,
                engine=SearchEngine.GOOGLE,  # Standard
                results=[],
                error=f"Mindestens {min_engines} Suchmaschinen erforderlich, nur {len(all_results)} verfügbar",
            )
        
        # Sammle alle URLs
        url_counts = {}
        all_items = []
        for engine, result in all_results.items():
            for item in result.results:
                if item.url not in url_counts:
                    url_counts[item.url] = 0
                url_counts[item.url] += 1
                all_items.append(item)
        
        # Filtere nach Konsens
        consensus_items = []
        for item in all_items:
            if url_counts.get(item.url, 0) >= min_engines:
                # Berechne durchschnittlichen Vertrauenswert
                avg_trust = sum(
                    i.trust_score for i in all_items 
                    if i.url == item.url
                ) / url_counts[item.url]
                
                # Erstelle konsolidiertes Item
                consensus_item = SearchResultItem(
                    title=item.title,
                    url=item.url,
                    snippet=item.snippet,
                    position=len(consensus_items) + 1,
                    engine=SearchEngine("consensus"),
                    trust_score=avg_trust,
                    is_verified=all(i.is_verified for i in all_items if i.url == item.url),
                )
                consensus_items.append(consensus_item)
        
        # Sortiere nach Vertrauenswert
        consensus_items.sort(key=lambda x: x.trust_score, reverse=True)
        
        return SearchResult(
            query=query,
            engine=SearchEngine("consensus"),
            results=consensus_items,
            total_results=len(consensus_items),
            execution_time=sum(r.execution_time for r in all_results.values()),
            cached=False,
            avg_trust_score=sum(i.trust_score for i in consensus_items) / len(consensus_items) if consensus_items else 0.0,
            verified_count=sum(1 for i in consensus_items if i.is_verified),
        )
