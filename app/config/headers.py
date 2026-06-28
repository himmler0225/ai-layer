from __future__ import annotations

from typing import Dict


def get_data_miner_headers(api_key: str) -> Dict:
    return {"X-API-Key": api_key}


def get_supabase_rest_headers(service_key: str) -> Dict:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }


def get_supabase_auth_headers(token: str, anon_key: str) -> Dict:
    return {
        "Authorization": f"Bearer {token}",
        "apikey": anon_key,
    }
