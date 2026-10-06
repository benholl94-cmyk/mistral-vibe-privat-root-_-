"""
Datenmodelle für die Verifizierung von Informationen
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, Field


class VerificationStatus(StrEnum):
    """Status der Verifizierung"""
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    FALSE = "false"
    PARTIALLY_TRUE = "partially_true"


class EvidenceType(StrEnum):
    """Typen von Beweisen"""
    SOURCE = "source"          # Offizielle Quelle
    COMMUNITY = "community"    # Community-Bestätigung
    CROSS_CHECK = "cross_check" # Kreuzvalidierung
    EXPERT = "expert"          # Expertenmeinung
    AUTOMATED = "automated"    # Automatisierte Prüfung


class ConfidenceLevel(StrEnum):
    """Vertrauensstufen"""
    VERY_LOW = "very_low"      # < 20%
    LOW = "low"               # 20-40%
    MEDIUM = "medium"         # 40-60%
    HIGH = "high"             # 60-80%
    VERY_HIGH = "very_high"   # > 80%


@dataclass
class Claim:
    """Eine zu überprüfende Behauptung"""
    text: str
    context: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "context": self.context,
            "category": self.category,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Evidence:
    """Beweis für oder gegen eine Behauptung"""
    id: str
    claim_id: str
    evidence_type: EvidenceType
    source: str
    content: str
    url: Optional[str] = None
    confidence: float = 0.5  # 0.0 bis 1.0
    supports_claim: bool = True  # Unterstützt die Behauptung?
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "claim_id": self.claim_id,
            "evidence_type": self.evidence_type.value,
            "source": self.source,
            "content": self.content,
            "url": self.url,
            "confidence": self.confidence,
            "supports_claim": self.supports_claim,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class VerificationRequest:
    """Anfrage zur Verifizierung einer Behauptung"""
    claim: Claim
    max_evidence: int = 5
    min_confidence: float = 0.0
    require_consensus: bool = True
    min_consensus_sources: int = 2
    timeout: int = 30  # Sekunden
    
    def to_dict(self) -> dict:
        return {
            "claim": self.claim.to_dict(),
            "max_evidence": self.max_evidence,
            "min_confidence": self.min_confidence,
            "require_consensus": self.require_consensus,
            "min_consensus_sources": self.min_consensus_sources,
            "timeout": self.timeout,
        }


@dataclass
class VerificationResult:
    """Ergebnis einer Verifizierung"""
    claim: Claim
    status: VerificationStatus
    confidence: float = 0.0  # 0.0 bis 1.0
    evidence: list[Evidence] = field(default_factory=list)
    supporting_evidence: int = 0
    contradicting_evidence: int = 0
    consensus_score: float = 0.0  # 0.0 bis 1.0
    sources_used: list[str] = field(default_factory=list)
    execution_time: float = 0.0
    verified_at: datetime = field(default_factory=datetime.now)
    notes: str = ""
    
    def to_dict(self) -> dict:
        return {
            "claim": self.claim.to_dict(),
            "status": self.status.value,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "consensus_score": self.consensus_score,
            "sources_used": self.sources_used,
            "execution_time": self.execution_time,
            "verified_at": self.verified_at.isoformat(),
            "notes": self.notes,
        }
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Gibt die Vertrauensstufe zurück"""
        if self.confidence >= 0.8:
            return ConfidenceLevel.VERY_HIGH
        elif self.confidence >= 0.6:
            return ConfidenceLevel.HIGH
        elif self.confidence >= 0.4:
            return ConfidenceLevel.MEDIUM
        elif self.confidence >= 0.2:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    @property
    def is_reliable(self) -> bool:
        """Ist das Ergebnis zuverlässig?"""
        return (
            self.status == VerificationStatus.VERIFIED and 
            self.confidence >= 0.7
        )
    
    @property
    def is_false(self) -> bool:
        """Ist die Behauptung falsch?"""
        return (
            self.status == VerificationStatus.FALSE or
            (self.status == VerificationStatus.DISPUTED and self.confidence < 0.3)
        )


# Pydantic-Modelle für API-Kompatibilität
class ClaimModel(BaseModel):
    text: str = Field(..., description="Text der Behauptung")
    context: Optional[str] = Field(default=None, description="Kontext der Behauptung")
    category: Optional[str] = Field(default=None, description="Kategorie der Behauptung")
    source: Optional[str] = Field(default=None, description="Quelle der Behauptung")
    created_at: datetime = Field(default_factory=datetime.now, description="Erstellungsdatum")


class EvidenceModel(BaseModel):
    id: str = Field(..., description="Einzigartige ID des Beweises")
    claim_id: str = Field(..., description="ID der zugehörigen Behauptung")
    evidence_type: EvidenceType = Field(..., description="Typ des Beweises")
    source: str = Field(..., description="Quelle des Beweises")
    content: str = Field(..., description="Inhalt des Beweises")
    url: Optional[str] = Field(default=None, description="URL des Beweises")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Vertrauenswert")
    supports_claim: bool = Field(default=True, description="Unterstützt die Behauptung?")
    created_at: datetime = Field(default_factory=datetime.now, description="Erstellungsdatum")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadaten")


class VerificationRequestModel(BaseModel):
    claim: ClaimModel = Field(..., description="Zu überprüfende Behauptung")
    max_evidence: int = Field(default=5, ge=1, le=20, description="Maximale Anzahl Beweise")
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Mindest-Vertrauenswert")
    require_consensus: bool = Field(default=True, description="Konsens erforderlich?")
    min_consensus_sources: int = Field(default=2, ge=1, le=10, description="Minimale Konsens-Quellen")
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout in Sekunden")


class VerificationResultModel(BaseModel):
    claim: ClaimModel = Field(..., description="Überprüfte Behauptung")
    status: VerificationStatus = Field(..., description="Verifizierungsstatus")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Vertrauenswert")
    evidence: list[EvidenceModel] = Field(default_factory=list, description="Beweise")
    supporting_evidence: int = Field(default=0, ge=0, description="Unterstützende Beweise")
    contradicting_evidence: int = Field(default=0, ge=0, description="Widersprechende Beweise")
    consensus_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Konsens-Score")
    sources_used: list[str] = Field(default_factory=list, description="Verwendete Quellen")
    execution_time: float = Field(default=0.0, ge=0.0, description="Ausführungszeit")
    verified_at: datetime = Field(default_factory=datetime.now, description="Verifizierungsdatum")
    notes: str = Field(default="", description="Hinweise")
