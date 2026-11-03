from typing import Dict, Any
from app.graph.client import graph_client, logger

def seed_graph_database():
    engine = graph_client.embedded
    engine.clear()

    engine.add_node("person_sarah", ["Person"], {
        "name": "Sarah Chen",
        "handle": "@sarah_architect",
        "email": "sarah.chen@enterprise.io",
        "role": "Principal Systems Architect (Exited 2022)",
        "is_active": False
    })
    engine.add_node("person_raj", ["Person"], {
        "name": "Raj Patel",
        "handle": "@raj_infra",
        "email": "raj.patel@enterprise.io",
        "role": "Staff Site Reliability Engineer",
        "is_active": True
    })

    engine.add_node("entity_retry_limit", ["CodeEntity"], {
        "name": "RETRY_LIMIT",
        "type": "CONFIG_KEY",
        "path": "core/networking/connection_pool.py",
        "aliases": ["MAX_RETRIES", "connection_retries", "pool_retry_count"]
    })
    engine.add_node("entity_conn_pool", ["CodeEntity"], {
        "name": "connection_pool.py",
        "type": "FILE",
        "path": "core/networking/connection_pool.py",
        "aliases": ["transport/pool.py"]
    })

    engine.add_node("commit_c101", ["Commit"], {
        "sha": "a8f9c1e289",
        "message": "feat(pool): initialize connection pool with aggressive retry limit (10)",
        "timestamp": "2021-04-12T10:30:00Z",
        "author": "Sarah Chen"
    })
    engine.add_node("commit_c302", ["Commit"], {
        "sha": "d4b2e8810c",
        "message": "fix(resilience): clamp retry limit to 3 with full jitter to stop thundering herds",
        "timestamp": "2023-08-14T18:45:00Z",
        "author": "Raj Patel"
    })

    engine.add_node("pr_104", ["PullRequest"], {
        "id": "pr_104",
        "number": 104,
        "title": "RFC-12: High-throughput HTTP/2 connection pooling",
        "body": "Sets RETRY_LIMIT=10. Sarah: 'Network micro-drops between AZs cause 502s unless retries are persistent.'",
        "merged_at": "2021-04-15T14:20:00Z",
        "url": "https://github.com/org/repo/pull/104"
    })
    engine.add_node("pr_318", ["PullRequest"], {
        "id": "pr_318",
        "number": 318,
        "title": "fix(outage): emergency clamp on retries and add backoff jitter",
        "body": "Post-mortem INC-402 resolution: 10 retries with zero jitter caused a self-inflicted DDoS on Redis during network partition. Clamping max retries to 3.",
        "merged_at": "2023-08-15T02:10:00Z",
        "url": "https://github.com/org/repo/pull/318"
    })

    engine.add_node("inc_402", ["Incident"], {
        "id": "INC-402",
        "title": "Sev-1: Cascading DB Outage from Thundering Herd Retries",
        "severity": "CRITICAL",
        "date": "2023-08-14T16:00:00Z",
        "postmortem_summary": "At 15:58 UTC, upstream Redis cluster had a 15-second pause. 120 client worker instances executed 10 retries each simultaneously without jitter, overwhelming the recovery nodes with 1.2M req/sec. Recovery impossible until client traffic was throttled."
    })

    engine.add_node("dec_2021_retries", ["Decision"], {
        "id": "DEC-2021-04",
        "title": "Set connection retry limit to 10 for AZ resilience",
        "summary": "Original 2021 policy: Set RETRY_LIMIT to 10 to mask cross-AZ latency spikes. (SUPERSEDED)",
        "rationale": "High retry tolerance chosen when cross-AZ network blips caused spurious 502s.",
        "timestamp": "2021-04-15T14:20:00Z",
        "status": "SUPERSEDED"
    })
    engine.add_node("dec_2023_retries", ["Decision"], {
        "id": "DEC-2023-08",
        "title": "Hard clamp RETRY_LIMIT to 3 with exponential jitter",
        "summary": "ACTIVE RULING: Maximum 3 retries with full decorrelated jitter. Mandated after INC-402.",
        "rationale": "Prevent cascading retry storms during downstream cold starts.",
        "timestamp": "2023-08-15T02:10:00Z",
        "status": "ACTIVE"
    })

    engine.add_relationship("entity_retry_limit", "entity_conn_pool", "DEFINED_IN")
    engine.add_relationship("commit_c101", "entity_retry_limit", "TOUCHES")
    engine.add_relationship("commit_c302", "entity_retry_limit", "TOUCHES")
    engine.add_relationship("commit_c101", "pr_104", "PART_OF")
    engine.add_relationship("commit_c302", "pr_318", "PART_OF")
    engine.add_relationship("pr_104", "dec_2021_retries", "PRODUCED")
    engine.add_relationship("pr_318", "dec_2023_retries", "PRODUCED")
    engine.add_relationship("pr_318", "inc_402", "MITIGATED")
    engine.add_relationship("person_sarah", "dec_2021_retries", "DECIDED")
    engine.add_relationship("person_raj", "dec_2023_retries", "DECIDED")
    engine.add_relationship("person_raj", "pr_318", "REVIEWED")
    
    engine.add_relationship("dec_2023_retries", "dec_2021_retries", "SUPERSEDES", {
        "date": "2023-08-15T02:10:00Z",
        "reason": "Overridden following INC-402 thundering herd postmortem"
    })

    engine.add_node("entity_old_transport", ["CodeEntity"], {
        "name": "transport/pool.py",
        "type": "FILE",
        "path": "src/transport/pool.py",
        "aliases": ["legacy_pool"]
    })
    engine.add_node("entity_new_conn_mgr", ["CodeEntity"], {
        "name": "connection_manager.py",
        "type": "FILE",
        "path": "core/networking/connection_manager.py",
        "aliases": ["transport/pool.py", "conn_mgr"]
    })
    engine.add_node("dec_keepalive", ["Decision"], {
        "id": "DEC-2022-11",
        "title": "Disable TCP Keep-Alives on connection pool",
        "summary": "Keep-alive packets terminated prematurely by AWS NLB idle timeout (350s).",
        "rationale": "NLB silently drops idle sockets; explicit ping-pong probe preferred.",
        "timestamp": "2022-11-20T09:15:00Z",
        "status": "ACTIVE"
    })
    engine.add_relationship("entity_old_transport", "entity_new_conn_mgr", "RENAMED_TO", {
        "date": "2024-01-10T11:00:00Z",
        "commit": "f9a2b419"
    })
    engine.add_relationship("dec_keepalive", "entity_old_transport", "GOVERNS")
    engine.add_relationship("dec_keepalive", "entity_new_conn_mgr", "GOVERNS")

    engine.add_node("entity_magic_buffer", ["CodeEntity"], {
        "name": "MAGIC_BUFFER_SIZE",
        "type": "CONFIG_KEY",
        "path": "core/io/socket_reader.py",
        "aliases": ["BUFFER_SIZE", "DEFAULT_BUF"]
    })
    engine.add_node("commit_orphan", ["Commit"], {
        "sha": "993a218f0a",
        "message": "quick fix buffer",
        "timestamp": "2020-03-01T22:04:11Z",
        "author": "ex_contractor_dev"
    })
    engine.add_node("person_ex_contractor", ["Person"], {
        "name": "Contractor 2020",
        "handle": "@contractor_temp",
        "email": "contractor.unreachable@external.com",
        "role": "Contract Developer (Left 2020)",
        "is_active": False
    })
    engine.add_relationship("commit_orphan", "entity_magic_buffer", "TOUCHES")
    engine.add_relationship("person_ex_contractor", "commit_orphan", "AUTHORED")

    engine.add_node("entity_legacy_flag", ["CodeEntity"], {
        "name": "ENABLE_LEGACY_GRPC_FALLBACK",
        "type": "CONFIG_KEY",
        "path": "config/features.py",
        "aliases": ["grpc_fallback_flag", "enable_legacy_grpc"]
    })
    engine.add_node("dec_grpc_flag", ["Decision"], {
        "id": "DEC-2023-01",
        "title": "Keep gRPC fallback permanently enabled for EU banking partner",
        "summary": "EU Partner 'Bank-Nordic' runs legacy TLS 1.1 proxies that reject HTTP/2 trailers.",
        "rationale": "Contractual SLA penalty ($50k/mo) if deprecated before their Q4 2026 upgrade.",
        "timestamp": "2023-01-18T16:00:00Z",
        "status": "ACTIVE"
    })
    engine.add_node("pr_209", ["PullRequest"], {
        "id": "pr_209",
        "number": 209,
        "title": "feat(flags): preserve legacy gRPC endpoint for enterprise compliance",
        "body": "Customer Success confirmed Bank-Nordic cannot migrate until their core banking upgrade in late 2026.",
        "merged_at": "2023-01-18T17:30:00Z",
        "url": "https://github.com/org/repo/pull/209"
    })
    engine.add_relationship("dec_grpc_flag", "entity_legacy_flag", "GOVERNS")
    engine.add_relationship("pr_209", "dec_grpc_flag", "PRODUCED")
    engine.add_relationship("person_raj", "pr_209", "REVIEWED")

    if graph_client.is_connected and graph_client.driver:
        try:
            _seed_live_neo4j(graph_client)
            logger.info("Successfully seeded live Neo4j AuraDB instance!")
        except Exception as e:
            logger.warning(f"Could not seed live Neo4j database: {e}")

    logger.info("WhyTrace knowledge graph seeded with 4 historical storylines.")

def _seed_live_neo4j(client):
    full = client.embedded.get_full_graph()
    with client.driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        
        for node in full["nodes"]:
            labels_str = ":".join(node["labels"])
            props = {k: v for k, v in node.items() if k not in ["id", "label", "labels"]}
            cypher = f"CREATE (n:{labels_str} {{id: $id}}) SET n += $props"
            session.run(cypher, id=node["id"], props=props)
            
        for edge in full["edges"]:
            rel_type = edge["type"]
            props = {k: v for k, v in edge.items() if k not in ["source", "target", "type"]}
            cypher = (
                f"MATCH (a {{id: $source}}), (b {{id: $target}}) "
                f"CREATE (a)-[r:{rel_type}]->(b) SET r += $props"
            )
            session.run(cypher, source=edge["source"], target=edge["target"], props=props)
