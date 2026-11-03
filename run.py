import uvicorn
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

if __name__ == "__main__":
    print("=" * 70)
    print("  Starting WhyTrace — Temporal Decision Graph Engine for Codebases")
    print("  Track: Best Use of Neo4j AuraDB | Problem Statement: T1.1")
    print("=" * 70)
    print("  Server running at: http://localhost:8000")
    print("=" * 70)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
