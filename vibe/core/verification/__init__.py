"""
Verification Module - Faktencheck und Validierung von Informationen

Dieses Modul bietet:
- Automatische Faktencheck-Pipeline
- Quellenvalidierung
- Vertrauensbewertung
- Konsensprüfung
"""

from vibe.core.verification.pipeline import FactCheckPipeline
from vibe.core.verification.validator import InformationValidator
from vibe.core.verification.models import (
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
    Claim,
    Evidence,
)

__all__ = [
    "FactCheckPipeline",
    "InformationValidator",
    "VerificationRequest",
    "VerificationResult",
    "VerificationStatus",
    "Claim",
    "Evidence",
    "get_verification_pipeline",
]

_verification_pipeline: FactCheckPipeline | None = None


def get_verification_pipeline() -> FactCheckPipeline:
    """Holt die globale Faktencheck-Pipeline-Instanz"""
    global _verification_pipeline
    if _verification_pipeline is None:
        _verification_pipeline = FactCheckPipeline()
    return _verification_pipeline
