from typing import Dict, Any, List
from app.config import settings

class ConfidenceEngine:
    @staticmethod
    def calculate_confidence(
        decisions: List[Dict[str, Any]],
        pull_requests: List[Dict[str, Any]],
        incidents: List[Dict[str, Any]],
        issues: List[Dict[str, Any]],
        persons: List[Dict[str, Any]],
        is_superseded: bool = False
    ) -> Dict[str, Any]:
        has_decision = len(decisions) > 0
        has_pr = len(pull_requests) > 0
        has_incident_or_issue = (len(incidents) > 0 or len(issues) > 0)
        has_person = len(persons) > 0
        is_active = (not is_superseded) if has_decision else False

        score = 0.0
        signals = []

        if has_decision:
            score += 0.35
            signals.append({"name": "Deliberate Decision Node", "weight": "+35%", "status": "VERIFIED"})
        else:
            signals.append({"name": "Deliberate Decision Node", "weight": "0%", "status": "MISSING"})

        if has_pr:
            score += 0.25
            signals.append({"name": "Pull Request Consensus Trail", "weight": "+25%", "status": "VERIFIED"})
        else:
            signals.append({"name": "Pull Request Consensus Trail", "weight": "0%", "status": "MISSING"})

        if has_incident_or_issue:
            score += 0.20
            signals.append({"name": "Causal Incident/Issue Link", "weight": "+20%", "status": "VERIFIED"})
        else:
            signals.append({"name": "Causal Incident/Issue Link", "weight": "0%", "status": "MISSING"})

        if is_active:
            score += 0.10
            signals.append({"name": "Temporal Validity (Unsuperseded)", "weight": "+10%", "status": "ACTIVE"})
        else:
            signals.append({"name": "Temporal Validity (Unsuperseded)", "weight": "0%", "status": "SUPERSEDED/UNVERIFIED"})

        if has_person:
            score += 0.10
            signals.append({"name": "Contactable Author/Reviewer", "weight": "+10%", "status": "FOUND"})
        else:
            signals.append({"name": "Contactable Author/Reviewer", "weight": "0%", "status": "MISSING"})

        score = round(min(1.0, score), 2)
        is_refusal = (score < settings.CONFIDENCE_REFUSAL_THRESHOLD) or (not has_decision and not has_pr)

        if is_refusal:
            refusal_reason = (
                "HONEST REFUSAL: The graph contains no recorded design consensus, PR debate, or incident record "
                "for this code entity. Only raw commit history was found without rationale. "
                "In accordance with strict provenance rules, WhyTrace refuses to hallucinate intent."
            )
        else:
            refusal_reason = None

        return {
            "score": score,
            "percentage": int(score * 100),
            "is_refusal": is_refusal,
            "refusal_reason": refusal_reason,
            "signals": signals,
            "status_label": "HIGH CONFIDENCE" if score >= 0.70 else ("MODERATE CONFIDENCE" if score >= 0.35 else "REFUSAL: INSUFFICIENT GRAPH DATA")
        }
