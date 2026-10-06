"""
Reputation System - Reputationsmanagement für Community-Mitglieder
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from vibe.core.community.models import UserReputation
from vibe.observability.logging import logger


class ReputationSystem:
    """
    Verwaltet die Reputation von Community-Mitgliedern.
    
    Features:
    - Reputations-Score Berechnung
    - Level-System
    - Belohnungen und Strafen
    - Zeitbasierte Abnahme (Decay)
    """
    
    DEFAULT_STORAGE_PATH = Path("~/.vibe/community/reputations.json").expanduser()
    
    # Reputations-Aktionen
    REPUTATION_ACTIONS = {
        "create_contribution": {
            "points": 1.0,
            "description": "Beitrag erstellt",
        },
        "upvote_received": {
            "points": 0.5,
            "description": "Upvote erhalten",
        },
        "downvote_received": {
            "points": -0.2,
            "description": "Downvote erhalten",
        },
        "verify_contribution": {
            "points": 2.0,
            "description": "Beitrag verifiziert",
        },
        "contribution_approved": {
            "points": 5.0,
            "description": "Beitrag genehmigt",
        },
        "contribution_rejected": {
            "points": -2.0,
            "description": "Beitrag abgelehnt",
        },
        "spam_report": {
            "points": -5.0,
            "description": "Spam gemeldet",
        },
        "daily_login": {
            "points": 0.1,
            "description": "Tägliche Anmeldung",
        },
    }
    
    # Level-Schwellenwerte
    LEVEL_THRESHOLDS = {
        1: 0,
        2: 20,
        3: 50,
        4: 100,
        5: 200,
    }
    
    # Decay-Rate (tägliche Abnahme)
    DAILY_DECAY_RATE = 0.01  # 1% pro Tag
    
    def __init__(self, storage_path: Path | str | None = None):
        self.storage_path = Path(storage_path) if storage_path else self.DEFAULT_STORAGE_PATH
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._reputations: dict[str, UserReputation] = {}
        self._load_reputations()
    
    def _load_reputations(self) -> None:
        """Lädt alle Reputationen aus dem Speicher"""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for user_id, user_data in data.items():
                    self._reputations[user_id] = UserReputation(**user_data)
        except Exception as e:
            logger.error("Failed to load reputations: %s", e)
    
    def _save_reputations(self) -> None:
        """Speichert alle Reputationen"""
        try:
            data = {
                user_id: reputation.to_dict()
                for user_id, reputation in self._reputations.items()
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save reputations: %s", e)
    
    def get_reputation(self, user_id: str) -> UserReputation:
        """Holt die Reputation eines Benutzers"""
        if user_id not in self._reputations:
            self._reputations[user_id] = UserReputation(
                user_id=user_id,
                user_name=f"user_{user_id}",
            )
        return self._reputations[user_id]
    
    def update_reputation(
        self,
        user_id: str,
        user_name: str | None = None,
        **kwargs,
    ) -> UserReputation:
        """Aktualisiert die Reputation eines Benutzers"""
        reputation = self.get_reputation(user_id)
        
        if user_name:
            reputation.user_name = user_name
        
        for key, value in kwargs.items():
            if hasattr(reputation, key):
                setattr(reputation, key, value)
        
        reputation.last_active = datetime.now()
        self._save_reputations()
        return reputation
    
    def add_points(self, user_id: str, action: str, context: dict[str, Any] | None = None) -> UserReputation:
        """
        Fügt Reputations-Punkte für eine Aktion hinzu.
        
        Args:
            user_id: ID des Benutzers
            action: Aktionsname
            context: Zusätzlicher Kontext
        
        Returns:
            Aktualisierte Reputation
        """
        if action not in self.REPUTATION_ACTIONS:
            logger.warning("Unknown reputation action: %s", action)
            return self.get_reputation(user_id)
        
        reputation = self.get_reputation(user_id)
        action_info = self.REPUTATION_ACTIONS[action]
        
        # Füge Punkte hinzu
        reputation.score = max(0.0, min(100.0, reputation.score + action_info["points"]))
        
        # Aktualisiere Statistiken basierend auf Aktion
        if action == "create_contribution":
            reputation.contributions += 1
        elif action == "upvote_received":
            reputation.upvotes_received += 1
        elif action == "downvote_received":
            reputation.downvotes_received += 1
        elif action == "verify_contribution":
            reputation.verified_contributions += 1
        elif action == "contribution_approved":
            reputation.contributions += 1
        
        # Aktualisiere Level
        self._update_level(reputation)
        
        # Speichern
        self._save_reputations()
        
        logger.info(
            "Added %s points to %s for %s (new score: %s)",
            action_info["points"],
            user_id,
            action,
            reputation.score,
        )
        return reputation
    
    def remove_points(self, user_id: str, amount: float, reason: str) -> UserReputation:
        """
        Entfernt Reputations-Punkte.
        
        Args:
            user_id: ID des Benutzers
            amount: Anzahl Punkte
            reason: Grund für die Entfernung
        
        Returns:
            Aktualisierte Reputation
        """
        reputation = self.get_reputation(user_id)
        reputation.score = max(0.0, reputation.score - amount)
        
        # Aktualisiere Level
        self._update_level(reputation)
        
        # Speichern
        self._save_reputations()
        
        logger.warning("Removed %s points from %s: %s (new score: %s)", amount, user_id, reason, reputation.score)
        return reputation
    
    def _update_level(self, reputation: UserReputation) -> None:
        """Aktualisiert das Level basierend auf dem Score"""
        for level, threshold in sorted(self.LEVEL_THRESHOLDS.items(), reverse=True):
            if reputation.score >= threshold:
                reputation.level = level
                return
        
        reputation.level = 1
    
    def get_level_info(self, level: int) -> dict:
        """Holt Informationen zu einem Level"""
        level_info = {
            1: {
                "name": "Newcomer",
                "description": "Neues Mitglied",
                "color": "gray",
                "min_score": 0,
                "max_score": 19,
            },
            2: {
                "name": "Contributor",
                "description": "Aktives Mitglied",
                "color": "blue",
                "min_score": 20,
                "max_score": 49,
            },
            3: {
                "name": "Trusted Contributor",
                "description": "Vertrauenswürdiges Mitglied",
                "color": "green",
                "min_score": 50,
                "max_score": 99,
            },
            4: {
                "name": "Expert",
                "description": "Experte",
                "color": "purple",
                "min_score": 100,
                "max_score": 199,
            },
            5: {
                "name": "Master",
                "description": "Meister",
                "color": "gold",
                "min_score": 200,
                "max_score": float('inf'),
            },
        }
        
        return level_info.get(level, {
            "name": "Unknown",
            "description": "Unbekannt",
            "color": "gray",
            "min_score": 0,
            "max_score": 0,
        })
    
    def get_leaderboard(self, limit: int = 20) -> list[dict]:
        """Holt die Bestenliste"""
        sorted_reputations = sorted(
            self._reputations.values(),
            key=lambda x: x.score,
            reverse=True,
        )[:limit]
        
        return [
            {
                "rank": i + 1,
                "user_id": r.user_id,
                "user_name": r.user_name,
                "score": r.score,
                "level": r.level,
                "level_name": self.get_level_info(r.level)["name"],
                "contributions": r.contributions,
                "verified_contributions": r.verified_contributions,
            }
            for i, r in enumerate(sorted_reputations)
        ]
    
    def apply_daily_decay(self) -> int:
        """
        Wendet den täglichen Decay auf alle Reputationen an.
        
        Returns:
            Anzahl der aktualisierten Reputationen
        """
        updated_count = 0
        
        for user_id, reputation in self._reputations.items():
            # Prüfe, ob Decay angewendet werden soll (1x pro Tag)
            last_decay = getattr(reputation, "_last_decay", None)
            if last_decay:
                last_decay = datetime.fromisoformat(last_decay) if isinstance(last_decay, str) else last_decay
            
            if last_decay is None or (datetime.now() - last_decay).days >= 1:
                # Wende Decay an
                old_score = reputation.score
                reputation.score = max(0.0, reputation.score * (1.0 - self.DAILY_DECAY_RATE))
                reputation._last_decay = datetime.now().isoformat()
                
                if old_score != reputation.score:
                    updated_count += 1
        
        self._save_reputations()
        logger.info("Applied daily decay to %d reputations", updated_count)
        return updated_count
    
    def get_stats(self) -> dict:
        """Holt Statistiken zum Reputationssystem"""
        total_users = len(self._reputations)
        total_score = sum(r.score for r in self._reputations.values())
        avg_score = total_score / total_users if total_users > 0 else 0.0
        
        # Level-Verteilung
        level_distribution = {}
        for reputation in self._reputations.values():
            level = reputation.level
            if level not in level_distribution:
                level_distribution[level] = 0
            level_distribution[level] += 1
        
        return {
            "total_users": total_users,
            "total_score": total_score,
            "average_score": avg_score,
            "level_distribution": level_distribution,
            "top_level": max((r.level for r in self._reputations.values()), default=0),
            "leaderboard": self.get_leaderboard(5),
        }
    
    def get_user_achievements(self, user_id: str) -> list[dict]:
        """Holt die Errungenschaften eines Benutzers"""
        reputation = self.get_reputation(user_id)
        
        achievements = []
        
        # Basis-Achievements
        if reputation.contributions >= 1:
            achievements.append({
                "name": "First Contribution",
                "description": "Erster Beitrag erstellt",
                "unlocked_at": reputation.created_at.isoformat(),
            })
        
        if reputation.contributions >= 10:
            achievements.append({
                "name": "Active Contributor",
                "description": "10 Beiträge erstellt",
                "unlocked_at": reputation.created_at.isoformat(),
            })
        
        if reputation.verified_contributions >= 1:
            achievements.append({
                "name": "Verifier",
                "description": "Erster Beitrag verifiziert",
                "unlocked_at": reputation.created_at.isoformat(),
            })
        
        if reputation.score >= 50:
            achievements.append({
                "name": "Trusted Member",
                "description": "Reputations-Score von 50 erreicht",
                "unlocked_at": reputation.created_at.isoformat(),
            })
        
        if reputation.score >= 100:
            achievements.append({
                "name": "Expert",
                "description": "Reputations-Score von 100 erreicht",
                "unlocked_at": reputation.created_at.isoformat(),
            })
        
        # Level-basierte Achievements
        for level in range(2, 6):
            if reputation.level >= level:
                level_info = self.get_level_info(level)
                achievements.append({
                    "name": f"Level {level} Reached",
                    "description": f"{level_info['name']} Level erreicht",
                    "unlocked_at": reputation.created_at.isoformat(),
                })
        
        # Sortiere nach Erreichungsdatum
        achievements.sort(key=lambda x: x["unlocked_at"])
        
        return achievements
    
    def can_perform_action(self, user_id: str, action: str) -> tuple[bool, str]:
        """
        Prüft, ob ein Benutzer eine Aktion ausführen darf.
        
        Args:
            user_id: ID des Benutzers
            action: Aktionsname
        
        Returns:
            (erlaubt, Grund)
        """
        reputation = self.get_reputation(user_id)
        
        # Definiere Anforderungen für verschiedene Aktionen
        action_requirements = {
            "create_contribution": {"min_level": 1, "min_score": 0},
            "vote": {"min_level": 1, "min_score": 0},
            "verify_contribution": {"min_level": 2, "min_score": 10},
            "delete_contribution": {"min_level": 3, "min_score": 50},
            "edit_any_contribution": {"min_level": 4, "min_score": 100},
            "manage_users": {"min_level": 5, "min_score": 200},
        }
        
        if action not in action_requirements:
            return True, "Aktion hat keine Anforderungen"
        
        requirements = action_requirements[action]
        
        if reputation.level < requirements["min_level"]:
            return False, f"Benötigt Level {requirements['min_level']} (aktuell: {reputation.level})"
        
        if reputation.score < requirements["min_score"]:
            return False, f"Benötigt Score {requirements['min_score']} (aktuell: {reputation.score:.1f})"
        
        return True, "Alle Anforderungen erfüllt"
