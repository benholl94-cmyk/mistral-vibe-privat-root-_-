"""
Datenmodelle für die Wissensdatenbank
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class KnowledgeCategory(StrEnum):
    """Kategorien für Wissenseinträge"""
    NEWS = "news"
    TECHNOLOGY = "technology"
    LEGAL = "legal"
    SECURITY = "security"
    SCIENCE = "science"
    BUSINESS = "business"
    HEALTH = "health"
    GENERAL = "general"


class KnowledgeSourceType(StrEnum):
    """Typen von Wissensquellen"""
    OFFICIAL = "official"      # Offizielle Quellen (z.B. Regierungen, Unternehmen)
    COMMUNITY = "community"    # Community-Beiträge
    WEB = "web"                # Web-Suche
    API = "api"                # API-basierte Daten
    MANUAL = "manual"          # Manuell hinzugefügt


@dataclass
class KnowledgeSource:
    """Quelle eines Wissenseintrags"""
    id: str
    name: str
    url: str
    source_type: KnowledgeSourceType
    trust_score: float = 0.5  # 0.0 bis 1.0
    last_updated: datetime = field(default_factory=datetime.now)
    description: str = ""
    is_active: bool = True


@dataclass
class KnowledgeEntry:
    """Ein einzelner Wissenseintrag"""
    id: str
    title: str
    content: str
    category: KnowledgeCategory
    source: KnowledgeSource
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Vertrauens- und Qualitätsmetriken
    confidence: float = 0.5  # 0.0 bis 1.0
    verification_status: str = "unverified"  # unverified, verified, disputed
    verification_count: int = 0
    last_verified: Optional[datetime] = None
    
    # Aktualitätsmetriken
    is_current: bool = True
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category.value,
            "source": self.source.to_dict() if hasattr(self.source, 'to_dict') else str(self.source),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "tags": self.tags,
            "metadata": self.metadata,
            "confidence": self.confidence,
            "verification_status": self.verification_status,
            "verification_count": self.verification_count,
            "last_verified": self.last_verified.isoformat() if self.last_verified else None,
            "is_current": self.is_current,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class KnowledgeQuery:
    """Abfrage an die Wissensdatenbank"""
    query: str
    categories: list[KnowledgeCategory] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    max_results: int = 10
    min_confidence: float = 0.0
    include_expired: bool = False
    sort_by: str = "relevance"  # relevance, date, confidence


@dataclass
class KnowledgeResult:
    """Ergebnis einer Wissensabfrage"""
    query: str
    results: list[KnowledgeEntry] = field(default_factory=list)
    total_results: int = 0
    sources_used: list[str] = field(default_factory=list)
    execution_time: float = 0.0
    cached: bool = False
    
    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "total_results": self.total_results,
            "sources_used": self.sources_used,
            "execution_time": self.execution_time,
            "cached": self.cached,
        }


# Pydantic-Modelle für API-Kompatibilität
class KnowledgeSourceModel(BaseModel):
    id: str = Field(..., description="Einzigartige ID der Quelle")
    name: str = Field(..., description="Name der Quelle")
    url: str = Field(..., description="URL der Quelle")
    source_type: KnowledgeSourceType = Field(..., description="Typ der Quelle")
    trust_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Vertrauenswert (0.0-1.0)")
    last_updated: datetime = Field(default_factory=datetime.now, description="Letzte Aktualisierung")
    description: str = Field(default="", description="Beschreibung der Quelle")
    is_active: bool = Field(default=True, description="Ist die Quelle aktiv?")


class KnowledgeEntryModel(BaseModel):
    id: str = Field(..., description="Einzigartige ID des Eintrags")
    title: str = Field(..., description="Titel des Eintrags")
    content: str = Field(..., description="Inhalt des Eintrags")
    category: KnowledgeCategory = Field(..., description="Kategorie des Eintrags")
    source: KnowledgeSourceModel = Field(..., description="Quelle des Eintrags")
    created_at: datetime = Field(default_factory=datetime.now, description="Erstellungsdatum")
    updated_at: datetime = Field(default_factory=datetime.now, description="Letzte Aktualisierung")
    version: int = Field(default=1, ge=1, description="Version des Eintrags")
    tags: list[str] = Field(default_factory=list, description="Tags für den Eintrag")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadaten")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Vertrauenswert (0.0-1.0)")
    verification_status: str = Field(default="unverified", description="Verifizierungsstatus")
    verification_count: int = Field(default=0, ge=0, description="Anzahl der Verifizierungen")
    last_verified: Optional[datetime] = Field(default=None, description="Letzte Verifizierung")
    is_current: bool = Field(default=True, description="Ist der Eintrag aktuell?")
    expires_at: Optional[datetime] = Field(default=None, description="Ablaufdatum")


class KnowledgeQueryModel(BaseModel):
    query: str = Field(..., description="Suchbegriff")
    categories: list[KnowledgeCategory] = Field(default_factory=list, description="Kategorienfilter")
    sources: list[str] = Field(default_factory=list, description="Quellenfilter")
    max_results: int = Field(default=10, ge=1, le=100, description="Maximale Anzahl Ergebnisse")
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Mindest-Vertrauenswert")
    include_expired: bool = Field(default=False, description="Abgelaufene Einträge einbeziehen?")
    sort_by: str = Field(default="relevance", description="Sortierkriterium")


class KnowledgeResultModel(BaseModel):
    query: str = Field(..., description="Originale Abfrage")
    results: list[KnowledgeEntryModel] = Field(default_factory=list, description="Ergebnisse")
    total_results: int = Field(default=0, ge=0, description="Gesamtzahl der Ergebnisse")
    sources_used: list[str] = Field(default_factory=list, description="Verwendete Quellen")
    execution_time: float = Field(default=0.0, ge=0.0, description="Ausführungszeit in Sekunden")
    cached: bool = Field(default=False, description="Wurde das Ergebnis gecacht?")
