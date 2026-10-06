"""
Datenmodelle für das Community-System
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ContributionStatus(StrEnum):
    """Status eines Community-Beitrags"""
    PENDING = "pending"      # Wartet auf Überprüfung
    APPROVED = "approved"    # Genehmigt
    REJECTED = "rejected"    # Abgelehnt
    DISPUTED = "disputed"    # Umstritten
    VERIFIED = "verified"    # Verifiziert


class ContributionType(StrEnum):
    """Typen von Community-Beiträgen"""
    KNOWLEDGE_ENTRY = "knowledge_entry"
    SOURCE = "source"
    CORRECTION = "correction"
    FEEDBACK = "feedback"
    SUGGESTION = "suggestion"


class VoteType(StrEnum):
    """Typen von Abstimmungen"""
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"
    VERIFY = "verify"
    DISPUTE = "dispute"


@dataclass
class CommunityContribution:
    """Ein Beitrag von einem Community-Mitglied"""
    id: str
    user_id: str
    user_name: str
    type: ContributionType
    title: str
    content: str
    category: str = ""
    status: ContributionStatus = ContributionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Abstimmungen
    upvotes: int = 0
    downvotes: int = 0
    verification_votes: int = 0
    dispute_votes: int = 0
    
    # Verifizierung
    verified_by: list[str] = field(default_factory=list)  # Liste von User-IDs
    verified_at: Optional[datetime] = None
    
    # Kommentare
    comments: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "type": self.type.value,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "upvotes": self.upvotes,
            "downvotes": self.downvotes,
            "verification_votes": self.verification_votes,
            "dispute_votes": self.dispute_votes,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "comments": self.comments,
        }
    
    @property
    def score(self) -> int:
        """Berechnet den Gesamt-Score des Beitrags"""
        return self.upvotes - self.downvotes
    
    @property
    def net_votes(self) -> int:
        """Berechnet die Nettostimmen"""
        return self.upvotes - self.downvotes
    
    @property
    def verification_score(self) -> int:
        """Berechnet den Verifizierungs-Score"""
        return self.verification_votes - self.dispute_votes
    
    @property
    def is_approved(self) -> bool:
        """Ist der Beitrag genehmigt?"""
        return self.status == ContributionStatus.APPROVED
    
    @property
    def is_verified(self) -> bool:
        """Ist der Beitrag verifiziert?"""
        return self.status == ContributionStatus.VERIFIED


@dataclass
class Vote:
    """Eine Abstimmung über einen Beitrag"""
    id: str
    contribution_id: str
    user_id: str
    user_name: str
    vote_type: VoteType
    created_at: datetime = field(default_factory=datetime.now)
    comment: Optional[str] = None
    weight: float = 1.0  # Gewicht der Stimme (basierend auf Reputation)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "contribution_id": self.contribution_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "vote_type": self.vote_type.value,
            "created_at": self.created_at.isoformat(),
            "comment": self.comment,
            "weight": self.weight,
        }


@dataclass
class UserReputation:
    """Reputation eines Benutzers"""
    user_id: str
    user_name: str
    score: float = 0.0  # 0.0 bis 100.0
    level: int = 1
    contributions: int = 0
    verified_contributions: int = 0
    upvotes_received: int = 0
    downvotes_received: int = 0
    last_active: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "score": self.score,
            "level": self.level,
            "contributions": self.contributions,
            "verified_contributions": self.verified_contributions,
            "upvotes_received": self.upvotes_received,
            "downvotes_received": self.downvotes_received,
            "last_active": self.last_active.isoformat(),
        }
    
    @property
    def trust_level(self) -> str:
        """Gibt den Vertrauenslevel zurück"""
        if self.score >= 80:
            return "trusted"
        elif self.score >= 60:
            return "reliable"
        elif self.score >= 40:
            return "neutral"
        elif self.score >= 20:
            return "unreliable"
        else:
            return "untrusted"


# Pydantic-Modelle für API-Kompatibilität
class CommunityContributionModel(BaseModel):
    id: str = Field(..., description="Einzigartige ID des Beitrags")
    user_id: str = Field(..., description="ID des Benutzers")
    user_name: str = Field(..., description="Name des Benutzers")
    type: ContributionType = Field(..., description="Typ des Beitrags")
    title: str = Field(..., description="Titel des Beitrags")
    content: str = Field(..., description="Inhalt des Beitrags")
    category: str = Field(default="", description="Kategorie")
    status: ContributionStatus = Field(default=ContributionStatus.PENDING, description="Status")
    created_at: datetime = Field(default_factory=datetime.now, description="Erstellungsdatum")
    updated_at: datetime = Field(default_factory=datetime.now, description="Letzte Aktualisierung")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadaten")
    upvotes: int = Field(default=0, ge=0, description="Upvotes")
    downvotes: int = Field(default=0, ge=0, description="Downvotes")
    verification_votes: int = Field(default=0, ge=0, description="Verifizierungsstimmen")
    dispute_votes: int = Field(default=0, ge=0, description="Widerspruchsstimmen")
    verified_by: list[str] = Field(default_factory=list, description="Verifiziert durch")
    verified_at: Optional[datetime] = Field(default=None, description="Verifizierungsdatum")
    comments: list[dict] = Field(default_factory=list, description="Kommentare")


class VoteModel(BaseModel):
    id: str = Field(..., description="Einzigartige ID der Abstimmung")
    contribution_id: str = Field(..., description="ID des Beitrags")
    user_id: str = Field(..., description="ID des Benutzers")
    user_name: str = Field(..., description="Name des Benutzers")
    vote_type: VoteType = Field(..., description="Typ der Abstimmung")
    created_at: datetime = Field(default_factory=datetime.now, description="Erstellungsdatum")
    comment: Optional[str] = Field(default=None, description="Kommentar")
    weight: float = Field(default=1.0, ge=0.0, description="Gewicht der Stimme")


class UserReputationModel(BaseModel):
    user_id: str = Field(..., description="ID des Benutzers")
    user_name: str = Field(..., description="Name des Benutzers")
    score: float = Field(default=0.0, ge=0.0, le=100.0, description="Reputations-Score")
    level: int = Field(default=1, ge=1, description="Level")
    contributions: int = Field(default=0, ge=0, description="Anzahl Beiträge")
    verified_contributions: int = Field(default=0, ge=0, description="Anzahl verifizierte Beiträge")
    upvotes_received: int = Field(default=0, ge=0, description="Erhaltene Upvotes")
    downvotes_received: int = Field(default=0, ge=0, description="Erhaltene Downvotes")
    last_active: datetime = Field(default_factory=datetime.now, description="Letzte Aktivität")
