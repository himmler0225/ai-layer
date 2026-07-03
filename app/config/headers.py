from app.config.service_auth import AI_LAYER_SERVICE_NAME


def get_data_miner_headers(api_key: str, service_token: str = "") -> dict[str, str]:
    """Lấy data miner headers.

    Args:
        api_key: (str) Tham số `api_key`.
        service_token: (str, mặc định '') Tham số `service_token`.

    Returns:
        (Dict[str, str]) Kết quả trả về."""
    headers = {
        "X-API-Key": api_key,
        "X-Service-Name": AI_LAYER_SERVICE_NAME,
    }
    if service_token:
        headers["X-Service-Token"] = service_token
    return headers


def get_supabase_rest_headers(service_key: str) -> dict[str, str]:
    """Lấy supabase rest headers.

    Args:
        service_key: (str) Tham số `service_key`.

    Returns:
        (Dict[str, str]) Kết quả trả về."""
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }


def get_supabase_auth_headers(token: str, anon_key: str) -> dict[str, str]:
    """Lấy supabase auth headers.

    Args:
        token: (str) Tham số `token`.
        anon_key: (str) Tham số `anon_key`.

    Returns:
        (Dict[str, str]) Kết quả trả về."""
    return {
        "Authorization": f"Bearer {token}",
        "apikey": anon_key,
    }
