"""Ingest pipeline configuration."""

from app.config.env import env_bool

INGEST_ENABLED: bool = env_bool("INGEST_ENABLED")
