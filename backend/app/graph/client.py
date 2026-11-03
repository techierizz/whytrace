import os
import logging
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase, Driver
from app.config import settings

logger = logging.getLogger("whytrace.graph")

class InMemoryGraphEngine:
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.relationships: List[Dict[str, Any]] = []

    def clear(self):
        self.nodes.clear()
        self.relationships.clear()

    def add_node(self, node_id: str, labels: List[str], properties: Dict[str, Any]):
        props = dict(properties)
        props["id"] = node_id
        self.nodes[node_id] = {
            "id": node_id,
            "labels": labels,
            "properties": props
        }

    def add_relationship(self, from_id: str, to_id: str, rel_type: str, properties: Optional[Dict[str, Any]] = None):
        self.relationships.append({
            "from": from_id,
            "to": to_id,
            "type": rel_type,
            "properties": properties or {}
        })

    def get_full_graph(self) -> Dict[str, Any]:
        nodes_list = []
        for nid, data in self.nodes.items():
            nodes_list.append({
                "id": nid,
                "label": data["labels"][0] if data["labels"] else "Node",
                "labels": data["labels"],
                **data["properties"]
            })
        
        edges_list = []
        for rel in self.relationships:
            edges_list.append({
                "source": rel["from"],
                "target": rel["to"],
                "type": rel["type"],
                **rel["properties"]
            })
            
        return {"nodes": nodes_list, "edges": edges_list}

    def resolve_entity(self, entity_query: str) -> Optional[Dict[str, Any]]:
        query_norm = entity_query.strip().lower()
        
        for nid, data in self.nodes.items():
            if "CodeEntity" in data["labels"]:
                name = str(data["properties"].get("name", "")).lower()
                if name == query_norm or nid.lower() == query_norm:
                    return data
                    
        for nid, data in self.nodes.items():
            if "CodeEntity" in data["labels"]:
                aliases = [str(a).lower() for a in data["properties"].get("aliases", [])]
                if query_norm in aliases:
                    return data
                    
        for nid, data in self.nodes.items():
            if "CodeEntity" in data["labels"]:
                name = str(data["properties"].get("name", "")).lower()
                path = str(data["properties"].get("path", "")).lower()
                if query_norm in name or query_norm in path:
                    return data

        return None

    def trace_supersessions(self, decision_id: str) -> List[Dict[str, Any]]:
        superseding = []
        queue = [decision_id]
        visited = set()

        while queue:
            curr_id = queue.pop(0)
            if curr_id in visited:
                continue
            visited.add(curr_id)

            for rel in self.relationships:
                if rel["type"] == "SUPERSEDES" and rel["to"] == curr_id:
                    newer_id = rel["from"]
                    newer_node = self.nodes.get(newer_id)
                    if newer_node:
                        superseding.append({
                            "id": newer_id,
                            "summary": newer_node["properties"].get("summary"),
                            "date": newer_node["properties"].get("timestamp"),
                            "reason": rel["properties"].get("reason", "Overridden in subsequent pull request")
                        })
                        queue.append(newer_id)
        return superseding

    def get_provenance_subgraph(self, entity_id: str) -> Dict[str, Any]:
        subgraph_node_ids = {entity_id}
        subgraph_edges = []
        
        frontier = {entity_id}
        for _ in range(5):
            next_frontier = set()
            for rel in self.relationships:
                if rel["from"] in frontier or rel["to"] in frontier:
                    other = rel["to"] if rel["from"] in frontier else rel["from"]
                    other_node = self.nodes.get(other)
                    
                    if rel not in subgraph_edges:
                        subgraph_edges.append(rel)
                    
                    if other not in subgraph_node_ids:
                        subgraph_node_ids.add(other)
                        if other_node and "Person" not in other_node["labels"]:
                            next_frontier.add(other)
            frontier = next_frontier
            if not frontier:
                break

        nodes_list = []
        for nid in subgraph_node_ids:
            if nid in self.nodes:
                nd = self.nodes[nid]
                nodes_list.append({
                    "id": nid,
                    "label": nd["labels"][0] if nd["labels"] else "Node",
                    "labels": nd["labels"],
                    **nd["properties"]
                })

        return {
            "nodes": nodes_list,
            "edges": [{
                "source": r["from"],
                "target": r["to"],
                "type": r["type"],
                **r["properties"]
            } for r in subgraph_edges]
        }

class Neo4jClient:
    def __init__(self):
        self.driver: Optional[Driver] = None
        self.is_connected: bool = False
        self.embedded: InMemoryGraphEngine = InMemoryGraphEngine()
        self.connection_error: Optional[str] = None
        self.init_driver()

    def init_driver(self):
        if settings.NEO4J_URI and settings.NEO4J_PASSWORD:
            usernames = [settings.NEO4J_USER, "neo4j", os.getenv("NEO4J_USERNAME", "neo4j")]
            seen = set()
            candidates = [u for u in usernames if u and not (u in seen or seen.add(u))]

            for user_candidate in candidates:
                try:
                    drv = GraphDatabase.driver(
                        settings.NEO4J_URI,
                        auth=(user_candidate, settings.NEO4J_PASSWORD)
                    )
                    drv.verify_connectivity()
                    self.driver = drv
                    self.is_connected = True
                    self.connection_error = None
                    logger.info(f"Connected to Neo4j AuraDB at {settings.NEO4J_URI} as {user_candidate}")
                    return
                except Exception as e:
                    self.connection_error = str(e)

            self.is_connected = False
            logger.warning(f"Could not connect to Neo4j AuraDB ({self.connection_error}). Operating in High-Fidelity Embedded Mode.")
        else:
            self.is_connected = False
            self.connection_error = "Neo4j AuraDB credentials not configured. Using High-Fidelity Graph Engine."

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None):
        if self.is_connected and self.driver:
            with self.driver.session() as session:
                return session.run(query, parameters or {}).data()
        return None

    def close(self):
        if self.driver:
            self.driver.close()

graph_client = Neo4jClient()
