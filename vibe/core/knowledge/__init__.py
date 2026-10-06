"""
Knowledge Module - Wissensdatenbank für Echtzeit-Aktualisierungen

Dieses Modul verwaltet:
- Statische Wissensdatenbank (lokal gespeichert)
- Dynamische Aktualisierungen (Echtzeit)
- Versionierung und Historien
- Quellenverwaltung
"""

from vibe.core.knowledge.database import KnowledgeDatabase
from vibe.core.knowledge.updater import KnowledgeUpdater
from vibe.core.knowledge.models import (
    KnowledgeEntry,
    KnowledgeCategory,
    KnowledgeSource,
    KnowledgeQuery,
    KnowledgeResult,
)

__all__ = [
    "KnowledgeDatabase",
    "KnowledgeUpdater",
    "KnowledgeEntry",
    "KnowledgeCategory",
    "KnowledgeSource",
    "KnowledgeQuery",
    "KnowledgeResult",
    "get_knowledge_db",
]

_knowledge_db: KnowledgeDatabase | None = None


def get_knowledge_db() -> KnowledgeDatabase:
    """Holt die globale Wissensdatenbank-Instanz"""
    global _knowledge_db
    if _knowledge_db is None:
        _knowledge_db = KnowledgeDatabase()
    return _knowledge_db
