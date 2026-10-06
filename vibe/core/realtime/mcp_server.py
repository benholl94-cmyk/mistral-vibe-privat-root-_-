"""
MCP Server für Live-Daten - Integration mit Model Context Protocol

Dieser Server bietet Echtzeit-Datenabruf über das MCP-Protokoll.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import TextContent, ImageContent, EmbeddedResource, Tool

from vibe.core.knowledge.database import KnowledgeDatabase
from vibe.core.realtime.search import RealTimeSearch
from vibe.core.realtime.fetcher import DataFetcher
from vibe.core.realtime.cache import ResponseCache
from vibe.core.verification.pipeline import FactCheckPipeline
from vibe.observability.logging import logger


# Global instances
_knowledge_db: KnowledgeDatabase | None = None
_realtime_search: RealTimeSearch | None = None
_data_fetcher: DataFetcher | None = None
_factcheck_pipeline: FactCheckPipeline | None = None


def get_knowledge_db() -> KnowledgeDatabase:
    """Holt die globale Wissensdatenbank-Instanz"""
    global _knowledge_db
    if _knowledge_db is None:
        _knowledge_db = KnowledgeDatabase()
    return _knowledge_db


def get_realtime_search() -> RealTimeSearch:
    """Holt die globale Echtzeit-Suchinstanz"""
    global _realtime_search
    if _realtime_search is None:
        _realtime_search = RealTimeSearch()
    return _realtime_search


def get_data_fetcher() -> DataFetcher:
    """Holt die globale DataFetcher-Instanz"""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = DataFetcher()
    return _data_fetcher


def get_factcheck_pipeline() -> FactCheckPipeline:
    """Holt die globale FactCheck-Pipeline-Instanz"""
    global _factcheck_pipeline
    if _factcheck_pipeline is None:
        _factcheck_pipeline = FactCheckPipeline()
    return _factcheck_pipeline


app = Server("vibe-realtime-server")


@app.tool()
async def search_web(query: str, max_results: int = 10, engine: str = "duckduckgo") -> list[dict]:
    """
    Führt eine Websuche in Echtzeit aus.
    
    Args:
        query: Suchbegriff
        max_results: Maximale Anzahl Ergebnisse (1-100)
        engine: Suchmaschine (google, duckduckgo, bing)
    
    Returns:
        Liste von Suchergebnissen mit Titel, URL, Snippet und Vertrauenswert
    """
    from vibe.core.realtime.models import SearchQuery, SearchEngine
    
    try:
        search_engine = SearchEngine(engine.lower())
        search = get_realtime_search()
        
        result = await search.search(SearchQuery(
            query=query,
            engine=search_engine,
            max_results=max_results,
        ))
        
        return [
            {
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet,
                "position": item.position,
                "engine": item.engine.value,
                "trust_score": item.trust_score,
                "is_verified": item.is_verified,
            }
            for item in result.results
        ]
    except Exception as e:
        logger.error("Web search failed: %s", e, exc_info=True)
        return [{"error": str(e)}]


@app.tool()
async def fetch_url(url: str, timeout: int = 30) -> dict:
    """
    Lädt den Inhalt einer URL.
    
    Args:
        url: URL zum Abrufen
        timeout: Timeout in Sekunden
    
    Returns:
        Dictionary mit Statuscode, Inhalt und Metadaten
    """
    from vibe.core.realtime.models import FetchRequest
    
    try:
        fetcher = get_data_fetcher()
        response = await fetcher.fetch(FetchRequest(
            url=url,
            timeout=timeout,
        ))
        
        return {
            "url": response.url,
            "status_code": response.status_code,
            "content": response.content[:10000],  # Max. 10.000 Zeichen
            "content_type": response.content_type.value,
            "execution_time": response.execution_time,
            "cached": response.cached,
        }
    except Exception as e:
        logger.error("URL fetch failed: %s", e, exc_info=True)
        return {"error": str(e), "url": url}


@app.tool()
async def get_knowledge(query: str, category: str = "", max_results: int = 10) -> list[dict]:
    """
    Durchsucht die lokale Wissensdatenbank.
    
    Args:
        query: Suchbegriff
        category: Kategorie (news, technology, legal, etc.)
        max_results: Maximale Anzahl Ergebnisse
    
    Returns:
        Liste von Wissenseinträgen
    """
    from vibe.core.knowledge.models import KnowledgeQuery, KnowledgeCategory
    
    try:
        db = get_knowledge_db()
        
        # Konvertiere Kategorie-String zu Enum
        category_enum = None
        if category:
            try:
                category_enum = KnowledgeCategory(category.lower())
            except ValueError:
                pass
        
        result = db.query_entries(KnowledgeQuery(
            query=query,
            categories=[category_enum] if category_enum else [],
            max_results=max_results,
        ))
        
        return [
            {
                "id": entry.id,
                "title": entry.title,
                "content": entry.content[:500],  # Max. 500 Zeichen
                "category": entry.category.value,
                "source": entry.source.name,
                "confidence": entry.confidence,
                "is_current": entry.is_current,
                "created_at": entry.created_at.isoformat(),
                "updated_at": entry.updated_at.isoformat(),
            }
            for entry in result.results
        ]
    except Exception as e:
        logger.error("Knowledge query failed: %s", e, exc_info=True)
        return [{"error": str(e)}]


@app.tool()
async def verify_claim(claim: str, context: str = "") -> dict:
    """
    Verifiziert eine Behauptung.
    
    Args:
        claim: Zu überprüfende Behauptung
        context: Optionaler Kontext
    
    Returns:
        Verifizierungsergebnis mit Status, Vertrauenswert und Beweisen
    """
    from vibe.core.verification.models import Claim
    
    try:
        pipeline = get_factcheck_pipeline()
        result = await pipeline.verify_simple(claim, context)
        
        return {
            "claim": claim,
            "status": result.status.value,
            "confidence": result.confidence,
            "confidence_level": result.confidence_level.value,
            "is_reliable": result.is_reliable,
            "is_false": result.is_false,
            "supporting_evidence": result.supporting_evidence,
            "contradicting_evidence": result.contradicting_evidence,
            "consensus_score": result.consensus_score,
            "sources_used": result.sources_used,
            "execution_time": result.execution_time,
            "notes": result.notes,
        }
    except Exception as e:
        logger.error("Claim verification failed: %s", e, exc_info=True)
        return {"error": str(e), "claim": claim}


@app.tool()
async def get_latest_news(category: str = "", max_results: int = 10) -> list[dict]:
    """
    Holt die neuesten Nachrichten aus der Wissensdatenbank.
    
    Args:
        category: Kategorie (news, technology, etc.)
        max_results: Maximale Anzahl Ergebnisse
    
    Returns:
        Liste der neuesten Einträge
    """
    from vibe.core.knowledge.models import KnowledgeCategory
    
    try:
        db = get_knowledge_db()
        
        # Konvertiere Kategorie-String zu Enum
        category_enum = None
        if category:
            try:
                category_enum = KnowledgeCategory(category.lower())
            except ValueError:
                pass
        
        if category_enum:
            entries = db.get_entries_by_category(category_enum, max_results)
        else:
            entries = db.get_latest_entries(max_results)
        
        return [
            {
                "id": entry.id,
                "title": entry.title,
                "content": entry.content[:200],  # Max. 200 Zeichen
                "category": entry.category.value,
                "source": entry.source.name,
                "published_date": entry.created_at.isoformat(),
                "confidence": entry.confidence,
            }
            for entry in entries
        ]
    except Exception as e:
        logger.error("Failed to get latest news: %s", e, exc_info=True)
        return [{"error": str(e)}]


@app.tool()
async def get_source_info(url: str) -> dict:
    """
    Holt Informationen über eine Quelle.
    
    Args:
        url: URL der Quelle
    
    Returns:
        Informationen über die Quelle (Vertrauenswert, Typ, etc.)
    """
    from vibe.core.verification.validator import InformationValidator
    
    try:
        validator = InformationValidator()
        result = validator.validate_source(url)
        
        return {
            "url": url,
            "is_valid": result.is_valid,
            "trust_score": result.score,
            "trust_level": validator.get_source_trust_level(url),
            "issues": result.issues,
            "suggestions": result.suggestions,
        }
    except Exception as e:
        logger.error("Source validation failed: %s", e, exc_info=True)
        return {"error": str(e), "url": url}


@app.tool()
async def check_consensus(query: str, min_sources: int = 2) -> dict:
    """
    Prüft auf Konsens zwischen mehreren Quellen.
    
    Args:
        query: Suchbegriff
        min_sources: Minimale Anzahl Quellen für Konsens
    
    Returns:
        Konsens-Ergebnis mit Status und Score
    """
    try:
        search = get_realtime_search()
        result = await search.get_consensus_result(query, min_sources)
        
        return {
            "query": query,
            "total_results": result.total_results,
            "consensus_results": [
                {
                    "title": item.title,
                    "url": item.url,
                    "trust_score": item.trust_score,
                }
                for item in result.results
            ],
            "avg_trust_score": result.avg_trust_score,
            "verified_count": result.verified_count,
            "execution_time": result.execution_time,
        }
    except Exception as e:
        logger.error("Consensus check failed: %s", e, exc_info=True)
        return {"error": str(e), "query": query}


@app.tool()
async def get_stats() -> dict:
    """
    Holt Statistiken zum Realtime-Server.
    
    Returns:
        Statistiken zu Cache, Datenbank und Leistung
    """
    try:
        db = get_knowledge_db()
        cache = ResponseCache()
        
        db_stats = db.get_stats()
        cache_stats = cache.get_stats()
        
        return {
            "knowledge_db": db_stats,
            "cache": cache_stats,
            "tools": [
                "search_web",
                "fetch_url", 
                "get_knowledge",
                "verify_claim",
                "get_latest_news",
                "get_source_info",
                "check_consensus",
                "get_stats",
            ],
        }
    except Exception as e:
        logger.error("Failed to get stats: %s", e, exc_info=True)
        return {"error": str(e)}


@app.tool()
async def health_check() -> dict:
    """
    Führt einen Health-Check des Servers aus.
    
    Returns:
        Status aller Komponenten
    """
    try:
        # Teste Wissensdatenbank
        db = get_knowledge_db()
        db_stats = db.get_stats()
        db_healthy = db_stats["total_entries"] >= 0
        
        # Teste Cache
        cache = ResponseCache()
        cache_stats = cache.get_stats()
        cache_healthy = cache_stats["memory_entries"] >= 0
        
        # Teste Suchfunktionalität
        search = get_realtime_search()
        test_result = await search.search("test query")
        search_healthy = test_result.total_results >= 0
        
        # Teste Fetcher
        fetcher = get_data_fetcher()
        test_fetch = await fetcher.fetch("https://httpbin.org/get")
        fetcher_healthy = test_fetch.status_code == 200
        
        return {
            "status": "healthy" if all([db_healthy, cache_healthy, search_healthy, fetcher_healthy]) else "degraded",
            "components": {
                "knowledge_db": "healthy" if db_healthy else "unhealthy",
                "cache": "healthy" if cache_healthy else "unhealthy",
                "search": "healthy" if search_healthy else "unhealthy",
                "fetcher": "healthy" if fetcher_healthy else "unhealthy",
            },
            "details": {
                "knowledge_db": db_stats,
                "cache": cache_stats,
            },
        }
    except Exception as e:
        logger.error("Health check failed: %s", e, exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
        }


# Server Initialisierung
@app.init
async def on_init(options: InitializationOptions):
    """Initialisierungs-Hook"""
    logger.info("Vibe Realtime Server initialized with options: %s", options)
    
    # Initialisiere Komponenten
    get_knowledge_db()
    get_realtime_search()
    get_data_fetcher()
    get_factcheck_pipeline()
    
    return {"protocolVersion": "2024-11-05", "capabilities": app.capabilities}


# Server-Informationen
@app.get_resources
def list_resources() -> list[EmbeddedResource]:
    """Listet verfügbare Ressourcen auf"""
    return [
        EmbeddedResource(
            uri="vibe://realtime/knowledge",
            mimeType="application/json",
            name="Knowledge Database",
            description="Lokale Wissensdatenbank mit aktuellen Informationen",
        ),
        EmbeddedResource(
            uri="vibe://realtime/search",
            mimeType="application/json", 
            name="Web Search",
            description="Echtzeit-Websuche",
        ),
        EmbeddedResource(
            uri="vibe://realtime/fetcher",
            mimeType="application/json",
            name="Data Fetcher",
            description="Abruf von Live-Daten aus dem Web",
        ),
    ]


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Vibe Realtime MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host-Adresse")
    parser.add_argument("--port", type=int, default=8080, help="Port")
    args = parser.parse_args()
    
    # Starte den Server
    async def run_server():
        await app.run_stdio()
    
    asyncio.run(run_server())
