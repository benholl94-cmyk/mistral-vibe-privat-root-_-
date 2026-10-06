"""
Datenmodelle für das Vertrauenssystem
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TrustLevel(StrEnum):
    """Vertrauensstufen"""
    UNTRUSTED = "untrusted"      # 0.0 - 0.2
    LOW = "low"                  # 0.2 - 0.4
    NEUTRAL = "neutral"          # 0.4 - 0.6
    TRUSTED = "trusted"          # 0.6 - 0.8
    HIGHLY_TRUSTED = "highly_trusted"  # 0.8 - 1.0


class TrustType(StrEnum):
    """Typen von Vertrauensbeziehungen"""
    SOURCE = "source"            # Quelle
    USER = "user"                # Benutzer
    CONTENT = "content"          # Inhalt
    SYSTEM = "system"            # Systemkomponente


@dataclass
class TrustScore:
    """Vertrauenswert für eine Entität"""
    entity_id: str
    entity_type: TrustType
    score: float = 0.5  # 0.0 bis 1.0
    level: TrustLevel = TrustLevel.NEUTRAL
    last_updated: datetime = field(default_factory=datetime.now)
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "score": self.score,
            "level": self.level.value,
            "last_updated": self.last_updated.isoformat(),
            "evidence": self.evidence,
            "metadata": self.metadata,
        }
    
    def update_level(self) -> None:
        """Aktualisiert das Level basierend auf dem Score"""
        if self.score >= 0.8:
            self.level = TrustLevel.HIGHLY_TRUSTED
        elif self.score >= 0.6:
            self.level = TrustLevel.TRUSTED
        elif self.score >= 0.4:
            self.level = TrustLevel.NEUTRAL
        elif self.score >= 0.2:
            self.level = TrustLevel.LOW
        else:
            self.level = TrustLevel.UNTRUSTED


@dataclass
class TrustRelationship:
    """Vertrauensbeziehung zwischen zwei Entitäten"""
    source_id: str
    source_type: TrustType
    target_id: str
    target_type: TrustType
    trust_score: float = 0.5  # 0.0 bis 1.0
    relationship_type: str = "default"
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "target_id": self.target_id,
            "target_type": self.target_type.value,
            "trust_score": self.trust_score,
            "relationship_type": self.relationship_type,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class TrustNetwork:
    """Vertrauensnetzwerk"""
    name: str
    description: str = ""
    entities: list[str] = field(default_factory=list)
    relationships: list[TrustRelationship] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "entities": self.entities,
            "relationships": [r.to_dict() for r in self.relationships],
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }


# Pydantic-Modelle für API-Kompatibilität
class TrustScoreModel(BaseModel):
    entity_id: str = Field(..., description="ID der Entität")
    entity_type: TrustType = Field(..., description="Typ der Entität")
    score: float = Field(default=0.5, ge=0.0, le=1.0, description="Vertrauenswert")
    level: TrustLevel = Field(default=TrustLevel.NEUTRAL, description="Vertrauenslevel")
    last_updated: datetime = Field(default_factory=datetime.now, description="Letzte Aktualisierung")
    evidence: list[str] = Field(default_factory=list, description="Beweise")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadaten")


class TrustRelationshipModel(BaseModel):
    source_id: str = Field(..., description="ID der Quelle")
    source_type: TrustType = Field(..., description="Typ der Quelle")
    target_id: str = Field(..., description="ID des Ziels")
    target_type: TrustType = Field(..., description="Typ des Ziels")
    trust_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Vertrauenswert")
    relationship_type: str = Field(default="default", description="Typ der Beziehung")
    created_at: datetime = Field(default_factory=datetime.now, description="Erstellungsdatum")
    last_updated: datetime = Field(default_factory=datetime.now, description="Letzte Aktualisierung")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadaten")


class TrustNetworkModel(BaseModel):
    name: str = Field(..., description="Name des Netzwerks")
    description: str = Field(default="", description="Beschreibung")
    entities: list[str] = Field(default_factory=list, description="Entitäten im Netzwerk")
    relationships: list[TrustRelationshipModel] = Field(default_factory=list, description="Beziehungen")
    created_at: datetime = Field(default_factory=datetime.now, description="Erstellungsdatum")
    last_updated: datetime = Field(default_factory=datetime.now, description="Letzte Aktualisierung")
