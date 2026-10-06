"""
Wissensdatenbank - Kernimplementierung für die Speicherung und Abfrage von Wissen
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from vibe.core.knowledge.models import (
    KnowledgeCategory,
    KnowledgeEntry,
    KnowledgeEntryModel,
    KnowledgeQuery,
    KnowledgeQueryModel,
    KnowledgeResult,
    KnowledgeSource,
    KnowledgeSourceModel,
)
from vibe.observability.logging import logger


class KnowledgeDatabase:
    """
    SQLite-basierte Wissensdatenbank für effiziente Speicherung und Abfrage.
    
    Features:
    - Volltextsuche
    - Kategorienfilter
    - Vertrauenswert-basierte Sortierung
    - Versionierung
    - Caching
    """
    
    DEFAULT_DB_PATH = Path("~/.vibe/knowledge/knowledge.db").expanduser()
    
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialisiert die Datenbanktabellen"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Quellen-Tabelle
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    trust_score REAL DEFAULT 0.5,
                    last_updated TEXT,
                    description TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1
                )
            """)
            
            # Einträge-Tabelle
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    tags TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    confidence REAL DEFAULT 0.5,
                    verification_status TEXT DEFAULT 'unverified',
                    verification_count INTEGER DEFAULT 0,
                    last_verified TEXT,
                    is_current INTEGER DEFAULT 1,
                    expires_at TEXT,
                    FOREIGN KEY (source_id) REFERENCES sources(id)
                )
            """)
            
            # Volltextsuche-Index
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts 
                USING fts5(
                    id, title, content, tags,
                    tokenize="unicode61 remove_diacritics 2"
                )
            """)
            
            # Indexe für schnelle Abfragen
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_category ON entries(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_source ON entries(source_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_confidence ON entries(confidence)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_current ON entries(is_current)")
            
            conn.commit()
    
    @asynccontextmanager
    async def _async_connection(self):
        """Asynchroner Datenbank-Kontextmanager"""
        # SQLite ist standardmäßig nicht asynchron, also nutzen wir Threading
        loop = asyncio.get_event_loop()
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Holt eine synchronen Datenbankverbindung"""
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
        return self._connection
    
    def add_source(self, source: KnowledgeSource) -> KnowledgeSource:
        """Fügt eine neue Quelle hinzu oder aktualisiert eine bestehende"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sources 
                (id, name, url, source_type, trust_score, last_updated, description, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                source.id,
                source.name,
                source.url,
                source.source_type.value,
                source.trust_score,
                source.last_updated.isoformat(),
                source.description,
                1 if source.is_active else 0,
            ))
            conn.commit()
        return source
    
    def get_source(self, source_id: str) -> Optional[KnowledgeSource]:
        """Holt eine Quelle anhand ihrer ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sources WHERE id = ?", (source_id,))
            row = cursor.fetchone()
            if row:
                return KnowledgeSource(
                    id=row["id"],
                    name=row["name"],
                    url=row["url"],
                    source_type=KnowledgeSourceType(row["source_type"]),
                    trust_score=row["trust_score"],
                    last_updated=datetime.fromisoformat(row["last_updated"]),
                    description=row["description"],
                    is_active=bool(row["is_active"]),
                )
        return None
    
    def add_entry(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        """Fügt einen neuen Wissenseintrag hinzu oder aktualisiert einen bestehenden"""
        # Quelle sicherstellen
        if not isinstance(entry.source, KnowledgeSource):
            raise ValueError("Source must be a KnowledgeSource object")
        
        self.add_source(entry.source)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO entries 
                (id, title, content, category, source_id, created_at, updated_at, 
                 version, tags, metadata, confidence, verification_status, 
                 verification_count, last_verified, is_current, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.title,
                entry.content,
                entry.category.value,
                entry.source.id,
                entry.created_at.isoformat(),
                entry.updated_at.isoformat(),
                entry.version,
                json.dumps(entry.tags),
                json.dumps(entry.metadata),
                entry.confidence,
                entry.verification_status,
                entry.verification_count,
                entry.last_verified.isoformat() if entry.last_verified else None,
                1 if entry.is_current else 0,
                entry.expires_at.isoformat() if entry.expires_at else None,
            ))
            
            # Volltextsuche-Index aktualisieren
            cursor.execute("""
                INSERT OR REPLACE INTO entries_fts 
                (id, title, content, tags)
                VALUES (?, ?, ?, ?)
            """, (
                entry.id,
                entry.title,
                entry.content,
                json.dumps(entry.tags),
            ))
            
            conn.commit()
        return entry
    
    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Holt einen Wissenseintrag anhand seiner ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.*, s.* FROM entries e 
                JOIN sources s ON e.source_id = s.id 
                WHERE e.id = ?
            """, (entry_id,))
            row = cursor.fetchone()
            if row:
                source = KnowledgeSource(
                    id=row["id_1"],  # s.id
                    name=row["name"],
                    url=row["url"],
                    source_type=KnowledgeSourceType(row["source_type"]),
                    trust_score=row["trust_score"],
                    last_updated=datetime.fromisoformat(row["last_updated"]),
                    description=row["description"],
                    is_active=bool(row["is_active"]),
                )
                return KnowledgeEntry(
                    id=row["id"],
                    title=row["title"],
                    content=row["content"],
                    category=KnowledgeCategory(row["category"]),
                    source=source,
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    version=row["version"],
                    tags=json.loads(row["tags"]),
                    metadata=json.loads(row["metadata"]),
                    confidence=row["confidence"],
                    verification_status=row["verification_status"],
                    verification_count=row["verification_count"],
                    last_verified=datetime.fromisoformat(row["last_verified"]) if row["last_verified"] else None,
                    is_current=bool(row["is_current"]),
                    expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
                )
        return None
    
    def query_entries(self, query: KnowledgeQuery) -> KnowledgeResult:
        """Führt eine Abfrage auf der Wissensdatenbank aus"""
        start_time = datetime.now()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Basisabfrage
            sql = """
                SELECT e.*, s.* FROM entries e 
                JOIN sources s ON e.source_id = s.id
            """
            conditions = []
            params = []
            
            # Volltextsuche
            if query.query:
                conditions.append("entries_fts MATCH ?")
                params.append(query.query)
            
            # Kategorienfilter
            if query.categories:
                placeholders = ",".join("？" * len(query.categories))
                conditions.append(f"e.category IN ({placeholders})")
                params.extend([cat.value for cat in query.categories])
            
            # Quellenfilter
            if query.sources:
                placeholders = ",".join("？" * len(query.sources))
                conditions.append(f"s.id IN ({placeholders})")
                params.extend(query.sources)
            
            # Mindest-Vertrauenswert
            if query.min_confidence > 0:
                conditions.append("e.confidence >= ?")
                params.append(query.min_confidence)
            
            # Aktualität
            if not query.include_expired:
                conditions.append("(e.is_current = 1 AND (e.expires_at IS NULL OR e.expires_at > datetime('now')))")
            
            # Kombiniere Bedingungen
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            
            # Sortierung
            if query.sort_by == "date":
                sql += " ORDER BY e.updated_at DESC"
            elif query.sort_by == "confidence":
                sql += " ORDER BY e.confidence DESC"
            else:  # relevance (Standard)
                sql += " ORDER BY rank"  # Volltextsuche-Rang
            
            # Limit
            sql += f" LIMIT {query.max_results}"
            
            # Führe Abfrage aus
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            # Konvertiere Ergebnisse
            results = []
            sources_used = set()
            for row in rows:
                source = KnowledgeSource(
                    id=row["id_1"],
                    name=row["name"],
                    url=row["url"],
                    source_type=KnowledgeSourceType(row["source_type"]),
                    trust_score=row["trust_score"],
                    last_updated=datetime.fromisoformat(row["last_updated"]),
                    description=row["description"],
                    is_active=bool(row["is_active"]),
                )
                entry = KnowledgeEntry(
                    id=row["id"],
                    title=row["title"],
                    content=row["content"],
                    category=KnowledgeCategory(row["category"]),
                    source=source,
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    version=row["version"],
                    tags=json.loads(row["tags"]),
                    metadata=json.loads(row["metadata"]),
                    confidence=row["confidence"],
                    verification_status=row["verification_status"],
                    verification_count=row["verification_count"],
                    last_verified=datetime.fromisoformat(row["last_verified"]) if row["last_verified"] else None,
                    is_current=bool(row["is_current"]),
                    expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
                )
                results.append(entry)
                sources_used.add(source.id)
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            return KnowledgeResult(
                query=query.query,
                results=results,
                total_results=len(results),
                sources_used=list(sources_used),
                execution_time=execution_time,
                cached=False,
            )
    
    def get_entries_by_category(self, category: KnowledgeCategory, limit: int = 10) -> list[KnowledgeEntry]:
        """Holt Einträge einer bestimmten Kategorie"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.*, s.* FROM entries e 
                JOIN sources s ON e.source_id = s.id 
                WHERE e.category = ? 
                ORDER BY e.updated_at DESC 
                LIMIT ?
            """, (category.value, limit))
            
            results = []
            for row in cursor.fetchall():
                source = KnowledgeSource(
                    id=row["id_1"],
                    name=row["name"],
                    url=row["url"],
                    source_type=KnowledgeSourceType(row["source_type"]),
                    trust_score=row["trust_score"],
                    last_updated=datetime.fromisoformat(row["last_updated"]),
                    description=row["description"],
                    is_active=bool(row["is_active"]),
                )
                entry = KnowledgeEntry(
                    id=row["id"],
                    title=row["title"],
                    content=row["content"],
                    category=KnowledgeCategory(row["category"]),
                    source=source,
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    version=row["version"],
                    tags=json.loads(row["tags"]),
                    metadata=json.loads(row["metadata"]),
                    confidence=row["confidence"],
                    verification_status=row["verification_status"],
                    verification_count=row["verification_count"],
                    last_verified=datetime.fromisoformat(row["last_verified"]) if row["last_verified"] else None,
                    is_current=bool(row["is_current"]),
                    expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
                )
                results.append(entry)
            return results
    
    def get_latest_entries(self, limit: int = 10) -> list[KnowledgeEntry]:
        """Holt die neuesten Wissenseinträge"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.*, s.* FROM entries e 
                JOIN sources s ON e.source_id = s.id 
                ORDER BY e.updated_at DESC 
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                source = KnowledgeSource(
                    id=row["id_1"],
                    name=row["name"],
                    url=row["url"],
                    source_type=KnowledgeSourceType(row["source_type"]),
                    trust_score=row["trust_score"],
                    last_updated=datetime.fromisoformat(row["last_updated"]),
                    description=row["description"],
                    is_active=bool(row["is_active"]),
                )
                entry = KnowledgeEntry(
                    id=row["id"],
                    title=row["title"],
                    content=row["content"],
                    category=KnowledgeCategory(row["category"]),
                    source=source,
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    version=row["version"],
                    tags=json.loads(row["tags"]),
                    metadata=json.loads(row["metadata"]),
                    confidence=row["confidence"],
                    verification_status=row["verification_status"],
                    verification_count=row["verification_count"],
                    last_verified=datetime.fromisoformat(row["last_verified"]) if row["last_verified"] else None,
                    is_current=bool(row["is_current"]),
                    expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
                )
                results.append(entry)
            return results
    
    def cleanup_expired_entries(self) -> int:
        """Löscht abgelaufene Einträge und gibt die Anzahl zurück"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM entries 
                WHERE is_current = 0 AND expires_at < datetime('now')
            """)
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
    
    def get_stats(self) -> dict:
        """Holt Statistiken zur Wissensdatenbank"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Gesamtzahl Einträge
            cursor.execute("SELECT COUNT(*) FROM entries")
            total_entries = cursor.fetchone()[0]
            
            # Aktuelle Einträge
            cursor.execute("""
                SELECT COUNT(*) FROM entries 
                WHERE is_current = 1 AND (expires_at IS NULL OR expires_at > datetime('now'))
            """)
            current_entries = cursor.fetchone()[0]
            
            # Nach Kategorie
            cursor.execute("""
                SELECT category, COUNT(*) FROM entries 
                GROUP BY category
            """)
            categories = {row["category"]: row["COUNT(*)"] for row in cursor.fetchall()}
            
            # Nach Quelle
            cursor.execute("""
                SELECT s.id, s.name, COUNT(*) FROM entries e 
                JOIN sources s ON e.source_id = s.id 
                GROUP BY s.id
            """)
            sources = {row["id"]: {"name": row["name"], "count": row["COUNT(*)"]} for row in cursor.fetchall()}
            
            return {
                "total_entries": total_entries,
                "current_entries": current_entries,
                "categories": categories,
                "sources": sources,
            }
