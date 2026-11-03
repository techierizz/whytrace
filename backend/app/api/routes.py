from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from app.graph.client import graph_client
from app.graph.traverser import GraphTraverser
from app.rag.baseline_vector_rag import BaselineVectorRAG
from app.ingest.seed_data import seed_graph_database
from app.ingest.github_pipeline import GitHubPipeline
from app.analytics.attrition import AttritionAnalytics
from app.config import settings

router = APIRouter(prefix="/api")

class QueryRequest(BaseModel):
    query: str
    entity_name: Optional[str] = None

class GitHubIngestRequest(BaseModel):
    repo: str
    max_items: Optional[int] = 12
    token: Optional[str] = None

class ConnectRequest(BaseModel):
    uri: str
    user: str
    password: str
    database: Optional[str] = "neo4j"

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "neo4j_connected": graph_client.is_connected,
        "neo4j_uri": settings.NEO4J_URI if graph_client.is_connected else "Embedded High-Fidelity Graph Engine",
        "connection_error": graph_client.connection_error
    }

@router.post("/query")
def execute_why_query(req: QueryRequest):
    query_text = req.query.strip()
    entity_target = req.entity_name or query_text
    
    q_lower = query_text.lower()
    if "retry" in q_lower or "retries" in q_lower:
        entity_target = "RETRY_LIMIT"
    elif "pool" in q_lower or "transport" in q_lower or "connection_manager" in q_lower:
        entity_target = "connection_manager.py"
    elif "magic" in q_lower or "buffer" in q_lower:
        entity_target = "MAGIC_BUFFER_SIZE"
    elif "grpc" in q_lower or "legacy" in q_lower or "flag" in q_lower:
        entity_target = "ENABLE_LEGACY_GRPC_FALLBACK"

    result = GraphTraverser.answer_why_query(entity_target)
    return {
        "user_query": query_text,
        "resolved_entity": entity_target,
        **result
    }

@router.post("/compare")
def compare_vector_vs_graph(req: QueryRequest):
    query_text = req.query.strip()
    
    q_lower = query_text.lower()
    entity_target = req.entity_name or query_text
    if "retry" in q_lower or "retries" in q_lower:
        entity_target = "RETRY_LIMIT"
    elif "magic" in q_lower or "buffer" in q_lower:
        entity_target = "MAGIC_BUFFER_SIZE"
    elif "pool" in q_lower or "transport" in q_lower:
        entity_target = "connection_manager.py"
    elif "grpc" in q_lower or "legacy" in q_lower:
        entity_target = "ENABLE_LEGACY_GRPC_FALLBACK"

    graph_result = GraphTraverser.answer_why_query(entity_target)
    vector_result = BaselineVectorRAG.simulate_vector_search(query_text)

    return {
        "query": query_text,
        "vector_search_result": vector_result,
        "whytrace_graph_result": graph_result
    }

@router.get("/graph/full")
def get_full_graph():
    if not graph_client.embedded.nodes:
        seed_graph_database()
    return graph_client.embedded.get_full_graph()

@router.get("/graph/temporal")
def get_temporal_graph(year: int = 2024):
    if not graph_client.embedded.nodes:
        seed_graph_database()
    full = graph_client.embedded.get_full_graph()
    target_cutoff = f"{year}-12-31T23:59:59Z"

    valid_node_ids = set()
    filtered_nodes = []

    for n in full["nodes"]:
        ts = n.get("timestamp") or n.get("date") or n.get("merged_at") or "2020-01-01"
        if str(ts) <= target_cutoff:
            node_copy = dict(n)
            if year < 2023 and n["id"] == "dec_2021_retries":
                node_copy["status"] = "ACTIVE"
            filtered_nodes.append(node_copy)
            valid_node_ids.add(n["id"])

    filtered_edges = []
    for e in full["edges"]:
        if e["source"] in valid_node_ids and e["target"] in valid_node_ids:
            e_date = e.get("date") or "2020-01-01"
            if str(e_date) <= target_cutoff:
                filtered_edges.append(e)

    return {
        "year": year,
        "nodes": filtered_nodes,
        "edges": filtered_edges,
        "active_decisions_at_time": len([n for n in filtered_nodes if n.get("status") == "ACTIVE"])
    }

@router.post("/ingest/github")
def ingest_github_repository(req: GitHubIngestRequest):
    try:
        res = GitHubPipeline.ingest_public_repo(
            repo_full_name=req.repo,
            max_items=req.max_items or 12,
            github_token=req.token
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/analytics/attrition")
def get_attrition_analytics():
    if not graph_client.embedded.nodes:
        seed_graph_database()
    return AttritionAnalytics.compute_attrition_report()

@router.post("/seed")
def reseed_database():
    seed_graph_database()
    return {"status": "success", "message": "WhyTrace Knowledge Graph reseeded successfully."}

@router.post("/connect")
def update_neo4j_credentials(req: ConnectRequest):
    from neo4j import GraphDatabase
    try:
        driver = GraphDatabase.driver(req.uri, auth=(req.user, req.password))
        driver.verify_connectivity()
        
        settings.NEO4J_URI = req.uri
        settings.NEO4J_USER = req.user
        settings.NEO4J_PASSWORD = req.password
        settings.NEO4J_DATABASE = req.database or "neo4j"
        
        graph_client.driver = driver
        graph_client.is_connected = True
        graph_client.connection_error = None
        
        seed_graph_database()
        
        return {
            "status": "success",
            "message": f"Successfully connected to Neo4j AuraDB at {req.uri} and synchronized graph data!"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to connect to Neo4j AuraDB: {str(e)}"
        }
