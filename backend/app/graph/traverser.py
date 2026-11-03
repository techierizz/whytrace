from typing import Dict, Any, List, Optional
from app.graph.client import graph_client
from app.graph.confidence import ConfidenceEngine
from app.graph.schema import CYPHER_GET_PROVENANCE

class GraphTraverser:
    @staticmethod
    def answer_why_query(entity_query: str) -> Dict[str, Any]:
        engine = graph_client.embedded
        if not engine.nodes:
            from app.ingest.seed_data import seed_graph_database
            seed_graph_database()
        
        entity_node = engine.resolve_entity(entity_query)
        if not entity_node:
            return {
                "entity_name": entity_query,
                "found": False,
                "confidence": {
                    "score": 0.0,
                    "percentage": 0,
                    "is_refusal": True,
                    "refusal_reason": f"Code entity '{entity_query}' was not found in the repository graph. Refusing to invent hallucinated answers.",
                    "signals": [],
                    "status_label": "NOT FOUND"
                },
                "active_decision": None,
                "superseded_decisions": [],
                "evidence_chain": [],
                "person_to_ask": None,
                "subgraph": {"nodes": [], "edges": []}
            }

        entity_id = entity_node["id"]
        entity_props = entity_node["properties"]
        entity_name = entity_props.get("name", entity_id)

        subgraph = engine.get_provenance_subgraph(entity_id)

        decisions = [n for n in subgraph["nodes"] if "Decision" in n["labels"]]
        prs = [n for n in subgraph["nodes"] if "PullRequest" in n["labels"]]
        incidents = [n for n in subgraph["nodes"] if "Incident" in n["labels"]]
        issues = [n for n in subgraph["nodes"] if "Issue" in n["labels"]]
        persons = [n for n in subgraph["nodes"] if "Person" in n["labels"]]
        commits = [n for n in subgraph["nodes"] if "Commit" in n["labels"]]

        active_decision = None
        superseded_decisions = []

        if decisions:
            sorted_decisions = sorted(
                decisions,
                key=lambda x: str(x.get("timestamp", "")),
                reverse=True
            )

            for d in sorted_decisions:
                d_id = d["id"]
                superseding_lineage = engine.trace_supersessions(d_id)
                if superseding_lineage:
                    superseded_decisions.append({
                        "id": d_id,
                        "summary": d.get("summary"),
                        "rationale": d.get("rationale"),
                        "date": d.get("timestamp"),
                        "overridden_by": superseding_lineage
                    })
                elif active_decision is None:
                    active_decision = d

            if active_decision is None and sorted_decisions:
                active_decision = sorted_decisions[0]

        person_to_ask = None
        if persons:
            active_persons = [p for p in persons if p.get("is_active", True)]
            target_p = active_persons[0] if active_persons else persons[0]
            person_to_ask = {
                "name": target_p.get("name"),
                "handle": target_p.get("handle"),
                "role": target_p.get("role"),
                "email": target_p.get("email"),
                "is_active": target_p.get("is_active", True)
            }

        confidence = ConfidenceEngine.calculate_confidence(
            decisions=decisions,
            pull_requests=prs,
            incidents=incidents,
            issues=issues,
            persons=persons,
            is_superseded=len(superseded_decisions) > 0 and active_decision is None
        )

        evidence_chain = []
        
        for inc in incidents:
            evidence_chain.append({
                "type": "INCIDENT",
                "badge": f"Production Incident ({inc.get('id')})",
                "title": inc.get("title"),
                "detail": inc.get("postmortem_summary"),
                "date": inc.get("date"),
                "severity": inc.get("severity", "CRITICAL")
            })

        for pr in prs:
            evidence_chain.append({
                "type": "PULL_REQUEST",
                "badge": f"Pull Request #{pr.get('number', pr.get('id'))}",
                "title": pr.get("title"),
                "detail": pr.get("body"),
                "date": pr.get("merged_at"),
                "url": pr.get("url", "#")
            })

        for c in commits:
            evidence_chain.append({
                "type": "COMMIT",
                "badge": f"Commit {c.get('sha', '')[:7]}",
                "title": c.get("message"),
                "detail": f"Authored by {c.get('author')}",
                "date": c.get("timestamp")
            })

        return {
            "entity_name": entity_name,
            "entity_path": entity_props.get("path"),
            "aliases": entity_props.get("aliases", []),
            "found": True,
            "confidence": confidence,
            "active_decision": active_decision,
            "superseded_decisions": superseded_decisions,
            "evidence_chain": evidence_chain,
            "person_to_ask": person_to_ask,
            "subgraph": subgraph
        }
