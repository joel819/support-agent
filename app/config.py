"""Settings from environment variables / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "support-agent"
    data_dir: Path = Path("./data")
    database_url: str = ""  # defaults to sqlite in data_dir
    seed_on_startup: bool = True

    # LLM (Groq free tier via the OpenAI-compatible API)
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    llm_timeout_seconds: float = 30.0
    llm_temperature: float = 0.0
    max_agent_steps: int = 4  # max LLM turns per question (tool rounds + final answer)

    # Embeddings: "sentence-transformers" (real, local) or "hash" (offline, no download)
    embedding_backend: str = "sentence-transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Policy retrieval
    top_k: int = 3
    min_score: float | None = None  # unset = 0.25 for MiniLM, 0.05 for hash

    @property
    def demo_mode(self) -> bool:
        return not self.groq_api_key

    @property
    def effective_min_score(self) -> float:
        if self.min_score is not None:
            return self.min_score
        return 0.05 if self.embedding_backend == "hash" else 0.25

    @property
    def sqlite_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.data_dir / 'app.db').as_posix()}"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"


@lru_cache
def get_settings() -> Settings:
    return Settings()
