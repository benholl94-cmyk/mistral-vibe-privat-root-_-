"""
Datenmodelle für Echtzeit-Datenabruf
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SearchEngine(StrEnum):
    """Unterstützte Suchmaschinen"""
    GOOGLE = "google"
    BING = "bing"
    DUCKDUCKGO = "duckduckgo"
    BRAVE = "brave"


class ContentType(StrEnum):
    """Inhaltstypen für Suchergebnisse"""
    TEXT = "text"
    HTML = "html"
    JSON = "json"
    XML = "xml"
    MARKDOWN = "markdown"


@dataclass
class SearchQuery:
    """Abfrage für die Echtzeit-Suche"""
    query: str
    engine: SearchEngine = SearchEngine.GOOGLE
    max_results: int = 10
    safe_search: bool = True
    language: str = "de"
    region: str = "de"
    time_range: Optional[str] = None  # "day", "week", "month", "year"
    site_filter: Optional[list[str]] = None  # z.B. ["github.com", "pypi.org"]
    exclude_sites: Optional[list[str]] = None
    
    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "engine": self.engine.value,
            "max_results": self.max_results,
            "safe_search": self.safe_search,
            "language": self.language,
            "region": self.region,
            "time_range": self.time_range,
            "site_filter": self.site_filter,
            "exclude_sites": self.exclude_sites,
        }


@dataclass
class SearchResultItem:
    """Ein einzelnes Suchergebnis"""
    title: str
    url: str
    snippet: str
    position: int
    engine: SearchEngine
    content_type: ContentType = ContentType.TEXT
    cached_content: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Vertrauens- und Qualitätsmetriken
    trust_score: float = 0.5
    is_verified: bool = False
    verification_sources: list[str] = field(default_factory=list)
    
    # Aktualität
    published_date: Optional[datetime] = None
    last_crawled: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "position": self.position,
            "engine": self.engine.value,
            "content_type": self.content_type.value,
            "cached_content": self.cached_content,
            "metadata": self.metadata,
            "trust_score": self.trust_score,
            "is_verified": self.is_verified,
            "verification_sources": self.verification_sources,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "last_crawled": self.last_crawled.isoformat() if self.last_crawled else None,
        }


@dataclass
class SearchResult:
    """Ergebnis einer Suchanfrage"""
    query: str
    engine: SearchEngine
    results: list[SearchResultItem] = field(default_factory=list)
    total_results: int = 0
    execution_time: float = 0.0
    cached: bool = False
    cache_key: Optional[str] = None
    
    # Aggregierte Metriken
    avg_trust_score: float = 0.0
    verified_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "engine": self.engine.value,
            "results": [r.to_dict() for r in self.results],
            "total_results": self.total_results,
            "execution_time": self.execution_time,
            "cached": self.cached,
            "cache_key": self.cache_key,
            "avg_trust_score": self.avg_trust_score,
            "verified_count": self.verified_count,
        }


@dataclass
class FetchRequest:
    """Anfrage zum Abruf von Daten"""
    url: str
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    data: Optional[dict[str, Any]] = None
    timeout: int = 30
    max_retries: int = 3
    cache_ttl: int = 3600  # 1 Stunde in Sekunden
    
    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "method": self.method,
            "headers": self.headers,
            "params": self.params,
            "data": self.data,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "cache_ttl": self.cache_ttl,
        }


@dataclass
class FetchResponse:
    """Antwort auf eine Fetch-Anfrage"""
    url: str
    status_code: int
    content: str
    content_type: ContentType = ContentType.TEXT
    headers: dict[str, str] = field(default_factory=dict)
    execution_time: float = 0.0
    cached: bool = False
    cache_key: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Fehlerbehandlung
    error: Optional[str] = None
    retries: int = 0
    
    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "status_code": self.status_code,
            "content": self.content,
            "content_type": self.content_type.value,
            "headers": self.headers,
            "execution_time": self.execution_time,
            "cached": self.cached,
            "cache_key": self.cache_key,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
            "retries": self.retries,
        }


# Pydantic-Modelle für API-Kompatibilität
class SearchQueryModel(BaseModel):
    query: str = Field(..., description="Suchbegriff")
    engine: SearchEngine = Field(default=SearchEngine.GOOGLE, description="Suchmaschine")
    max_results: int = Field(default=10, ge=1, le=100, description="Maximale Ergebnisse")
    safe_search: bool = Field(default=True, description="Sichere Suche aktivieren")
    language: str = Field(default="de", description="Sprache der Ergebnisse")
    region: str = Field(default="de", description="Region für die Suche")
    time_range: Optional[str] = Field(default=None, description="Zeitraum (day/week/month/year)")
    site_filter: Optional[list[str]] = Field(default=None, description="Site-Filter")
    exclude_sites: Optional[list[str]] = Field(default=None, description="Ausgeschlossene Sites")


class SearchResultItemModel(BaseModel):
    title: str = Field(..., description="Titel des Ergebnisses")
    url: str = Field(..., description="URL des Ergebnisses")
    snippet: str = Field(..., description="Auszug aus dem Ergebnis")
    position: int = Field(..., ge=1, description="Position in den Ergebnissen")
    engine: SearchEngine = Field(..., description="Verwendete Suchmaschine")
    content_type: ContentType = Field(default=ContentType.TEXT, description="Inhaltstyp")
    cached_content: Optional[str] = Field(default=None, description="Gecachter Inhalt")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadaten")
    trust_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Vertrauenswert")
    is_verified: bool = Field(default=False, description="Ist verifiziert?")
    verification_sources: list[str] = Field(default_factory=list, description="Verifizierungsquellen")
    published_date: Optional[datetime] = Field(default=None, description="Veröffentlichungsdatum")
    last_crawled: Optional[datetime] = Field(default=None, description="Letzte Crawl-Datum")


class SearchResultModel(BaseModel):
    query: str = Field(..., description="Originale Abfrage")
    engine: SearchEngine = Field(..., description="Verwendete Suchmaschine")
    results: list[SearchResultItemModel] = Field(default_factory=list, description="Suchergebnisse")
    total_results: int = Field(default=0, ge=0, description="Gesamtzahl der Ergebnisse")
    execution_time: float = Field(default=0.0, ge=0.0, description="Ausführungszeit")
    cached: bool = Field(default=False, description="Wurde gecacht?")
    cache_key: Optional[str] = Field(default=None, description="Cache-Schlüssel")
    avg_trust_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Durchschnittlicher Vertrauenswert")
    verified_count: int = Field(default=0, ge=0, description="Anzahl verifizierter Ergebnisse")


class FetchRequestModel(BaseModel):
    url: str = Field(..., description="URL zum Abrufen")
    method: str = Field(default="GET", description="HTTP-Methode")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP-Header")
    params: dict[str, Any] = Field(default_factory=dict, description="URL-Parameter")
    data: Optional[dict[str, Any]] = Field(default=None, description="Request-Body")
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout in Sekunden")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximale Wiederholungen")
    cache_ttl: int = Field(default=3600, ge=0, description="Cache-TTL in Sekunden")


class FetchResponseModel(BaseModel):
    url: str = Field(..., description="Abgerufene URL")
    status_code: int = Field(..., ge=100, le=599, description="HTTP-Statuscode")
    content: str = Field(..., description="Inhalt der Antwort")
    content_type: ContentType = Field(default=ContentType.TEXT, description="Inhaltstyp")
    headers: dict[str, str] = Field(default_factory=dict, description="Response-Header")
    execution_time: float = Field(default=0.0, ge=0.0, description="Ausführungszeit")
    cached: bool = Field(default=False, description="Wurde gecacht?")
    cache_key: Optional[str] = Field(default=None, description="Cache-Schlüssel")
    timestamp: datetime = Field(default_factory=datetime.now, description="Zeitstempel")
    error: Optional[str] = Field(default=None, description="Fehlermeldung")
    retries: int = Field(default=0, ge=0, description="Anzahl der Wiederholungen")
