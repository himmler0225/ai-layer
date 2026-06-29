from __future__ import annotations

from typing import Dict

from app.config.service_auth import AI_LAYER_SERVICE_NAME


def get_data_miner_headers(api_key: str, service_token: str = "") -> Dict[str, str]:
    headers = {
        "X-API-Key": api_key,
        "X-Service-Name": AI_LAYER_SERVICE_NAME,
    }
    if service_token:
        headers["X-Service-Token"] = service_token
    return headers


def get_supabase_rest_headers(service_key: str) -> Dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }


def get_supabase_auth_headers(token: str, anon_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "apikey": anon_key,
    }
