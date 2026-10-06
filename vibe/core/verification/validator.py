"""
Information Validator - Validierung von Informationen und Quellen
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from vibe.core.knowledge.models import KnowledgeSourceType
from vibe.core.verification.models import (
    Claim,
    Evidence,
    EvidenceType,
    VerificationStatus,
)
from vibe.observability.logging import logger


@dataclass
class ValidationResult:
    """Ergebnis einer Validierung"""
    is_valid: bool
    score: float  # 0.0 bis 1.0
    issues: list[str]
    suggestions: list[str]


class InformationValidator:
    """
    Validator für Informationen und Quellen.
    
    Prüft:
    - Quellen-Glaubwürdigkeit
    - Inhaltliche Qualität
    - Zeitliche Aktualität
    - Formatierung
    """
    
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
        "reddit.com": 0.4,
        "4chan.org": 0.1,
        "8kun.top": 0.1,
    }
    
    # Muster für unseriöse Inhalte
    UNRELIABLE_PATTERNS = [
        r"\bclickbait\b",
        r"\bshocking\b",
        r"\bunbelievable\b",
        r"\byou won't believe\b",
        r"\bsecret they don't want you to know\b",
        r"\bact now\b",
        r"\blimited time\b",
        r"\bexclusive offer\b",
    ]
    
    # Muster für seriöse Quellen
    RELIABLE_PATTERNS = [
        r"\bstudy\b",
        r"\bresearch\b",
        r"\baccording to\b",
        r"\bcites\b",
        r"\breferences\b",
        r"\bsources\b",
    ]
    
    def __init__(self):
        self._domain_cache: dict[str, float] = {}
    
    def validate_source(self, url: str, source_type: KnowledgeSourceType = KnowledgeSourceType.WEB) -> ValidationResult:
        """Validiert eine Quelle"""
        issues = []
        suggestions = []
        score = 0.5  # Standardwert
        
        # Extrahiere Domain
        domain = self._extract_domain(url)
        if not domain:
            issues.append("URL ist ungültig")
            return ValidationResult(is_valid=False, score=0.0, issues=issues, suggestions=suggestions)
        
        # Prüfe Domain-Vertrauenswert
        domain_score = self._get_domain_score(domain)
        if domain_score is not None:
            score = domain_score
        
        # Prüfe Quelle-Typ
        if source_type == KnowledgeSourceType.OFFICIAL:
            score = min(1.0, score * 1.1)  # Bonus für offizielle Quellen
        elif source_type == KnowledgeSourceType.COMMUNITY:
            score = max(0.3, score * 0.9)  # Malus für Community-Quellen
        
        # Prüfe auf HTTPS
        if not url.startswith("https://"):
            issues.append("Quelle verwendet kein HTTPS")
            score = max(0.1, score * 0.5)
            suggestions.append("Verwenden Sie HTTPS-Quellen")
        
        # Prüfe auf bekannte vertrauenswürdige Domains
        for trusted_domain, trusted_score in self.TRUSTED_DOMAINS.items():
            if trusted_domain in domain:
                score = max(score, trusted_score)
                break
        
        # Prüfe auf bekannte unzuverlässige Domains
        for untrusted_domain, untrusted_score in self.UNTRUSTED_DOMAINS.items():
            if untrusted_domain in domain:
                score = min(score, untrusted_score)
                issues.append(f"Domain {domain} gilt als unzuverlässig")
                suggestions.append("Verwenden Sie seriösere Quellen")
                break
        
        # Prüfe auf Social Media
        if any(sm in domain for sm in ["facebook", "twitter", "x.com", "instagram", "tiktok"]):
            issues.append("Social Media Quellen sind oft unzuverlässig")
            score = max(0.2, score * 0.5)
            suggestions.append("Verwenden Sie primäre Quellen statt Social Media")
        
        is_valid = score >= 0.5
        if not is_valid:
            issues.append(f"Quellen-Score zu niedrig: {score:.1%}")
        
        return ValidationResult(
            is_valid=is_valid,
            score=score,
            issues=issues,
            suggestions=suggestions,
        )
    
    def validate_content(self, content: str, context: Optional[str] = None) -> ValidationResult:
        """Validiert den Inhalt einer Information"""
        issues = []
        suggestions = []
        score = 0.5
        
        if not content or len(content.strip()) < 10:
            issues.append("Inhalt ist zu kurz")
            return ValidationResult(is_valid=False, score=0.0, issues=issues, suggestions=suggestions)
        
        # Prüfe auf unseriöse Muster
        for pattern in self.UNRELIABLE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(f"Enthält unseriöses Muster: {pattern}")
                score = max(0.1, score * 0.7)
                suggestions.append("Vermeiden Sie Clickbait-Formulierungen")
        
        # Prüfe auf seriöse Muster
        reliable_count = sum(1 for pattern in self.RELIABLE_PATTERNS if re.search(pattern, content, re.IGNORECASE))
        if reliable_count >= 2:
            score = min(1.0, score * 1.2)
        
        # Prüfe auf Faktenbehauptungen ohne Quellen
        if re.search(r"\bfakt\b|\bnachweislich\b|\bwissenschaftlich bewiesen\b", content, re.IGNORECASE):
            if not re.search(r"\bquelle\b|\bstudie\b|\bforschung\b|\blaut\b", content, re.IGNORECASE):
                issues.append("Faktenbehauptungen ohne Quellenangabe")
                score = max(0.3, score * 0.8)
                suggestions.append("Fügen Sie Quellen für Faktenbehauptungen hinzu")
        
        # Prüfe auf übertriebene Behauptungen
        if re.search(r"\b100%\b|\balles\b|\bjedes\b|\bimmer\b|\bnie\b", content, re.IGNORECASE):
            issues.append("Übertriebene Behauptungen")
            score = max(0.4, score * 0.8)
            suggestions.append("Vermeiden Sie absolute Behauptungen")
        
        # Prüfe auf Ausgewogenheit
        if self._is_unbalanced(content):
            issues.append("Inhalt scheint einseitig")
            score = max(0.4, score * 0.8)
            suggestions.append("Präsentieren Sie verschiedene Perspektiven")
        
        is_valid = score >= 0.6
        return ValidationResult(
            is_valid=is_valid,
            score=score,
            issues=issues,
            suggestions=suggestions,
        )
    
    def validate_claim(self, claim: Claim) -> ValidationResult:
        """Validiert eine Behauptung"""
        # Validieren Sie den Text
        content_result = self.validate_content(claim.text, claim.context)
        
        # Validieren Sie die Quelle, falls vorhanden
        if claim.source:
            source_result = self.validate_source(claim.source)
            combined_score = (content_result.score * 0.6) + (source_result.score * 0.4)
            issues = content_result.issues + source_result.issues
            suggestions = content_result.suggestions + source_result.suggestions
            is_valid = content_result.is_valid and source_result.is_valid
        else:
            combined_score = content_result.score
            issues = content_result.issues
            suggestions = content_result.suggestions
            is_valid = content_result.is_valid
        
        return ValidationResult(
            is_valid=is_valid,
            score=combined_score,
            issues=issues,
            suggestions=suggestions,
        )
    
    def validate_evidence(self, evidence: Evidence) -> ValidationResult:
        """Validiert einen Beweis"""
        # Validieren Sie die Quelle
        source_result = self.validate_source(evidence.source)
        
        # Validieren Sie den Inhalt
        content_result = self.validate_content(evidence.content)
        
        # Kombinieren Sie die Ergebnisse
        combined_score = (source_result.score * 0.7) + (content_result.score * 0.3)
        issues = source_result.issues + content_result.issues
        suggestions = source_result.suggestions + content_result.suggestions
        
        # Prüfe, ob der Beweis die Behauptung unterstützt
        if evidence.supports_claim:
            # Höhere Anforderungen für unterstützende Beweise
            if combined_score < 0.6:
                issues.append("Unterstützender Beweis hat zu niedrigen Score")
        else:
            # Widersprechende Beweise sollten besonders gut begründet sein
            if combined_score < 0.7:
                issues.append("Widersprechender Beweis hat zu niedrigen Score")
        
        is_valid = combined_score >= 0.6
        
        return ValidationResult(
            is_valid=is_valid,
            score=combined_score,
            issues=issues,
            suggestions=suggestions,
        )
    
    def calculate_trust_score(self, url: str, content: str, source_type: KnowledgeSourceType = KnowledgeSourceType.WEB) -> float:
        """Berechnet einen kombinierten Vertrauenswert"""
        source_result = self.validate_source(url, source_type)
        content_result = self.validate_content(content)
        
        # Gewichtet kombinieren
        trust_score = (source_result.score * 0.6) + (content_result.score * 0.4)
        
        # Bonus für offizielle Quellen
        if source_type == KnowledgeSourceType.OFFICIAL:
            trust_score = min(1.0, trust_score * 1.1)
        
        return trust_score
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extrahiert die Domain aus einer URL"""
        # Entferne Protokoll
        url = url.replace("https://", "").replace("http://", "").replace("www.", "")
        
        # Extrahiere Domain
        domain = url.split("/")[0].split("?")[0].split("#")[0]
        
        # Entferne Port
        domain = domain.split(":")[0]
        
        return domain.lower() if domain else None
    
    def _get_domain_score(self, domain: str) -> Optional[float]:
        """Holt den Vertrauenswert einer Domain (mit Cache)"""
        if domain in self._domain_cache:
            return self._domain_cache[domain]
        
        # Prüfe vertrauenswürdige Domains
        for trusted_domain, score in self.TRUSTED_DOMAINS.items():
            if trusted_domain in domain:
                self._domain_cache[domain] = score
                return score
        
        # Prüfe unzuverlässige Domains
        for untrusted_domain, score in self.UNTRUSTED_DOMAINS.items():
            if untrusted_domain in domain:
                self._domain_cache[domain] = score
                return score
        
        # Standardwert
        return 0.5
    
    def _is_unbalanced(self, content: str) -> bool:
        """Prüft, ob ein Inhalt einseitig ist"""
        # Einfache Heuristik: Prüfe auf übermäßige Nutzung von Superlativen
        superlatives = [
            r"\bbester\b", r"\bschlechtester\b", r"\bperfekt\b",
            r"\btotal\b", r"\bkomplett\b", r"\babsolut\b",
        ]
        
        superlative_count = sum(
            1 for pattern in superlatives 
            if re.search(pattern, content, re.IGNORECASE)
        )
        
        # Prüfe auf fehlende Alternativen
        alternative_terms = [
            r"\babere\b", r"\bandererseits\b", r"\bjedoch\b",
            r"\baber\b", r"\bhingegen\b", r"\ballerdings\b",
        ]
        
        alternative_count = sum(
            1 for pattern in alternative_terms 
            if re.search(pattern, content, re.IGNORECASE)
        )
        
        # Wenn viele Superlative und wenige Alternativen
        return superlative_count >= 3 and alternative_count < 2
    
    def get_source_trust_level(self, url: str) -> str:
        """Gibt den Vertrauenslevel einer Quelle zurück"""
        score = self.validate_source(url).score
        
        if score >= 0.8:
            return "very_high"
        elif score >= 0.6:
            return "high"
        elif score >= 0.4:
            return "medium"
        elif score >= 0.2:
            return "low"
        else:
            return "very_low"
    
    def get_content_quality_level(self, content: str) -> str:
        """Gibt den Qualitätslevel eines Inhalts zurück"""
        score = self.validate_content(content).score
        
        if score >= 0.8:
            return "excellent"
        elif score >= 0.6:
            return "good"
        elif score >= 0.4:
            return "fair"
        elif score >= 0.2:
            return "poor"
        else:
            return "very_poor"
