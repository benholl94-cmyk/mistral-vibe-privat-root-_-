"""
Faktencheck-Pipeline - Automatische Validierung von Informationen
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from datetime import datetime
from typing import Any, Optional

from vibe.core.knowledge.database import KnowledgeDatabase
from vibe.core.realtime.search import RealTimeSearch
from vibe.core.realtime.fetcher import DataFetcher
from vibe.core.verification.models import (
    Claim,
    Evidence,
    EvidenceType,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
)
from vibe.observability.logging import logger


class FactCheckStep:
    """Ein einzelner Schritt in der Faktencheck-Pipeline"""
    
    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight  # Gewicht für die Gesamtbewertung
    
    async def execute(self, claim: Claim, context: dict[str, Any] | None = None) -> tuple[VerificationStatus, float, list[Evidence]]:
        """
        Führt den Schritt aus.
        
        Returns:
            (status, confidence, evidence)
        """
        raise NotImplementedError(f"Step {self.name} not implemented")


class KnowledgeBaseCheckStep(FactCheckStep):
    """Prüft gegen die lokale Wissensdatenbank"""
    
    def __init__(self, db: KnowledgeDatabase | None = None):
        super().__init__("knowledge_base", weight=0.8)
        self.db = db or KnowledgeDatabase()
    
    async def execute(self, claim: Claim, context: dict[str, Any] | None = None) -> tuple[VerificationStatus, float, list[Evidence]]:
        evidence_list = []
        
        # Suche in der Wissensdatenbank
        from vibe.core.knowledge.models import KnowledgeQuery
        query = KnowledgeQuery(
            query=claim.text,
            min_confidence=0.5,
            max_results=5,
        )
        
        result = self.db.query_entries(query)
        
        if result.results:
            # Beweise aus den Ergebnissen erstellen
            for entry in result.results:
                evidence = Evidence(
                    id=f"kb_{entry.id}",
                    claim_id=claim.text[:50],  # Kurzform als ID
                    evidence_type=EvidenceType.SOURCE,
                    source=entry.source.name,
                    content=entry.content[:500],  # Max. 500 Zeichen
                    url=entry.source.url,
                    confidence=entry.confidence,
                    supports_claim=True,  # Annahme: Übereinstimmung
                )
                evidence_list.append(evidence)
            
            # Status basierend auf den Ergebnissen
            avg_confidence = sum(e.confidence for e in evidence_list) / len(evidence_list)
            if avg_confidence >= 0.7:
                return VerificationStatus.VERIFIED, avg_confidence, evidence_list
            elif avg_confidence >= 0.4:
                return VerificationStatus.PARTIALLY_TRUE, avg_confidence, evidence_list
            else:
                return VerificationStatus.DISPUTED, avg_confidence, evidence_list
        
        return VerificationStatus.UNVERIFIED, 0.0, evidence_list


class WebSearchCheckStep(FactCheckStep):
    """Prüft gegen Live-Websuchen"""
    
    def __init__(self, search: RealTimeSearch | None = None):
        super().__init__("web_search", weight=1.0)
        self.search = search or RealTimeSearch()
    
    async def execute(self, claim: Claim, context: dict[str, Any] | None = None) -> tuple[VerificationStatus, float, list[Evidence]]:
        evidence_list = []
        
        try:
            # Suche ausführen
            query = f"{claim.text} fact check" if not context else f"{claim.text} {context} fact check"
            result = await self.search.search(query)
            
            if result.results:
                # Beweise aus den Suchergebnissen erstellen
                for item in result.results[:5]:  # Max. 5 Ergebnisse
                    evidence = Evidence(
                        id=f"ws_{item.url}",
                        claim_id=claim.text[:50],
                        evidence_type=EvidenceType.CROSS_CHECK,
                        source=item.title,
                        content=item.snippet[:500],
                        url=item.url,
                        confidence=item.trust_score,
                        supports_claim=True,
                    )
                    evidence_list.append(evidence)
                
                # Status basierend auf den Ergebnissen
                avg_confidence = sum(e.confidence for e in evidence_list) / len(evidence_list) if evidence_list else 0.0
                if avg_confidence >= result.avg_trust_score:
                    return VerificationStatus.VERIFIED, avg_confidence, evidence_list
                elif avg_confidence >= 0.5:
                    return VerificationStatus.PARTIALLY_TRUE, avg_confidence, evidence_list
                else:
                    return VerificationStatus.DISPUTED, avg_confidence, evidence_list
        
        except Exception as e:
            logger.error("Web search check failed: %s", e)
        
        return VerificationStatus.UNVERIFIED, 0.0, evidence_list


class ConsensusCheckStep(FactCheckStep):
    """Prüft auf Konsens zwischen mehreren Quellen"""
    
    def __init__(self, min_sources: int = 2):
        super().__init__("consensus", weight=0.9)
        self.min_sources = min_sources
    
    async def execute(self, claim: Claim, context: dict[str, Any] | None = None) -> tuple[VerificationStatus, float, list[Evidence]]:
        # Dieser Schritt benötigt Vorherige Ergebnisse
        previous_evidence = context.get("evidence", []) if context else []
        
        if not previous_evidence:
            return VerificationStatus.UNVERIFIED, 0.0, []
        
        # Gruppe Beweise nach Quelle
        source_groups = {}
        for evidence in previous_evidence:
            source = evidence.source
            if source not in source_groups:
                source_groups[source] = []
            source_groups[source].append(evidence)
        
        # Prüfe Konsens
        consensus_count = 0
        total_sources = len(source_groups)
        
        for source, evidences in source_groups.items():
            # Wenn die Mehrheit der Beweise einer Quelle die Behauptung unterstützt
            supporting = sum(1 for e in evidences if e.supports_claim)
            if supporting >= len(evidences) * 0.7:  # 70% Unterstützung
                consensus_count += 1
        
        # Berechne Konsens-Score
        consensus_score = consensus_count / total_sources if total_sources > 0 else 0.0
        
        if consensus_count >= self.min_sources and consensus_score >= 0.8:
            return VerificationStatus.VERIFIED, consensus_score, previous_evidence
        elif consensus_count >= self.min_sources and consensus_score >= 0.5:
            return VerificationStatus.PARTIALLY_TRUE, consensus_score, previous_evidence
        else:
            return VerificationStatus.DISPUTED, consensus_score, previous_evidence


class FactCheckPipeline:
    """
    Pipeline für automatische Faktenchecks.
    
    Die Pipeline führt mehrere Prüfs-Schritte aus und kombiniert die Ergebnisse
    zu einem Gesamturteil.
    """
    
    def __init__(
        self,
        db: KnowledgeDatabase | None = None,
        search: RealTimeSearch | None = None,
    ):
        self.db = db
        self.search = search
        self.steps: list[FactCheckStep] = [
            KnowledgeBaseCheckStep(db),
            WebSearchCheckStep(search),
            ConsensusCheckStep(),
        ]
    
    async def verify(self, request: VerificationRequest) -> VerificationResult:
        """
        Führt einen vollständigen Faktencheck durch.
        
        Args:
            request: Verifizierungsanfrage
        
        Returns:
            Verifizierungsergebnis
        """
        start_time = time.time()
        
        # Kontext für die Schritte
        context: dict[str, Any] = {
            "claim": request.claim,
            "evidence": [],
        }
        
        # Führe alle Schritte aus
        step_results = []
        for step in self.steps:
            try:
                status, confidence, evidence = await step.execute(request.claim, context)
                step_results.append((step, status, confidence, evidence))
                context["evidence"].extend(evidence)
            except Exception as e:
                logger.error("Step %s failed: %s", step.name, e, exc_info=True)
                step_results.append((step, VerificationStatus.UNVERIFIED, 0.0, []))
        
        # Kombiniere Ergebnisse
        final_status, final_confidence = self._combine_results(step_results, request)
        
        # Filtere und begrenze Beweise
        all_evidence = context.get("evidence", [])
        supporting = [e for e in all_evidence if e.supports_claim]
        contradicting = [e for e in all_evidence if not e.supports_claim]
        
        # Sortiere nach Vertrauenswert
        all_evidence.sort(key=lambda x: x.confidence, reverse=True)
        
        # Begrenze auf max_evidence
        evidence = all_evidence[:request.max_evidence]
        
        # Quellen sammeln
        sources_used = list(set(e.source for e in evidence))
        
        execution_time = time.time() - start_time
        
        return VerificationResult(
            claim=request.claim,
            status=final_status,
            confidence=final_confidence,
            evidence=evidence,
            supporting_evidence=len(supporting),
            contradicting_evidence=len(contradicting),
            consensus_score=self._calculate_consensus_score(step_results),
            sources_used=sources_used,
            execution_time=execution_time,
            verified_at=datetime.now(),
            notes=self._generate_notes(step_results, final_status),
        )
    
    async def verify_simple(self, text: str, category: Optional[str] = None) -> VerificationResult:
        """
        Einfache Verifizierung eines Textes.
        
        Args:
            text: Zu überprüfender Text
            category: Optionale Kategorie
        
        Returns:
            Verifizierungsergebnis
        """
        claim = Claim(text=text, category=category)
        request = VerificationRequest(claim=claim)
        return await self.verify(request)
    
    def _combine_results(
        self,
        step_results: list[tuple[FactCheckStep, VerificationStatus, float, list[Evidence]]],
        request: VerificationRequest,
    ) -> tuple[VerificationStatus, float]:
        """Kombiniert die Ergebnisse der einzelnen Schritte"""
        # Gewichtete Durchschnittsberechnung
        total_weight = 0.0
        weighted_confidence = 0.0
        status_votes: dict[VerificationStatus, float] = {}
        
        for step, status, confidence, _ in step_results:
            weight = step.weight
            total_weight += weight
            weighted_confidence += confidence * weight
            
            if status not in status_votes:
                status_votes[status] = 0.0
            status_votes[status] += weight
        
        # Durchschnittliche Confidence
        avg_confidence = weighted_confidence / total_weight if total_weight > 0 else 0.0
        
        # Status basierend auf den meisten Stimmen
        if not status_votes:
            return VerificationStatus.UNVERIFIED, 0.0
        
        winning_status = max(status_votes.items(), key=lambda x: x[1])[0]
        
        # Anpassen basierend auf Konsens-Anforderung
        if request.require_consensus:
            # Prüfe, ob genug Quellen übereinstimmen
            verified_weight = status_votes.get(VerificationStatus.VERIFIED, 0.0)
            if verified_weight >= request.min_consensus_sources * 0.5:
                return VerificationStatus.VERIFIED, avg_confidence
            elif verified_weight + status_votes.get(VerificationStatus.PARTIALLY_TRUE, 0.0) >= request.min_consensus_sources * 0.5:
                return VerificationStatus.PARTIALLY_TRUE, avg_confidence
        
        return winning_status, avg_confidence
    
    def _calculate_consensus_score(
        self,
        step_results: list[tuple[FactCheckStep, VerificationStatus, float, list[Evidence]]],
    ) -> float:
        """Berechnet den Konsens-Score"""
        if not step_results:
            return 0.0
        
        # Zähle unterstützende und widersprechende Ergebnisse
        supporting = 0
        contradicting = 0
        
        for _, status, confidence, _ in step_results:
            if status in [VerificationStatus.VERIFIED, VerificationStatus.PARTIALLY_TRUE]:
                supporting += confidence
            else:
                contradicting += (1.0 - confidence)
        
        total = supporting + contradicting
        if total == 0:
            return 0.5  # Neutral
        
        return supporting / total
    
    def _generate_notes(
        self,
        step_results: list[tuple[FactCheckStep, VerificationStatus, float, list[Evidence]]],
        final_status: VerificationStatus,
    ) -> str:
        """Generiert Hinweise basierend auf den Schritten"""
        notes = []
        
        # Schritt-Ergebnisse
        for step, status, confidence, evidence in step_results:
            if status != VerificationStatus.UNVERIFIED:
                notes.append(f"{step.name}: {status.value} ({confidence:.1%})")
        
        # Konsens-Information
        consensus_score = self._calculate_consensus_score(step_results)
        if consensus_score >= 0.8:
            notes.append(f"Hoher Konsens zwischen Quellen ({consensus_score:.1%})")
        elif consensus_score < 0.5:
            notes.append(f"Geringer Konsens zwischen Quellen ({consensus_score:.1%})")
        
        # Endgültiger Status
        if final_status == VerificationStatus.VERIFIED:
            notes.append("✅ Behauptung wurde verifiziert")
        elif final_status == VerificationStatus.FALSE:
            notes.append("❌ Behauptung ist falsch")
        elif final_status == VerificationStatus.DISPUTED:
            notes.append("⚠️ Behauptung ist umstritten")
        else:
            notes.append("ℹ️ Behauptung konnte nicht vollständig verifiziert werden")
        
        return " | ".join(notes)
    
    def add_custom_step(self, step: FactCheckStep) -> None:
        """Fügt einen benutzerdefinierten Schritt hinzu"""
        self.steps.append(step)
    
    def remove_step(self, name: str) -> bool:
        """Entfernt einen Schritt aus der Pipeline"""
        for i, step in enumerate(self.steps):
            if step.name == name:
                del self.steps[i]
                return True
        return False
