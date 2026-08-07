from app.clients.data_miner._http import get as _get


async def search_web(query: str, max_results: int = 5) -> dict:
    return await _get("/api/google/search", {"q": query, "num_results": max_results})
