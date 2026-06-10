from fastapi import Request
from slowapi import Limiter

def get_client_ip(request: Request) -> str:
    if cf_ip := request.headers.get("cf-connecting-ip"):
        return cf_ip

    if forwarded := request.headers.get("x-forwarded-for"):
        return forwarded.split(",")[0].strip()

    return request.client.host


limiter = Limiter(key_func=get_client_ip)