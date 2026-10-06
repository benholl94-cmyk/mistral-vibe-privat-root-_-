"""
Community Module - Kollaborative Wissenspflege durch Benutzer

Dieses Modul ermöglicht:
- Benutzer können Wissenseinträge beisteuern
- Abstimmung über Einträge
- Reputationssystem für Benutzer
- Kollaborative Validierung
"""

from vibe.core.community.contributions import ContributionManager
from vibe.core.community.voting import VotingSystem
from vibe.core.community.reputation import ReputationSystem
from vibe.core.community.models import (
    CommunityContribution,
    Vote,
    UserReputation,
    ContributionStatus,
)

__all__ = [
    "ContributionManager",
    "VotingSystem",
    "ReputationSystem",
    "CommunityContribution",
    "Vote",
    "UserReputation",
    "ContributionStatus",
    "get_community_manager",
]

_community_manager: ContributionManager | None = None


def get_community_manager() -> ContributionManager:
    """Holt die globale Community-Manager-Instanz"""
    global _community_manager
    if _community_manager is None:
        _community_manager = ContributionManager()
    return _community_manager
