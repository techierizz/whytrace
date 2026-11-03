import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "WhyTrace - Temporal Decision Graph Engine"
    VERSION: str = "1.0.0"
    
    NEO4J_URI: str = os.getenv("NEO4J_URI", "neo4j+s://your-instance.databases.neo4j.io")
    NEO4J_USER: str = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")
    
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", None)
    
    CONFIDENCE_REFUSAL_THRESHOLD: float = 0.35
    PORT: int = int(os.getenv("PORT", "8000"))

settings = Settings()
