"""
Contribution Manager - Verwaltung von Community-Beiträgen
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from vibe.core.community.models import (
    CommunityContribution,
    ContributionStatus,
    ContributionType,
    Vote,
    VoteType,
    UserReputation,
)
from vibe.core.knowledge.database import KnowledgeDatabase
from vibe.core.knowledge.models import KnowledgeCategory, KnowledgeEntry, KnowledgeSource, KnowledgeSourceType
from vibe.observability.logging import logger


class ContributionManager:
    """
    Verwaltet Community-Beiträge und deren Integration in die Wissensdatenbank.
    
    Features:
    - Beitrags-Verwaltung
    - Abstimmungssystem
    - Integration mit Wissensdatenbank
    - Benachrichtigungen
    """
    
    DEFAULT_STORAGE_PATH = Path("~/.vibe/community/contributions").expanduser()
    
    def __init__(self, storage_path: Path | str | None = None, db: KnowledgeDatabase | None = None):
        self.storage_path = Path(storage_path) if storage_path else self.DEFAULT_STORAGE_PATH
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.db = db or KnowledgeDatabase()
        self._contributions: dict[str, CommunityContribution] = {}
        self._votes: dict[str, list[Vote]] = {}
        self._reputations: dict[str, UserReputation] = {}
        self._load_contributions()
    
    def _load_contributions(self) -> None:
        """Lädt alle Beiträge aus dem Speicher"""
        if not self.storage_path.exists():
            return
        
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    contribution = CommunityContribution(**data)
                    self._contributions[contribution.id] = contribution
            except Exception as e:
                logger.error("Failed to load contribution from %s: %s", file_path, e)
    
    def _save_contribution(self, contribution: CommunityContribution) -> None:
        """Speichert einen Beitrag"""
        file_path = self.storage_path / f"{contribution.id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(contribution.to_dict(), f, indent=2, ensure_ascii=False)
    
    def create_contribution(
        self,
        user_id: str,
        user_name: str,
        type: ContributionType,
        title: str,
        content: str,
        category: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CommunityContribution:
        """
        Erstellt einen neuen Community-Beitrag.
        
        Args:
            user_id: ID des Benutzers
            user_name: Name des Benutzers
            type: Typ des Beitrags
            title: Titel
            content: Inhalt
            category: Kategorie
            metadata: Metadaten
        
        Returns:
            Der erstellte Beitrag
        """
        # Generiere ID
        content_hash = hashlib.md5(f"{user_id}_{title}_{content}".encode()).hexdigest()[:16]
        contribution_id = f"contrib_{content_hash}"
        
        contribution = CommunityContribution(
            id=contribution_id,
            user_id=user_id,
            user_name=user_name,
            type=type,
            title=title,
            content=content,
            category=category,
            status=ContributionStatus.PENDING,
            metadata=metadata or {},
        )
        
        self._contributions[contribution_id] = contribution
        self._save_contribution(contribution)
        
        # Aktualisiere Benutzer-Reputation
        self._update_reputation_on_contribution(user_id, user_name)
        
        logger.info("Created new contribution: %s by %s", contribution_id, user_name)
        return contribution
    
    def get_contribution(self, contribution_id: str) -> Optional[CommunityContribution]:
        """Holt einen Beitrag anhand seiner ID"""
        return self._contributions.get(contribution_id)
    
    def list_contributions(
        self,
        status: ContributionStatus | None = None,
        user_id: str | None = None,
        type: ContributionType | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[CommunityContribution]:
        """Listet Beiträge mit optionalem Filter"""
        contributions = list(self._contributions.values())
        
        # Filter anwenden
        if status:
            contributions = [c for c in contributions if c.status == status]
        
        if user_id:
            contributions = [c for c in contributions if c.user_id == user_id]
        
        if type:
            contributions = [c for c in contributions if c.type == type]
        
        if category:
            contributions = [c for c in contributions if c.category == category]
        
        # Sortieren nach Erstellungsdatum (neueste zuerst)
        contributions.sort(key=lambda x: x.created_at, reverse=True)
        
        return contributions[:limit]
    
    def update_contribution_status(
        self,
        contribution_id: str,
        status: ContributionStatus,
        user_id: str | None = None,
    ) -> bool:
        """Aktualisiert den Status eines Beitrags"""
        contribution = self.get_contribution(contribution_id)
        if not contribution:
            return False
        
        old_status = contribution.status
        contribution.status = status
        contribution.updated_at = datetime.now()
        
        # Wenn genehmigt, in Wissensdatenbank integrieren
        if status == ContributionStatus.APPROVED and old_status != ContributionStatus.APPROVED:
            self._integrate_into_knowledge_db(contribution)
        
        self._save_contribution(contribution)
        logger.info("Updated contribution %s status to %s", contribution_id, status.value)
        return True
    
    def delete_contribution(self, contribution_id: str, user_id: str | None = None) -> bool:
        """Löscht einen Beitrag"""
        contribution = self.get_contribution(contribution_id)
        if not contribution:
            return False
        
        # Nur der Ersteller oder Admin kann löschen
        if user_id and contribution.user_id != user_id:
            logger.warning("User %s tried to delete contribution %s by %s", user_id, contribution_id, contribution.user_id)
            return False
        
        file_path = self.storage_path / f"{contribution_id}.json"
        if file_path.exists():
            file_path.unlink()
        
        del self._contributions[contribution_id]
        
        # Abstimmungen löschen
        if contribution_id in self._votes:
            del self._votes[contribution_id]
        
        logger.info("Deleted contribution: %s", contribution_id)
        return True
    
    def vote_on_contribution(
        self,
        contribution_id: str,
        user_id: str,
        user_name: str,
        vote_type: VoteType,
        comment: str | None = None,
    ) -> Optional[Vote]:
        """
        Stimmt über einen Beitrag ab.
        
        Args:
            contribution_id: ID des Beitrags
            user_id: ID des Benutzers
            user_name: Name des Benutzers
            vote_type: Typ der Abstimmung
            comment: Kommentar
        
        Returns:
            Die erstellte Abstimmung oder None, wenn fehlgeschlagen
        """
        contribution = self.get_contribution(contribution_id)
        if not contribution:
            return None
        
        # Prüfe, ob der Benutzer bereits abgestimmt hat
        if contribution_id in self._votes:
            for vote in self._votes[contribution_id]:
                if vote.user_id == user_id:
                    logger.warning("User %s already voted on contribution %s", user_id, contribution_id)
                    return None
        
        # Erstelle Abstimmung
        vote_id = f"vote_{hashlib.md5(f"{user_id}_{contribution_id}_{vote_type}".encode()).hexdigest()[:16]}"
        vote = Vote(
            id=vote_id,
            contribution_id=contribution_id,
            user_id=user_id,
            user_name=user_name,
            vote_type=vote_type,
            comment=comment,
            weight=self._get_user_weight(user_id),
        )
        
        # Speichere Abstimmung
        if contribution_id not in self._votes:
            self._votes[contribution_id] = []
        self._votes[contribution_id].append(vote)
        
        # Aktualisiere Beitrag
        if vote_type == VoteType.UPVOTE:
            contribution.upvotes += 1
        elif vote_type == VoteType.DOWNVOTE:
            contribution.downvotes += 1
        elif vote_type == VoteType.VERIFY:
            contribution.verification_votes += 1
            if user_id not in contribution.verified_by:
                contribution.verified_by.append(user_id)
        elif vote_type == VoteType.DISPUTE:
            contribution.dispute_votes += 1
        
        contribution.updated_at = datetime.now()
        self._save_contribution(contribution)
        
        # Aktualisiere Reputation
        self._update_reputation_on_vote(user_id, vote_type)
        
        # Prüfe, ob Beitrag automatisch genehmigt werden kann
        self._check_auto_approval(contribution)
        
        logger.info("User %s voted %s on contribution %s", user_name, vote_type.value, contribution_id)
        return vote
    
    def get_votes(self, contribution_id: str) -> list[Vote]:
        """Holt alle Abstimmungen für einen Beitrag"""
        return self._votes.get(contribution_id, [])
    
    def get_user_vote(self, contribution_id: str, user_id: str) -> Optional[Vote]:
        """Holt die Abstimmung eines bestimmten Benutzers für einen Beitrag"""
        votes = self.get_votes(contribution_id)
        for vote in votes:
            if vote.user_id == user_id:
                return vote
        return None
    
    def get_reputation(self, user_id: str) -> UserReputation:
        """Holt die Reputation eines Benutzers"""
        if user_id not in self._reputations:
            # Erstelle neue Reputation
            self._reputations[user_id] = UserReputation(
                user_id=user_id,
                user_name=f"user_{user_id}",  # Wird später aktualisiert
            )
        return self._reputations[user_id]
    
    def update_reputation(self, user_id: str, user_name: str | None = None, **kwargs) -> UserReputation:
        """Aktualisiert die Reputation eines Benutzers"""
        reputation = self.get_reputation(user_id)
        
        if user_name:
            reputation.user_name = user_name
        
        for key, value in kwargs.items():
            if hasattr(reputation, key):
                setattr(reputation, key, value)
        
        reputation.last_active = datetime.now()
        return reputation
    
    def _update_reputation_on_contribution(self, user_id: str, user_name: str) -> None:
        """Aktualisiert die Reputation nach einem Beitrag"""
        reputation = self.get_reputation(user_id)
        reputation.user_name = user_name
        reputation.contributions += 1
        
        # Berechne neuen Score
        self._calculate_reputation_score(reputation)
    
    def _update_reputation_on_vote(self, user_id: str, vote_type: VoteType) -> None:
        """Aktualisiert die Reputation nach einer Abstimmung"""
        reputation = self.get_reputation(user_id)
        
        # Bonus für Verifizierungsstimmen
        if vote_type == VoteType.VERIFY:
            reputation.verified_contributions += 1
            reputation.score = min(100.0, reputation.score + 2.0)
        elif vote_type == VoteType.UPVOTE:
            reputation.score = min(100.0, reputation.score + 0.5)
        elif vote_type == VoteType.DOWNVOTE:
            # Small penalty for downvotes (to prevent abuse)
            reputation.score = max(0.0, reputation.score - 0.1)
        
        # Aktualisiere Level
        self._update_reputation_level(reputation)
    
    def _calculate_reputation_score(self, reputation: UserReputation) -> None:
        """Berechnet den Reputations-Score"""
        # Basis-Score
        base_score = 0.0
        
        # Beiträge
        base_score += reputation.contributions * 1.0
        
        # Verifizierte Beiträge
        base_score += reputation.verified_contributions * 5.0
        
        # Upvotes erhalten
        base_score += reputation.upvotes_received * 0.5
        
        # Downvotes erhalten
        base_score -= reputation.downvotes_received * 0.2
        
        # Begrenze auf 0-100
        reputation.score = max(0.0, min(100.0, base_score))
        
        # Aktualisiere Level
        self._update_reputation_level(reputation)
    
    def _update_reputation_level(self, reputation: UserReputation) -> None:
        """Aktualisiert das Level basierend auf dem Score"""
        if reputation.score >= 80:
            reputation.level = 5
        elif reputation.score >= 60:
            reputation.level = 4
        elif reputation.score >= 40:
            reputation.level = 3
        elif reputation.score >= 20:
            reputation.level = 2
        else:
            reputation.level = 1
    
    def _get_user_weight(self, user_id: str) -> float:
        """Holt das Abstimmungsgewicht eines Benutzers basierend auf seiner Reputation"""
        reputation = self.get_reputation(user_id)
        
        # Gewicht basierend auf Level
        level_weights = {
            1: 0.5,
            2: 0.8,
            3: 1.0,
            4: 1.2,
            5: 1.5,
        }
        
        return level_weights.get(reputation.level, 1.0)
    
    def _check_auto_approval(self, contribution: CommunityContribution) -> None:
        """Prüft, ob ein Beitrag automatisch genehmigt werden kann"""
        # Mindestens 5 Upvotes und 0 Downvotes
        if (contribution.upvotes >= 5 and 
            contribution.downvotes == 0 and
            contribution.status == ContributionStatus.PENDING):
            
            contribution.status = ContributionStatus.APPROVED
            contribution.updated_at = datetime.now()
            self._save_contribution(contribution)
            self._integrate_into_knowledge_db(contribution)
            
            logger.info("Auto-approved contribution: %s", contribution.id)
    
    def _integrate_into_knowledge_db(self, contribution: CommunityContribution) -> None:
        """Integriert einen genehmigten Beitrag in die Wissensdatenbank"""
        try:
            # Erstelle Quelle
            source = KnowledgeSource(
                id=f"community_{contribution.id}",
                name=f"Community: {contribution.user_name}",
                url="",  # Keine URL für Community-Quellen
                source_type=KnowledgeSourceType.COMMUNITY,
                trust_score=0.7,  # Standard-Vertrauenswert für Community
                description=f"Community-Beitrag von {contribution.user_name}",
            )
            
            # Erstelle Wissenseintrag
            category = KnowledgeCategory.GENERAL
            if contribution.category:
                try:
                    category = KnowledgeCategory(contribution.category.lower())
                except ValueError:
                    pass
            
            entry = KnowledgeEntry(
                id=f"kb_{contribution.id}",
                title=contribution.title,
                content=contribution.content,
                category=category,
                source=source,
                confidence=0.7,  # Standard-Vertrauenswert
                verification_status="community_verified",
                verification_count=contribution.verification_votes,
            )
            
            # Speichere in Wissensdatenbank
            self.db.add_entry(entry)
            self.db.add_source(source)
            
            logger.info("Integrated contribution %s into knowledge database", contribution.id)
            
        except Exception as e:
            logger.error("Failed to integrate contribution %s into knowledge DB: %s", contribution.id, e)
    
    def get_stats(self) -> dict:
        """Holt Statistiken zum Community-System"""
        return {
            "total_contributions": len(self._contributions),
            "pending": len([c for c in self._contributions.values() if c.status == ContributionStatus.PENDING]),
            "approved": len([c for c in self._contributions.values() if c.status == ContributionStatus.APPROVED]),
            "rejected": len([c for c in self._contributions.values() if c.status == ContributionStatus.REJECTED]),
            "verified": len([c for c in self._contributions.values() if c.status == ContributionStatus.VERIFIED]),
            "total_votes": sum(len(votes) for votes in self._votes.values()),
            "total_users": len(self._reputations),
            "top_contributors": self._get_top_contributors(10),
        }
    
    def _get_top_contributors(self, limit: int = 10) -> list[dict]:
        """Holt die Top-Beitragenden"""
        sorted_reputations = sorted(
            self._reputations.values(),
            key=lambda x: x.score,
            reverse=True,
        )[:limit]
        
        return [
            {
                "user_id": r.user_id,
                "user_name": r.user_name,
                "score": r.score,
                "level": r.level,
                "contributions": r.contributions,
                "verified_contributions": r.verified_contributions,
            }
            for r in sorted_reputations
        ]
    
    def get_user_contributions(self, user_id: str) -> list[CommunityContribution]:
        """Holt alle Beiträge eines Benutzers"""
        return [
            c for c in self._contributions.values()
            if c.user_id == user_id
        ]
