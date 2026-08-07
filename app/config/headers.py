from app.config.service_auth import AI_LAYER_SERVICE_NAME


def get_data_miner_headers(api_key: str, service_token: str = "") -> dict[str, str]:
    """Build the HTTP headers used to authenticate requests to the data-miner service.

    Args:
        api_key: API key identifying this caller to the data-miner service.
        service_token: Optional inter-service token; when provided, sent as
            `X-Service-Token`.

    Returns:
        dict[str, str]: Headers including `X-API-Key`, `X-Service-Name`, and
        optionally `X-Service-Token`.
    """
    headers = {
        "X-API-Key": api_key,
        "X-Service-Name": AI_LAYER_SERVICE_NAME,
    }
    if service_token:
        headers["X-Service-Token"] = service_token
    return headers


def get_supabase_rest_headers(service_key: str) -> dict[str, str]:
    """Build the HTTP headers for authenticating against the Supabase REST API.

    Args:
        service_key: Supabase service-role key.

    Returns:
        dict[str, str]: `apikey` and `Authorization: Bearer` headers.
    """
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }


def get_supabase_auth_headers(token: str, anon_key: str) -> dict[str, str]:
    """Build the HTTP headers for a user-authenticated Supabase Auth request.

    Args:
        token: User's Supabase access (JWT) token.
        anon_key: Supabase anon/public API key.

    Returns:
        dict[str, str]: `Authorization: Bearer` and `apikey` headers.
    """
    return {
        "Authorization": f"Bearer {token}",
        "apikey": anon_key,
    }
