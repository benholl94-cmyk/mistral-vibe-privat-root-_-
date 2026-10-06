"""
Trust Scoring - Berechnung und Verwaltung von Vertrauenswerten
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from vibe.core.trust.models import (
    TrustLevel,
    TrustScore,
    TrustType,
    TrustNetwork,
    TrustRelationship,
)
from vibe.core.knowledge.models import KnowledgeSourceType
from vibe.core.community.models import UserReputation
from vibe.observability.logging import logger


class TrustScoring:
    """
    System zur Berechnung und Verwaltung von Vertrauenswerten.
    
    Features:
    - Vertrauenswerte für Quellen, Benutzer und Inhalte
    - Vertrauenspropagierung durch Beziehungen
    - Zeitbasierte Anpassung
    - Betrugserkennung
    """
    
    DEFAULT_STORAGE_PATH = Path("~/.vibe/trust/scores.json").expanduser()
    
    # Standard-Vertrauenswerte für verschiedene Typen
    DEFAULT_TRUST_SCORES = {
        TrustType.SOURCE: {
            KnowledgeSourceType.OFFICIAL: 0.9,
            KnowledgeSourceType.COMMUNITY: 0.6,
            KnowledgeSourceType.WEB: 0.5,
            KnowledgeSourceType.API: 0.7,
            KnowledgeSourceType.MANUAL: 0.8,
        },
        TrustType.USER: 0.5,
        TrustType.CONTENT: 0.5,
        TrustType.SYSTEM: 0.9,
    }
    
    # Vertrauenswürdige Domains
    TRUSTED_DOMAINS = {
        # Offizielle Quellen
        "gov": 0.95,
        "edu": 0.90,
        "eu": 0.90,
        "bundesregierung.de": 0.95,
        "eur-lex.europa.eu": 0.98,
        
        # Nachrichten
        "heise.de": 0.90,
        "golem.de": 0.85,
        "spiegel.de": 0.85,
        "zeit.de": 0.85,
        "faz.net": 0.85,
        "sueddeutsche.de": 0.85,
        "tagesschau.de": 0.90,
        
        # Technologie
        "github.com": 0.85,
        "pypi.org": 0.90,
        "python.org": 0.95,
        "mistral.ai": 0.90,
        "arxiv.org": 0.90,
        "wikipedia.org": 0.80,
        
        # Wissenschaft
        "nature.com": 0.95,
        "science.org": 0.95,
        "ieee.org": 0.90,
        "acm.org": 0.90,
    }
    
    # Unzuverlässige Domains
    UNTRUSTED_DOMAINS = {
        "facebook.com": 0.2,
        "twitter.com": 0.3,
        "x.com": 0.3,
        "instagram.com": 0.2,
        "tiktok.com": 0.2,
        "reddit.com": 0.4,
        "4chan.org": 0.1,
        "8kun.top": 0.1,
    }
    
    def __init__(self, storage_path: Path | str | None = None):
        self.storage_path = Path(storage_path) if storage_path else self.DEFAULT_STORAGE_PATH
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._scores: dict[str, TrustScore] = {}
        self._networks: dict[str, TrustNetwork] = {}
        self._load_scores()
    
    def _load_scores(self) -> None:
        """Lädt alle Vertrauenswerte aus dem Speicher"""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entity_id, entity_data in data.get("scores", {}).items():
                    self._scores[entity_id] = TrustScore(**entity_data)
                for network_name, network_data in data.get("networks", {}).items():
                    self._networks[network_name] = TrustNetwork(**network_data)
        except Exception as e:
            logger.error("Failed to load trust scores: %s", e)
    
    def _save_scores(self) -> None:
        """Speichert alle Vertrauenswerte"""
        try:
            data = {
                "scores": {
                    entity_id: score.to_dict()
                    for entity_id, score in self._scores.items()
                },
                "networks": {
                    name: network.to_dict()
                    for name, network in self._networks.items()
                },
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save trust scores: %s", e)
    
    def get_trust_score(self, entity_id: str, entity_type: TrustType) -> TrustScore:
        """Holt den Vertrauenswert einer Entität"""
        key = self._generate_key(entity_id, entity_type)
        
        if key not in self._scores:
            # Erstelle neuen Vertrauenswert mit Standardwert
            default_score = self.DEFAULT_TRUST_SCORES.get(entity_type, 0.5)
            if isinstance(default_score, dict):
                # Für Quellen: Verwende den passenden Standardwert
                default_score = default_score.get(getattr(entity_type, "value", entity_type), 0.5)
            
            score = TrustScore(
                entity_id=entity_id,
                entity_type=entity_type,
                score=default_score,
            )
            score.update_level()
            self._scores[key] = score
        
        return self._scores[key]
    
    def set_trust_score(
        self,
        entity_id: str,
        entity_type: TrustType,
        score: float,
        evidence: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TrustScore:
        """Setzt den Vertrauenswert einer Entität"""
        key = self._generate_key(entity_id, entity_type)
        
        if key not in self._scores:
            self._scores[key] = TrustScore(
                entity_id=entity_id,
                entity_type=entity_type,
                score=score,
                evidence=evidence or [],
                metadata=metadata or {},
            )
        else:
            self._scores[key].score = score
            if evidence:
                self._scores[key].evidence = evidence
            if metadata:
                self._scores[key].metadata.update(metadata)
        
        self._scores[key].last_updated = datetime.now()
        self._scores[key].update_level()
        self._save_scores()
        
        return self._scores[key]
    
    def update_trust_score(
        self,
        entity_id: str,
        entity_type: TrustType,
        delta: float,
        evidence: str | None = None,
    ) -> TrustScore:
        """Aktualisiert den Vertrauenswert einer Entität"""
        score = self.get_trust_score(entity_id, entity_type)
        old_score = score.score
        
        # Wende Delta an
        score.score = max(0.0, min(1.0, score.score + delta))
        
        if evidence:
            score.evidence.append(evidence)
        
        score.last_updated = datetime.now()
        score.update_level()
        self._save_scores()
        
        logger.info(
            "Updated trust score for %s (%s): %s -> %s",
            entity_id,
            entity_type.value,
            old_score,
            score.score,
        )
        
        return score
    
    def _generate_key(self, entity_id: str, entity_type: TrustType) -> str:
        """Generiert einen eindeutigen Schlüssel für eine Entität"""
        return f"{entity_type.value}:{entity_id}"
    
    def calculate_source_trust(self, url: str, source_type: KnowledgeSourceType = KnowledgeSourceType.WEB) -> float:
        """Berechnet den Vertrauenswert einer Quelle"""
        # Extrahiere Domain
        domain = self._extract_domain(url)
        if not domain:
            return 0.5
        
        # Prüfe auf vertrauenswürdige Domains
        for trusted_domain, score in self.TRUSTED_DOMAINS.items():
            if trusted_domain in domain:
                return min(1.0, score * 1.1)  # Bonus für vertrauenswürdige Quellen
        
        # Prüfe auf unzuverlässige Domains
        for untrusted_domain, score in self.UNTRUSTED_DOMAINS.items():
            if untrusted_domain in domain:
                return score
        
        # Standardwert basierend auf Quelle-Typ
        default_score = self.DEFAULT_TRUST_SCORES.get(TrustType.SOURCE, {}).get(source_type, 0.5)
        return default_score
    
    def calculate_user_trust(self, user_reputation: UserReputation) -> float:
        """Berechnet den Vertrauenswert eines Benutzers basierend auf seiner Reputation"""
        # Skalierung von 0-100 auf 0-1
        return user_reputation.score / 100.0
    
    def calculate_content_trust(
        self,
        content: str,
        source_trust: float,
        author_trust: float = 0.5,
    ) -> float:
        """Berechnet den Vertrauenswert von Inhalt"""
        # Basis: Durchschnitt von Quelle und Autor
        base_trust = (source_trust + author_trust) / 2.0
        
        # Prüfe auf Qualitätsindikatoren
        quality_indicators = 0
        
        # Länge des Inhalts
        if len(content) >= 100:
            quality_indicators += 1
        
        # Vorhandensein von Quellen
        if "quelle" in content.lower() or "source" in content.lower():
            quality_indicators += 1
        
        # Vorhandensein von Belegen
        if "beleg" in content.lower() or "evidence" in content.lower():
            quality_indicators += 1
        
        # Anpassung basierend auf Qualitätsindikatoren
        quality_bonus = quality_indicators * 0.1
        
        return min(1.0, base_trust + quality_bonus)
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extrahiert die Domain aus einer URL"""
        # Entferne Protokoll
        url = url.replace("https://", "").replace("http://", "").replace("www.", "")
        
        # Extrahiere Domain
        domain = url.split("/")[0].split("?")[0].split("#")[0]
        
        # Entferne Port
        domain = domain.split(":")[0]
        
        return domain.lower() if domain else None
    
    def create_trust_network(self, name: str, description: str = "") -> TrustNetwork:
        """Erstellt ein neues Vertrauensnetzwerk"""
        network = TrustNetwork(
            name=name,
            description=description,
        )
        self._networks[name] = network
        self._save_scores()
        return network
    
    def add_entity_to_network(self, network_name: str, entity_id: str, entity_type: TrustType) -> bool:
        """Fügt eine Entität zu einem Vertrauensnetzwerk hinzu"""
        if network_name not in self._networks:
            return False
        
        network = self._networks[network_name]
        if entity_id not in network.entities:
            network.entities.append(entity_id)
            network.last_updated = datetime.now()
            self._save_scores()
        
        return True
    
    def add_relationship(
        self,
        network_name: str,
        source_id: str,
        source_type: TrustType,
        target_id: str,
        target_type: TrustType,
        trust_score: float,
        relationship_type: str = "default",
    ) -> bool:
        """Fügt eine Vertrauensbeziehung zu einem Netzwerk hinzu"""
        if network_name not in self._networks:
            return False
        
        network = self._networks[network_name]
        
        relationship = TrustRelationship(
            source_id=source_id,
            source_type=source_type,
            target_id=target_id,
            target_type=target_type,
            trust_score=trust_score,
            relationship_type=relationship_type,
        )
        
        network.relationships.append(relationship)
        network.last_updated = datetime.now()
        self._save_scores()
        
        return True
    
    def propagate_trust(self, network_name: str, iterations: int = 3) -> dict[str, float]:
        """
        Propagiert Vertrauenswerte durch ein Netzwerk.
        
        Args:
            network_name: Name des Netzwerks
            iterations: Anzahl der Iterationen
        
        Returns:
            Dictionary mit den aktualisierten Vertrauenswerten
        """
        if network_name not in self._networks:
            return {}
        
        network = self._networks[network_name]
        updated_scores: dict[str, float] = {}
        
        for _ in range(iterations):
            for relationship in network.relationships:
                # Hole aktuellen Vertrauenswert der Quelle
                source_score = self.get_trust_score(relationship.source_id, relationship.source_type).score
                
                # Berechne neuen Vertrauenswert für das Ziel
                target_key = self._generate_key(relationship.target_id, relationship.target_type)
                if target_key not in self._scores:
                    self._scores[target_key] = TrustScore(
                        entity_id=relationship.target_id,
                        entity_type=relationship.target_type,
                        score=0.5,
                    )
                
                target_score = self._scores[target_key]
                
                # Propagierung: Ziel = Ziel * (1 - alpha) + Quelle * alpha * Beziehung
                alpha = 0.2  # Lernrate
                new_score = (
                    target_score.score * (1.0 - alpha) +
                    source_score * alpha * relationship.trust_score
                )
                
                # Aktualisiere nur, wenn sich der Wert signifikant ändert
                if abs(new_score - target_score.score) > 0.01:
                    target_score.score = new_score
                    target_score.last_updated = datetime.now()
                    target_score.update_level()
                    updated_scores[target_key] = new_score
        
        self._save_scores()
        return updated_scores
    
    def get_network_trust(self, network_name: str) -> dict[str, float]:
        """Holt alle Vertrauenswerte in einem Netzwerk"""
        if network_name not in self._networks:
            return {}
        
        network = self._networks[network_name]
        result = {}
        
        for entity_id in network.entities:
            # Versuche alle Typen
            for entity_type in TrustType:
                key = self._generate_key(entity_id, entity_type)
                if key in self._scores:
                    result[entity_id] = self._scores[key].score
                    break
        
        return result
    
    def detect_fraud(self, entity_id: str, entity_type: TrustType) -> dict:
        """
        Erkennt potenziellen Betrug für eine Entität.
        
        Args:
            entity_id: ID der Entität
            entity_type: Typ der Entität
        
        Returns:
            Dictionary mit Betrugsindikatoren und Score
        """
        score = self.get_trust_score(entity_id, entity_type)
        indicators = []
        fraud_score = 0.0
        
        # Prüfe auf niedrigen Vertrauenswert
        if score.score < 0.3:
            indicators.append("Low trust score")
            fraud_score += 0.4
        
        # Prüfe auf fehlende Beweise
        if not score.evidence:
            indicators.append("No evidence")
            fraud_score += 0.2
        
        # Prüfe auf kürzliche Änderungen
        if score.last_updated:
            age = (datetime.now() - score.last_updated).total_seconds()
            if age < 3600:  # Weniger als 1 Stunde
                indicators.append("Recently changed")
                fraud_score += 0.1
        
        # Prüfe auf extreme Werte
        if score.score < 0.1 or score.score > 0.95:
            indicators.append("Extreme trust score")
            fraud_score += 0.2
        
        # Normalisieren
        fraud_score = min(1.0, fraud_score)
        
        return {
            "entity_id": entity_id,
            "entity_type": entity_type.value,
            "trust_score": score.score,
            "fraud_score": fraud_score,
            "is_fraudulent": fraud_score >= 0.7,
            "indicators": indicators,
        }
    
    def get_stats(self) -> dict:
        """Holt Statistiken zum Vertrauenssystem"""
        return {
            "total_scores": len(self._scores),
            "total_networks": len(self._networks),
            "trust_distribution": self._calculate_trust_distribution(),
            "networks": list(self._networks.keys()),
        }
    
    def _calculate_trust_distribution(self) -> dict[str, int]:
        """Berechnet die Verteilung der Vertrauenswerte"""
        distribution = {
            "untrusted": 0,
            "low": 0,
            "neutral": 0,
            "trusted": 0,
            "highly_trusted": 0,
        }
        
        for score in self._scores.values():
            level = score.level.value
            if level in distribution:
                distribution[level] += 1
        
        return distribution
    
    def reset_score(self, entity_id: str, entity_type: TrustType) -> None:
        """Setzt den Vertrauenswert einer Entität auf den Standardwert zurück"""
        key = self._generate_key(entity_id, entity_type)
        if key in self._scores:
            del self._scores[key]
        self._save_scores()
    
    def reset_all(self) -> None:
        """Setzt alle Vertrauenswerte zurück"""
        self._scores.clear()
        self._networks.clear()
        self._save_scores()
