"""
Voting System - Abstimmungssystem für Community-Beiträge
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from vibe.core.community.models import (
    CommunityContribution,
    ContributionStatus,
    Vote,
    VoteType,
)
from vibe.observability.logging import logger


@dataclass
class VotingResult:
    """Ergebnis einer Abstimmung"""
    contribution_id: str
    upvotes: int
    downvotes: int
    verification_votes: int
    dispute_votes: int
    net_score: int
    consensus_score: float  # 0.0 bis 1.0
    status_change: Optional[ContributionStatus] = None


class VotingSystem:
    """
    Verwaltet Abstimmungen über Community-Beiträge.
    
    Features:
    - Abstimmungen verwalten
    - Konsens berechnen
    - Automatische Statusänderungen
    - Spam-Schutz
    """
    
    def __init__(self):
        self._votes: dict[str, list[Vote]] = {}
        self._vote_history: dict[str, list[Vote]] = {}  # user_id -> [Vote]
    
    def add_vote(self, vote: Vote) -> VotingResult:
        """
        Fügt eine neue Abstimmung hinzu.
        
        Args:
            vote: Die Abstimmung
        
        Returns:
            VotingResult mit dem aktuellen Stand
        """
        # Initialisiere Liste für diesen Beitrag
        if vote.contribution_id not in self._votes:
            self._votes[vote.contribution_id] = []
        
        # Füge Abstimmung hinzu
        self._votes[vote.contribution_id].append(vote)
        
        # Aktualisiere Benutzerhistorie
        if vote.user_id not in self._vote_history:
            self._vote_history[vote.user_id] = []
        self._vote_history[vote.user_id].append(vote)
        
        # Berechne Ergebnis
        return self._calculate_voting_result(vote.contribution_id)
    
    def remove_vote(self, vote_id: str) -> bool:
        """Entfernt eine Abstimmung"""
        for contribution_id, votes in self._votes.items():
            for i, vote in enumerate(votes):
                if vote.id == vote_id:
                    del votes[i]
                    
                    # Entferne aus Benutzerhistorie
                    if vote.user_id in self._vote_history:
                        user_votes = self._vote_history[vote.user_id]
                        for j, user_vote in enumerate(user_votes):
                            if user_vote.id == vote_id:
                                del user_votes[j]
                                break
                    
                    return True
        return False
    
    def get_votes(self, contribution_id: str) -> list[Vote]:
        """Holt alle Abstimmungen für einen Beitrag"""
        return self._votes.get(contribution_id, [])
    
    def get_user_votes(self, user_id: str) -> list[Vote]:
        """Holt alle Abstimmungen eines Benutzers"""
        return self._vote_history.get(user_id, [])
    
    def get_user_vote_on_contribution(self, user_id: str, contribution_id: str) -> Optional[Vote]:
        """Holt die Abstimmung eines Benutzers für einen bestimmten Beitrag"""
        votes = self.get_votes(contribution_id)
        for vote in votes:
            if vote.user_id == user_id:
                return vote
        return None
    
    def _calculate_voting_result(self, contribution_id: str) -> VotingResult:
        """Berechnet das Abstimmungsergebnis für einen Beitrag"""
        votes = self.get_votes(contribution_id)
        
        upvotes = sum(1 for v in votes if v.vote_type == VoteType.UPVOTE)
        downvotes = sum(1 for v in votes if v.vote_type == VoteType.DOWNVOTE)
        verification_votes = sum(1 for v in votes if v.vote_type == VoteType.VERIFY)
        dispute_votes = sum(1 for v in votes if v.vote_type == VoteType.DISPUTE)
        
        net_score = (upvotes + verification_votes) - (downvotes + dispute_votes)
        
        # Berechne Konsens-Score
        total_votes = len(votes)
        if total_votes > 0:
            positive_votes = upvotes + verification_votes
            consensus_score = positive_votes / total_votes
        else:
            consensus_score = 0.0
        
        # Bestimme Statusänderung
        status_change = self._determine_status_change(
            upvotes, downvotes, verification_votes, dispute_votes
        )
        
        return VotingResult(
            contribution_id=contribution_id,
            upvotes=upvotes,
            downvotes=downvotes,
            verification_votes=verification_votes,
            dispute_votes=dispute_votes,
            net_score=net_score,
            consensus_score=consensus_score,
            status_change=status_change,
        )
    
    def _determine_status_change(
        self,
        upvotes: int,
        downvotes: int,
        verification_votes: int,
        dispute_votes: int,
    ) -> Optional[ContributionStatus]:
        """Bestimmt, ob sich der Status basierend auf den Abstimmungen ändern sollte"""
        # Genehmigung: Mindestens 5 Upvotes, keine Downvotes
        if upvotes >= 5 and downvotes == 0 and dispute_votes == 0:
            return ContributionStatus.APPROVED
        
        # Verifiziert: Mindestens 3 Verifizierungsstimmen
        if verification_votes >= 3 and dispute_votes < verification_votes:
            return ContributionStatus.VERIFIED
        
        # Umstritten: Mindestens 2 Widerspruchsstimmen
        if dispute_votes >= 2:
            return ContributionStatus.DISPUTED
        
        # Abgelehnt: Mehr Downvotes als Upvotes
        if downvotes > upvotes + verification_votes:
            return ContributionStatus.REJECTED
        
        return None
    
    def check_spam(self, user_id: str, contribution_id: str | None = None) -> bool:
        """
        Prüft, ob ein Benutzer Spam betreibt.
        
        Args:
            user_id: ID des Benutzers
            contribution_id: Optionale Beitrags-ID
        
        Returns:
            True, wenn Spam vermutet wird
        """
        user_votes = self.get_user_votes(user_id)
        
        # Zu viele Abstimmungen in kurzer Zeit
        if len(user_votes) > 20:
            # Prüfe, ob die letzten 20 Abstimmungen innerhalb von 1 Minute waren
            now = datetime.now()
            recent_votes = [v for v in user_votes if (now - v.created_at).total_seconds() < 60]
            if len(recent_votes) >= 20:
                logger.warning("User %s is voting too fast (potential spam)", user_id)
                return True
        
        # Zu viele Abstimmungen für denselben Beitrag
        if contribution_id:
            contribution_votes = [v for v in user_votes if v.contribution_id == contribution_id]
            if len(contribution_votes) > 1:
                logger.warning("User %s voted multiple times on contribution %s", user_id, contribution_id)
                return True
        
        return False
    
    def get_contribution_score(self, contribution_id: str) -> float:
        """
        Berechnet den Score eines Beitrags basierend auf Abstimmungen.
        
        Args:
            contribution_id: ID des Beitrags
        
        Returns:
            Score zwischen 0.0 und 1.0
        """
        votes = self.get_votes(contribution_id)
        
        if not votes:
            return 0.5  # Neutraler Score
        
        total_weight = 0.0
        weighted_score = 0.0
        
        for vote in votes:
            weight = vote.weight
            total_weight += weight
            
            if vote.vote_type in [VoteType.UPVOTE, VoteType.VERIFY]:
                weighted_score += weight
            elif vote.vote_type in [VoteType.DOWNVOTE, VoteType.DISPUTE]:
                weighted_score -= weight
        
        if total_weight == 0:
            return 0.5
        
        # Normalisieren auf 0.0 bis 1.0
        normalized_score = (weighted_score / total_weight + 1.0) / 2.0
        return max(0.0, min(1.0, normalized_score))
    
    def get_trending_contributions(self, limit: int = 10) -> list[str]:
        """
        Holt die Trend-Beiträge (meiste Abstimmungen in letzter Zeit).
        
        Args:
            limit: Maximale Anzahl Ergebnisse
        
        Returns:
            Liste von Beitrags-IDs, sortiert nach Score
        """
        # Berechne Score für alle Beiträge
        contribution_scores = []
        for contribution_id, votes in self._votes.items():
            score = self.get_contribution_score(contribution_id)
            contribution_scores.append((contribution_id, score, len(votes)))
        
        # Sortiere nach Score und Anzahl Abstimmungen
        contribution_scores.sort(key=lambda x: (x[1], x[2]), reverse=True)
        
        return [cid for cid, _, _ in contribution_scores[:limit]]
    
    def get_controversial_contributions(self, limit: int = 10) -> list[str]:
        """
        Holt die umstrittenen Beiträge (meiste Kontroversen).
        
        Args:
            limit: Maximale Anzahl Ergebnisse
        
        Returns:
            Liste von Beitrags-IDs, sortiert nach Kontroversen
        """
        # Berechne Kontroversen-Score für alle Beiträge
        contribution_controversies = []
        for contribution_id, votes in self._votes.items():
            upvotes = sum(1 for v in votes if v.vote_type == VoteType.UPVOTE)
            downvotes = sum(1 for v in votes if v.vote_type == VoteType.DOWNVOTE)
            verification_votes = sum(1 for v in votes if v.vote_type == VoteType.VERIFY)
            dispute_votes = sum(1 for v in votes if v.vote_type == VoteType.DISPUTE)
            
            # Kontroversen-Score = Ausgewogenheit der Abstimmungen
            total = upvotes + downvotes + verification_votes + dispute_votes
            if total == 0:
                controversy_score = 0.0
            else:
                positive = upvotes + verification_votes
                negative = downvotes + dispute_votes
                controversy_score = 1.0 - abs(positive - negative) / total
            
            contribution_controversies.append((contribution_id, controversy_score, total))
        
        # Sortiere nach Kontroversen-Score
        contribution_controversies.sort(key=lambda x: (x[1], x[2]), reverse=True)
        
        return [cid for cid, _, _ in contribution_controversies[:limit]]
