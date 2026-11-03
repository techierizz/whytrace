from typing import Dict, Any

class BaselineVectorRAG:
    VECTOR_DOCUMENTS = [
        {
            "id": "doc_arch_rfc_2021",
            "title": "Architecture RFC 12 - Networking & Resilience (2021)",
            "content": (
                "Regarding connection pooling: RETRY_LIMIT is configured to 10. "
                "Because network blips between AWS availability zones cause spurious connection drops, "
                "we maintain an aggressive retry threshold of 10 to ensure zero dropped customer requests."
            ),
            "date": "2021-04-12",
            "similarity_score": 0.94
        },
        {
            "id": "doc_features_2020",
            "title": "Internal Constants Specification (2020)",
            "content": (
                "MAGIC_BUFFER_SIZE is set to 1460 in socket_reader.py. "
                "This value was calibrated by network performance engineering for optimal TCP MSS frame alignment."
            ),
            "date": "2020-03-01",
            "similarity_score": 0.88
        }
    ]

    @classmethod
    def simulate_vector_search(cls, query: str) -> Dict[str, Any]:
        query_norm = query.lower()
        
        if "retry" in query_norm or "limit" in query_norm or "pool" in query_norm:
            top_hit = cls.VECTOR_DOCUMENTS[0]
            return {
                "method": "Naive Vector Embedding Search (Cosine Similarity)",
                "top_similarity_score": top_hit["similarity_score"],
                "retrieved_document": top_hit["title"],
                "date_of_document": top_hit["date"],
                "generated_answer": (
                    "Based on the repository architecture documentation, the retry limit is set to 10. "
                    "This was implemented to ensure resilience against cross-AZ network latency spikes "
                    "and avoid 502 Bad Gateway responses."
                ),
                "flaw_explanation": (
                    "FAIL: Vector search returned a stale 2021 document because it has high semantic keyword match. "
                    "It has NO awareness that this decision was superseded following Incident INC-402 in 2023."
                ),
                "confidence_signal": "Hallucinated High (94% Cosine Match)"
            }
        elif "magic" in query_norm or "buffer" in query_norm:
            top_hit = cls.VECTOR_DOCUMENTS[1]
            return {
                "method": "Naive Vector Embedding Search (Cosine Similarity)",
                "top_similarity_score": top_hit["similarity_score"],
                "retrieved_document": top_hit["title"],
                "date_of_document": top_hit["date"],
                "generated_answer": (
                    "MAGIC_BUFFER_SIZE is 1460 because it matches the standard Ethernet MTU minus TCP/IP headers (TCP MSS)."
                ),
                "flaw_explanation": (
                    "FAIL: The model hallucinated a technical justification. In reality, the commit was an arbitrary patch "
                    "with zero documented rationale. Vector search encourages LLM hallucination."
                ),
                "confidence_signal": "Hallucinated High (88% Cosine Match)"
            }
        else:
            return {
                "method": "Naive Vector Embedding Search (Cosine Similarity)",
                "top_similarity_score": 0.42,
                "retrieved_document": "General Development Guide",
                "date_of_document": "2020-01-01",
                "generated_answer": "Standard engineering practice suggests reviewing the latest commits.",
                "flaw_explanation": "Low relevance match without causal evidence.",
                "confidence_signal": "Low"
            }
