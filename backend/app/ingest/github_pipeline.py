import re
import urllib.request
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.graph.client import graph_client, logger

class GitHubPipeline:
    @staticmethod
    def ingest_public_repo(repo_full_name: str, max_items: int = 15, github_token: Optional[str] = None) -> Dict[str, Any]:
        clean_name = repo_full_name.strip().replace("https://github.com/", "").strip("/")
        parts = clean_name.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repository format '{repo_full_name}'. Expected 'owner/repo' (e.g. psf/requests)")
        
        owner, repo = parts
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "WhyTrace-Codebase-Archaeology"
        }
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        engine = graph_client.embedded

        prs_url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=closed&per_page={max_items}"
        prs_data = GitHubPipeline._fetch_json(prs_url, headers)

        commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page={max_items}"
        commits_data = GitHubPipeline._fetch_json(commits_url, headers)

        stats = {
            "repo": f"{owner}/{repo}",
            "prs_ingested": 0,
            "commits_ingested": 0,
            "decisions_extracted": 0,
            "entities_created": 0,
            "supersessions_detected": 0
        }

        pr_decision_map = {}
        all_decisions = []

        for pr in prs_data:
            pr_num = pr.get("number")
            pr_id = f"gh_pr_{repo}_{pr_num}"
            title = pr.get("title", "")
            body = pr.get("body") or ""
            merged_at = pr.get("merged_at") or pr.get("closed_at") or datetime.utcnow().isoformat()
            user = pr.get("user", {})
            username = user.get("login", "unknown")
            user_id = f"person_{username}"

            engine.add_node(user_id, ["Person"], {
                "name": username,
                "handle": f"@{username}",
                "email": f"{username}@github.com",
                "role": "Core Contributor",
                "is_active": True
            })

            engine.add_node(pr_id, ["PullRequest"], {
                "id": pr_id,
                "number": pr_num,
                "title": title,
                "body": (body[:280] + "...") if len(body) > 280 else body,
                "merged_at": merged_at,
                "url": pr.get("html_url", "#")
            })
            stats["prs_ingested"] += 1

            decision_summary = GitHubPipeline._extract_decision_summary(title, body)
            decision_id = f"gh_dec_{repo}_{pr_num}"
            engine.add_node(decision_id, ["Decision"], {
                "id": decision_id,
                "title": f"Decision: {title}",
                "summary": decision_summary,
                "rationale": (body[:200] + "...") if body else "Merged pull request policy change.",
                "timestamp": merged_at,
                "status": "ACTIVE"
            })
            stats["decisions_extracted"] += 1

            engine.add_relationship(pr_id, decision_id, "PRODUCED")
            engine.add_relationship(user_id, decision_id, "DECIDED")
            engine.add_relationship(user_id, pr_id, "REVIEWED")

            pr_decision_map[pr_num] = decision_id
            all_decisions.append({
                "id": decision_id,
                "number": pr_num,
                "title": title,
                "body": body,
                "date": merged_at
            })

            supersedes_matches = re.findall(r"(?:supersedes?|replaces?|reverts?|overrides?)\s+#?(\d+)", body + " " + title, re.IGNORECASE)
            for target_pr_num_str in supersedes_matches:
                target_pr_num = int(target_pr_num_str)
                if target_pr_num in pr_decision_map:
                    prior_dec_id = pr_decision_map[target_pr_num]
                    engine.add_relationship(decision_id, prior_dec_id, "SUPERSEDES", {
                        "date": merged_at,
                        "reason": f"Overridden by PR #{pr_num}: {title}"
                    })
                    if prior_dec_id in engine.nodes:
                        engine.nodes[prior_dec_id]["properties"]["status"] = "SUPERSEDED"
                    stats["supersessions_detected"] += 1

        for commit in commits_data:
            sha = commit.get("sha", "")[:10]
            c_id = f"commit_{sha}"
            commit_obj = commit.get("commit", {})
            message = commit_obj.get("message", "").split("\n")[0]
            date = commit_obj.get("author", {}).get("date") or datetime.utcnow().isoformat()
            author_name = commit_obj.get("author", {}).get("name") or "developer"

            engine.add_node(c_id, ["Commit"], {
                "sha": sha,
                "message": message,
                "timestamp": date,
                "author": author_name
            })
            stats["commits_ingested"] += 1

            entity_name = GitHubPipeline._extract_entity_from_message(message, repo)
            ent_id = f"ent_{repo}_{entity_name.replace('/', '_').replace('.', '_')}"
            
            if ent_id not in engine.nodes:
                engine.add_node(ent_id, ["CodeEntity"], {
                    "name": entity_name,
                    "type": "FILE" if ("." in entity_name or "/" in entity_name) else "CONFIG_KEY",
                    "path": entity_name,
                    "aliases": [entity_name.split("/")[-1]]
                })
                stats["entities_created"] += 1

            engine.add_relationship(c_id, ent_id, "TOUCHES")

            if all_decisions:
                top_dec = all_decisions[0]
                engine.add_relationship(top_dec["id"], ent_id, "GOVERNS")

        return {
            "status": "success",
            "message": f"Successfully ingested {owner}/{repo} from GitHub into Neo4j graph.",
            "stats": stats
        }

    @staticmethod
    def _fetch_json(url: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    return json.loads(response.read().decode())
        except Exception as e:
            logger.warning(f"GitHub API fetch error for {url}: {e}")
        return []

    @staticmethod
    def _extract_decision_summary(title: str, body: str) -> str:
        first_line_body = body.split("\n")[0].strip() if body else ""
        if first_line_body and len(first_line_body) > 15:
            return f"{title} — {first_line_body[:120]}"
        return f"Policy Decision: {title}"

    @staticmethod
    def _extract_entity_from_message(message: str, default_repo: str) -> str:
        file_match = re.search(r"([\w\-]+/[\w\-]+(?:\.[\w]+)?)", message)
        if file_match:
            return file_match.group(1)
        
        ident_match = re.search(r"(?:in|for|fix|refactor|feat)\s+([A-Za-z0-9_]{3,25})", message)
        if ident_match:
            return ident_match.group(1)
            
        return f"{default_repo}/core.py"
