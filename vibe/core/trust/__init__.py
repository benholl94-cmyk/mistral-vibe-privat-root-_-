"""
Trust Module - Vertrauenssystem für Quellen und Informationen

Dieses Modul bietet:
- Vertrauensbewertung von Quellen
- Vertrauenspropagierung durch das System
- Vertrauensnetzwerke
- Betrugserkennung
"""

from vibe.core.trust.scoring import TrustScoring
from vibe.core.trust.models import (
    TrustScore,
    TrustNetwork,
    TrustRelationship,
    TrustLevel,
)

__all__ = [
    "TrustScoring",
    "TrustScore",
    "TrustNetwork",
    "TrustRelationship",
    "TrustLevel",
    "get_trust_scoring",
]

_trust_scoring: TrustScoring | None = None


def get_trust_scoring() -> TrustScoring:
    """Holt die globale TrustScoring-Instanz"""
    global _trust_scoring
    if _trust_scoring is None:
        _trust_scoring = TrustScoring()
    return _trust_scoring
