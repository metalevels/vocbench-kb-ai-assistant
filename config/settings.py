"""
Configuration settings for VocBench Knowledge Chat
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Anthropic API
    anthropic_api_key: str = Field(..., env='ANTHROPIC_API_KEY')

    # Google Group
    google_group_url: str = Field(
        default='https://groups.google.com/g/vocbench-user',
        env='GOOGLE_GROUP_URL'
    )
    scraper_user_agent: str = Field(
        default='VocBenchBot/1.0',
        env='SCRAPER_USER_AGENT'
    )

    # Vector Database
    vector_db_type: str = Field(default='chromadb', env='VECTOR_DB_TYPE')
    vector_db_host: str = Field(default='localhost', env='VECTOR_DB_HOST')
    vector_db_port: int = Field(default=8000, env='VECTOR_DB_PORT')
    chroma_persist_dir: str = Field(default='./data/chromadb', env='CHROMA_PERSIST_DIR')

    # Embeddings
    embedding_model: str = Field(
        default='all-MiniLM-L6-v2',
        env='EMBEDDING_MODEL'
    )
    embedding_dimension: int = Field(default=384, env='EMBEDDING_DIMENSION')
    chunk_size: int = Field(default=600, env='CHUNK_SIZE')
    chunk_overlap: int = Field(default=100, env='CHUNK_OVERLAP')

    # API
    api_host: str = Field(default='0.0.0.0', env='API_HOST')
    api_port: int = Field(default=8080, env='API_PORT')
    api_workers: int = Field(default=4, env='API_WORKERS')

    # Logging
    log_level: str = Field(default='INFO', env='LOG_LEVEL')
    log_dir: str = Field(default='./logs', env='LOG_DIR')

    # Scheduling
    refresh_schedule_cron: str = Field(
        default='0 2 * * 0',
        env='REFRESH_SCHEDULE_CRON'
    )

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False


# Global settings instance
settings = Settings()
