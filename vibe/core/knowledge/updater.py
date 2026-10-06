"""
Wissensdatenbank-Updater - Automatische Aktualisierung von Wissen
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import aiohttp
import feedparser
from pydantic import BaseModel

from vibe.core.knowledge.database import KnowledgeDatabase
from vibe.core.knowledge.models import (
    KnowledgeCategory,
    KnowledgeEntry,
    KnowledgeSource,
    KnowledgeSourceType,
)
from vibe.observability.logging import logger


@dataclass
class UpdateConfig:
    """Konfiguration für den Updater"""
    update_interval_hours: int = 1  # Standard: 1 Stunde
    max_entries_per_source: int = 100
    default_expiration_days: int = 30
    default_confidence: float = 0.7
    
    # Quellen-Konfiguration
    news_sources: list[dict] = field(default_factory=lambda: [
        {"name": "Heise Online", "url": "https://www.heise.de/feeds/news.rdf", "type": "rss"},
        {"name": "Golem", "url": "https://rss.golem.de/rss.php?feed=RSS2.0", "type": "rss"},
        {"name": "Spiegel Online", "url": "https://www.spiegel.de/schlagzeilen/tops/rss-0,520,0.xml", "type": "rss"},
    ])
    tech_sources: list[dict] = field(default_factory=lambda: [
        {"name": "GitHub Trending", "url": "https://api.github.com/search/repositories?q=created:>2026-01-01", "type": "api"},
        {"name": "PyPI Updates", "url": "https://pypi.org/rss/updates.xml", "type": "rss"},
        {"name": "Hacker News", "url": "https://hnrss.org/newest", "type": "rss"},
    ])
    legal_sources: list[dict] = field(default_factory=lambda: [
        {"name": "EU AI Act", "url": "https://digital-strategy.ec.europa.eu/en/policies/ai-act", "type": "web"},
        {"name": "Bundesregierung KI", "url": "https://www.bundesregierung.de/breg-de/themen/digitalisierung/ki", "type": "web"},
    ])


@dataclass
class UpdateResult:
    """Ergebnis eines Update-Vorgangs"""
    source_name: str
    entries_added: int
    entries_updated: int
    entries_removed: int
    errors: list[str]
    execution_time: float


class KnowledgeUpdater:
    """
    Automatischer Updater für die Wissensdatenbank.
    
    Unterstützt:
    - RSS-Feeds
    - Web-APIs
    - Web-Scraping (begrenzt)
    - Manuelle Einträge
    """
    
    def __init__(self, db: KnowledgeDatabase | None = None, config: UpdateConfig | None = None):
        self.db = db or KnowledgeDatabase()
        self.config = config or UpdateConfig()
        self._session: aiohttp.ClientSession | None = None
        self._running = False
    
    async def start_periodic_updates(self) -> None:
        """Startet die periodischen Aktualisierungen"""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting periodic knowledge updates (every %d hours)", self.config.update_interval_hours)
        
        while self._running:
            start_time = datetime.now()
            try:
                await self.update_all()
            except Exception as e:
                logger.error("Error during periodic update: %s", e, exc_info=True)
            
            # Warte bis zur nächsten Aktualisierung
            wait_time = timedelta(hours=self.config.update_interval_hours) - (datetime.now() - start_time)
            if wait_time.total_seconds() > 0:
                await asyncio.sleep(wait_time.total_seconds())
    
    async def stop_periodic_updates(self) -> None:
        """Stoppt die periodischen Aktualisierungen"""
        self._running = False
        if self._session:
            await self._session.close()
    
    async def update_all(self) -> list[UpdateResult]:
        """Aktualisiert alle Quellen"""
        results = []
        
        # News-Quellen
        for source_config in self.config.news_sources:
            result = await self._update_source(source_config, KnowledgeCategory.NEWS)
            results.append(result)
        
        # Tech-Quellen
        for source_config in self.config.tech_sources:
            result = await self._update_source(source_config, KnowledgeCategory.TECHNOLOGY)
            results.append(result)
        
        # Legal-Quellen
        for source_config in self.config.legal_sources:
            result = await self._update_source(source_config, KnowledgeCategory.LEGAL)
            results.append(result)
        
        # Bereinigung
        deleted_count = self.db.cleanup_expired_entries()
        if deleted_count > 0:
            logger.info("Cleaned up %d expired entries", deleted_count)
        
        return results
    
    async def _update_source(self, source_config: dict, default_category: KnowledgeCategory) -> UpdateResult:
        """Aktualisiert eine einzelne Quelle"""
        start_time = datetime.now()
        source_name = source_config["name"]
        source_url = source_config["url"]
        source_type = source_config.get("type", "rss")
        
        errors = []
        entries_added = 0
        entries_updated = 0
        
        try:
            # Quelle in der Datenbank registrieren
            source = KnowledgeSource(
                id=f"source_{hashlib.md5(source_url.encode()).hexdigest()}",
                name=source_name,
                url=source_url,
                source_type=KnowledgeSourceType(source_type),
                trust_score=0.8,  # Standard-Vertrauenswert für bekannte Quellen
                description=source_config.get("description", ""),
            )
            self.db.add_source(source)
            
            # Daten abrufen
            if source_type == "rss":
                items = await self._fetch_rss(source_url)
            elif source_type == "api":
                items = await self._fetch_api(source_url)
            elif source_type == "web":
                items = await self._fetch_web(source_url)
            else:
                items = []
            
            # Verarbeite Items
            for item in items:
                try:
                    entry = self._create_entry_from_item(item, source, default_category)
                    existing = self.db.get_entry(entry.id)
                    if existing:
                        # Aktualisiere bestehenden Eintrag
                        entry.version = existing.version + 1
                        entry.updated_at = datetime.now()
                        self.db.add_entry(entry)
                        entries_updated += 1
                    else:
                        # Neuer Eintrag
                        self.db.add_entry(entry)
                        entries_added += 1
                except Exception as e:
                    errors.append(f"Error processing item: {e}")
                    logger.warning("Error processing item from %s: %s", source_name, e)
            
        except Exception as e:
            errors.append(f"Error fetching from {source_name}: {e}")
            logger.error("Error fetching from %s: %s", source_name, e, exc_info=True)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return UpdateResult(
            source_name=source_name,
            entries_added=entries_added,
            entries_updated=entries_updated,
            entries_removed=0,
            errors=errors,
            execution_time=execution_time,
        )
    
    async def _fetch_rss(self, url: str) -> list[dict]:
        """Lädt einen RSS-Feed"""
        async with self._get_session() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status} for {url}")
                
                content = await response.text()
                feed = feedparser.parse(content)
                
                items = []
                for entry in feed.entries:
                    # Extrahiere relevante Daten
                    item = {
                        "id": entry.get("id", entry.get("link", "")),
                        "title": entry.get("title", ""),
                        "content": entry.get("description", "") or entry.get("summary", ""),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "updated": entry.get("updated", ""),
                    }
                    items.append(item)
                
                return items
    
    async def _fetch_api(self, url: str) -> list[dict]:
        """Lädt Daten von einer API"""
        async with self._get_session() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status} for {url}")
                
                data = await response.json()
                
                # Beispiel: GitHub API
                if "github.com" in url:
                    items = []
                    for repo in data.get("items", []):
                        item = {
                            "id": repo.get("id", ""),
                            "title": repo.get("name", ""),
                            "content": repo.get("description", ""),
                            "link": repo.get("html_url", ""),
                            "published": repo.get("created_at", ""),
                        }
                        items.append(item)
                    return items
                
                # Standardfall
                return [{"id": "api_data", "title": "API Data", "content": str(data), "link": url}]
    
    async def _fetch_web(self, url: str) -> list[dict]:
        """Lädt Daten von einer Webseite (einfaches Scraping)"""
        async with self._get_session() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status} for {url}")
                
                content = await response.text()
                
                # Einfache Extraktion (könnte mit BeautifulSoup erweitert werden)
                return [{
                    "id": url,
                    "title": f"Content from {url}",
                    "content": content[:5000],  # Max. 5000 Zeichen
                    "link": url,
                }]
    
    def _create_entry_from_item(self, item: dict, source: KnowledgeSource, default_category: KnowledgeCategory) -> KnowledgeEntry:
        """Erstellt einen Wissenseintrag aus einem Item"""
        # Generiere eine einzigartige ID
        content_hash = hashlib.md5(item.get("content", "").encode()).hexdigest()[:8]
        entry_id = f"{source.id}_{content_hash}"
        
        # Bestimme Kategorie
        category = self._determine_category(item, default_category)
        
        # Parsen von Datumsangaben
        published_at = None
        for date_field in ["published", "updated", "pubDate"]:
            if date_field in item and item[date_field]:
                try:
                    published_at = datetime.fromisoformat(item[date_field].replace("Z", "+00:00"))
                    break
                except ValueError:
                    continue
        
        # Erstelle den Eintrag
        return KnowledgeEntry(
            id=entry_id,
            title=item.get("title", "Untitled"),
            content=item.get("content", ""),
            category=category,
            source=source,
            created_at=published_at or datetime.now(),
            updated_at=datetime.now(),
            version=1,
            tags=self._extract_tags(item),
            metadata={
                "original_url": item.get("link", ""),
                "source_type": source.source_type.value,
            },
            confidence=self.config.default_confidence,
            verification_status="unverified",
            verification_count=0,
            last_verified=None,
            is_current=True,
            expires_at=datetime.now() + timedelta(days=self.config.default_expiration_days),
        )
    
    def _determine_category(self, item: dict, default_category: KnowledgeCategory) -> KnowledgeCategory:
        """Bestimmt die Kategorie basierend auf dem Item"""
        title = item.get("title", "").lower()
        content = item.get("content", "").lower()
        
        # KI/Technologie
        if any(keyword in title or keyword in content for keyword in ["ki", "künstliche intelligenz", "ai", "machine learning", "python", "javascript", "github"]):
            return KnowledgeCategory.TECHNOLOGY
        
        # Rechtliches
        if any(keyword in title or keyword in content for keyword in ["gesetz", "ai act", "regulierung", "datenschutz", "dsgvo"]):
            return KnowledgeCategory.LEGAL
        
        # Sicherheit
        if any(keyword in title or keyword in content for keyword in ["sicherheit", "cve", "exploit", "hack", "vulnerability"]):
            return KnowledgeCategory.SECURITY
        
        # Standardmäßig die übergebene Kategorie
        return default_category
    
    def _extract_tags(self, item: dict) -> list[str]:
        """Extrahiert Tags aus einem Item"""
        tags = []
        
        # Aus Titel
        title = item.get("title", "").lower()
        for keyword in ["ki", "ai", "python", "javascript", "github", "security", "update", "new", "release"]:
            if keyword in title:
                tags.append(keyword)
        
        # Aus Kategorien (falls vorhanden)
        if "categories" in item and isinstance(item["categories"], list):
            tags.extend([tag.lower() for tag in item["categories"]])
        
        # Entferne Duplikate
        return list(set(tags))
    
    @asynccontextmanager
    async def _get_session(self) -> aiohttp.ClientSession:
        """Holt oder erstellt eine aiohttp-Session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "Vibe Knowledge Updater/1.0"}
            )
        try:
            yield self._session
        except Exception:
            if self._session:
                await self._session.close()
                self._session = None
            raise
    
    async def add_manual_entry(
        self,
        title: str,
        content: str,
        category: KnowledgeCategory,
        source_url: str,
        source_name: str,
        trust_score: float = 0.7,
    ) -> KnowledgeEntry:
        """Fügt manuell einen Wissenseintrag hinzu"""
        source = KnowledgeSource(
            id=f"manual_{hashlib.md5(source_url.encode()).hexdigest()}",
            name=source_name,
            url=source_url,
            source_type=KnowledgeSourceType.MANUAL,
            trust_score=trust_score,
        )
        
        entry = KnowledgeEntry(
            id=f"manual_{hashlib.md5(content.encode()).hexdigest()[:16]}",
            title=title,
            content=content,
            category=category,
            source=source,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            version=1,
            confidence=trust_score,
        )
        
        return self.db.add_entry(entry)
    
    async def verify_entry(self, entry_id: str, verified: bool, source: str = "") -> bool:
        """Verifiziert oder widerlegt einen Wissenseintrag"""
        entry = self.db.get_entry(entry_id)
        if not entry:
            return False
        
        entry.verification_count += 1
        entry.verification_status = "verified" if verified else "disputed"
        entry.last_verified = datetime.now()
        
        # Passe Vertrauenswert an
        if verified:
            entry.confidence = min(1.0, entry.confidence + 0.1)
        else:
            entry.confidence = max(0.0, entry.confidence - 0.2)
        
        self.db.add_entry(entry)
        return True
