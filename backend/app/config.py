from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_timeout_seconds: float = 8.0
    llm_max_output_tokens: int = 220
    llm_max_calls_per_minute: int = 30

    seed_admin_password: str = ""
    seed_analyst_password: str = ""

    score_weight_xgb: float = 0.80
    score_weight_similarity: float = 0.20
    score_weight_rules: float = 0.0
    score_weight_anomaly: float = 0.0
    review_threshold: float = 0.30
    block_threshold: float = 0.70
    similarity_k: int = 10
    similarity_exact: bool = True
    learned_review_min: int = 3
    learned_block_min: int = 5

    rule_drain_ratio: float = 0.99
    rule_night_hour_end: int = 8
    rule_high_amount: float = 200_000
    rule_amount_cap: float = 10_000_000

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()