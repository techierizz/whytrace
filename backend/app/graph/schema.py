CONSTRAINTS = [
    "CREATE CONSTRAINT code_entity_id IF NOT EXISTS FOR (c:CodeEntity) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT decision_id IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT pull_request_id IF NOT EXISTS FOR (pr:PullRequest) REQUIRE pr.id IS UNIQUE",
    "CREATE CONSTRAINT commit_sha IF NOT EXISTS FOR (c:Commit) REQUIRE c.sha IS UNIQUE",
    "CREATE CONSTRAINT incident_id IF NOT EXISTS FOR (i:Incident) REQUIRE i.id IS UNIQUE",
    "CREATE CONSTRAINT issue_id IF NOT EXISTS FOR (iss:Issue) REQUIRE iss.id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX code_entity_name IF NOT EXISTS FOR (c:CodeEntity) ON (c.name)",
    "CREATE INDEX decision_timestamp IF NOT EXISTS FOR (d:Decision) ON (d.timestamp)",
    "CREATE INDEX decision_status IF NOT EXISTS FOR (d:Decision) ON (d.status)",
]

CYPHER_GET_PROVENANCE = (
    "MATCH (target:CodeEntity) "
    "WHERE toLower(target.name) = toLower($entity_name) "
    "OR toLower($entity_name) IN [alias IN target.aliases | toLower(alias)] "
    "OPTIONAL MATCH (target)<-[:TOUCHES]-(c:Commit)-[:PART_OF]->(pr:PullRequest)-[:PRODUCED]->(d:Decision) "
    "OPTIONAL MATCH (pr)-[:MITIGATED|RESOLVES]->(inc:Incident) "
    "OPTIONAL MATCH (pr)-[:RESOLVES]->(iss:Issue) "
    "OPTIONAL MATCH (author:Person)-[:DECIDED]->(d) "
    "OPTIONAL MATCH (reviewer:Person)-[:REVIEWED]->(pr) "
    "OPTIONAL MATCH (newer:Decision)-[:SUPERSEDES*1..5]->(d) "
    "RETURN target, c, pr, d, inc, iss, author, reviewer, collect(DISTINCT newer) as superseding_decisions"
)

CYPHER_CHECK_SUPERSEDED = (
    "MATCH (d:Decision {id: $decision_id}) "
    "OPTIONAL MATCH (newer:Decision)-[r:SUPERSEDES*1..5]->(d) "
    "RETURN newer, r "
    "ORDER BY newer.timestamp DESC"
)
