"""
Response Cache - Caching für Suchergebnisse und Fetch-Anfragen
"""

from __future__ import annotations

import json
import pickle
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generic, Optional, TypeVar

from vibe.core.realtime.models import (
    FetchResponse,
    FetchResponseModel,
    SearchResult,
    SearchResultModel,
)
from vibe.observability.logging import logger


T = TypeVar('T')


class ResponseCache(Generic[T]):
    """
    Generischer Cache für Suchergebnisse und Fetch-Antworten.
    
    Unterstützt:
    - In-Memory-Cache (schnell)
    - SQLite-Cache (persistent)
    - TTL (Time-To-Live)
    - Größenbegrenzung
    """
    
    DEFAULT_DB_PATH = Path("~/.vibe/cache/responses.db").expanduser()
    DEFAULT_MAX_SIZE = 1000  # Maximale Anzahl von Einträgen
    DEFAULT_TTL = 3600  # 1 Stunde Standard-TTL
    
    def __init__(
        self,
        db_path: Path | str | None = None,
        max_size: int = DEFAULT_MAX_SIZE,
        use_disk_cache: bool = True,
    ):
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB_PATH
        self.max_size = max_size
        self.use_disk_cache = use_disk_cache
        self._memory_cache: dict[str, tuple[T, datetime, int]] = {}
        
        if self.use_disk_cache:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
    
    def _init_db(self) -> None:
        """Initialisiert die SQLite-Datenbank"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    ttl INTEGER NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at)
            """)
            conn.commit()
    
    def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """
        Speichert einen Wert im Cache.
        
        Args:
            key: Cache-Schlüssel
            value: Zu speichernder Wert
            ttl: Time-To-Live in Sekunden (Standard: DEFAULT_TTL)
        """
        if ttl is None:
            ttl = self.DEFAULT_TTL
        
        expires_at = datetime.now() + timedelta(seconds=ttl)
        
        # In-Memory-Cache
        self._memory_cache[key] = (value, datetime.now(), ttl)
        
        # Disk-Cache
        if self.use_disk_cache:
            try:
                # Serialisieren
                serialized = self._serialize(value)
                
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO cache 
                        (key, value, created_at, expires_at, ttl)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        key,
                        serialized,
                        datetime.now().isoformat(),
                        expires_at.isoformat(),
                        ttl,
                    ))
                    conn.commit()
            except Exception as e:
                logger.warning("Failed to save to disk cache: %s", e)
        
        # Cache-Größe prüfen
        if len(self._memory_cache) > self.max_size:
            self._cleanup_memory_cache()
    
    def get(self, key: str) -> T | None:
        """
        Holt einen Wert aus dem Cache.
        
        Args:
            key: Cache-Schlüssel
        
        Returns:
            Der gecachte Wert oder None, wenn nicht gefunden oder abgelaufen
        """
        # In-Memory-Cache prüfen
        if key in self._memory_cache:
            value, created_at, ttl = self._memory_cache[key]
            expires_at = created_at + timedelta(seconds=ttl)
            if datetime.now() < expires_at:
                return value
            else:
                del self._memory_cache[key]
        
        # Disk-Cache prüfen
        if self.use_disk_cache:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT value, created_at, ttl FROM cache 
                        WHERE key = ? AND expires_at > datetime('now')
                    """, (key,))
                    row = cursor.fetchone()
                    if row:
                        value = self._deserialize(row[0])
                        # In Memory-Cache speichern
                        self._memory_cache[key] = (value, datetime.fromisoformat(row[1]), row[2])
                        return value
            except Exception as e:
                logger.warning("Failed to read from disk cache: %s", e)
        
        return None
    
    def delete(self, key: str) -> bool:
        """Löscht einen Eintrag aus dem Cache"""
        deleted = False
        
        if key in self._memory_cache:
            del self._memory_cache[key]
            deleted = True
        
        if self.use_disk_cache:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
                    if cursor.rowcount > 0:
                        deleted = True
                    conn.commit()
            except Exception as e:
                logger.warning("Failed to delete from disk cache: %s", e)
        
        return deleted
    
    def clear(self) -> None:
        """Löscht alle Einträge aus dem Cache"""
        self._memory_cache.clear()
        
        if self.use_disk_cache:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM cache")
                    conn.commit()
            except Exception as e:
                logger.warning("Failed to clear disk cache: %s", e)
    
    def cleanup(self) -> int:
        """
        Bereinigt abgelaufene Einträge.
        
        Returns:
            Anzahl der gelöschten Einträge
        """
        deleted_count = 0
        
        # In-Memory-Cache bereinigen
        keys_to_delete = [
            key for key, (_, created_at, ttl) in self._memory_cache.items()
            if datetime.now() > created_at + timedelta(seconds=ttl)
        ]
        for key in keys_to_delete:
            del self._memory_cache[key]
            deleted_count += 1
        
        # Disk-Cache bereinigen
        if self.use_disk_cache:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        DELETE FROM cache WHERE expires_at < datetime('now')
                    """)
                    deleted_count += cursor.rowcount
                    conn.commit()
            except Exception as e:
                logger.warning("Failed to cleanup disk cache: %s", e)
        
        return deleted_count
    
    def _cleanup_memory_cache(self) -> int:
        """Bereinigt den In-Memory-Cache, wenn er zu groß wird"""
        # Einfache Strategie: Lösche die ältesten 20%
        if len(self._memory_cache) <= self.max_size:
            return 0
        
        # Sortiere nach Erstellungsdatum
        sorted_entries = sorted(
            self._memory_cache.items(),
            key=lambda x: x[1][1],  # created_at
        )
        
        # Lösche die ältesten 20%
        delete_count = max(1, len(sorted_entries) // 5)
        for key, _ in sorted_entries[:delete_count]:
            del self._memory_cache[key]
        
        return delete_count
    
    def _serialize(self, value: T) -> bytes:
        """Serialisiert einen Wert für die Datenbank"""
        # Für Pydantic-Modelle
        if hasattr(value, 'model_dump'):
            data = value.model_dump()
            return json.dumps(data).encode('utf-8')
        
        # Für Dataclasses
        if hasattr(value, '__dataclass_fields__'):
            data = asdict(value)
            return json.dumps(data).encode('utf-8')
        
        # Für einfache Typen
        try:
            return json.dumps(value).encode('utf-8')
        except (TypeError, ValueError):
            return pickle.dumps(value)
    
    def _deserialize(self, data: bytes) -> T:
        """Deserialisiert einen Wert aus der Datenbank"""
        try:
            # Versuche JSON
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Versuche Pickle
            return pickle.loads(data)
    
    def get_stats(self) -> dict:
        """Holt Statistiken zum Cache"""
        stats = {
            "memory_entries": len(self._memory_cache),
            "max_size": self.max_size,
        }
        
        if self.use_disk_cache:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM cache")
                    stats["disk_entries"] = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM cache WHERE expires_at < datetime('now')")
                    stats["expired_entries"] = cursor.fetchone()[0]
            except Exception as e:
                logger.warning("Failed to get disk cache stats: %s", e)
                stats["disk_entries"] = 0
                stats["expired_entries"] = 0
        
        return stats
    
    def get_keys(self) -> list[str]:
        """Holt alle Cache-Schlüssel"""
        keys = list(self._memory_cache.keys())
        
        if self.use_disk_cache:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT key FROM cache")
                    keys.extend([row[0] for row in cursor.fetchall()])
            except Exception as e:
                logger.warning("Failed to get disk cache keys: %s", e)
        
        return list(set(keys))
