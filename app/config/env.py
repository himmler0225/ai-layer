import os


def env_bool(key: str, default: str = "false") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}
