"""Tests for the movie-aggregator-api client (app.clients.movie_aggregator):
query-param building, and the shared HTTP GET helper's retry/error behavior.

Uses httpx.MockTransport (stdlib to httpx, no extra dependency) instead of a
live movie-aggregator-api instance, so these stay hermetic like test_api_auth.py.
"""

from __future__ import annotations

import httpx
import pytest

from app.clients.movie_aggregator import _http, movies
from app.exceptions import AiLayerUpstreamError


@pytest.fixture(autouse=True)
async def _reset_client():
    """Ensure each test starts with no shared client and cleans up after itself."""
    await _http.close_client()
    yield
    await _http.close_client()


def _install_mock(handler):
    _http._client = httpx.AsyncClient(
        base_url="http://movie-aggregator.test",
        transport=httpx.MockTransport(handler),
    )


class TestSourceParam:
    def test_explicit_provider_is_used(self):
        assert movies._source_param("kkphim") == {"source": "kkphim"}

    def test_no_provider_falls_back_to_settings_default(self, monkeypatch):
        monkeypatch.setattr("app.clients.movie_aggregator.movies.settings.MOVIE_DEFAULT_PROVIDER", "")
        assert movies._source_param(None) == {}

    def test_settings_default_is_used_when_no_explicit_provider(self, monkeypatch):
        monkeypatch.setattr("app.clients.movie_aggregator.movies.settings.MOVIE_DEFAULT_PROVIDER", "ophim")
        assert movies._source_param(None) == {"source": "ophim"}


class TestMovieFilters:
    def test_drops_none_and_empty_values(self):
        result = movies._movie_filters(category="action", country=None, year="", sort_field="views")
        assert result == {"category": "action", "sort_field": "views"}


class TestGet:
    async def test_returns_parsed_json_on_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/movies/search"
            assert request.url.params["keyword"] == "one piece"
            return httpx.Response(200, json={"data": [{"slug": "one-piece"}]})

        _install_mock(handler)
        result = await movies.movie_search("one piece")
        assert result == {"data": [{"slug": "one-piece"}]}

    async def test_retries_on_retryable_status_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(_http, "retry_delay", lambda attempt: 0)
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            if attempts["n"] < 2:
                return httpx.Response(502)
            return httpx.Response(200, json={"data": []})

        _install_mock(handler)
        result = await _http.get("/api/movies/new")
        assert result == {"data": []}
        assert attempts["n"] == 2

    async def test_raises_upstream_error_after_exhausting_retries(self, monkeypatch):
        monkeypatch.setattr(_http, "retry_delay", lambda attempt: 0)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        _install_mock(handler)
        with pytest.raises(AiLayerUpstreamError):
            await _http.get("/api/movies/new")

    async def test_non_retryable_status_raises_immediately_without_retry(self, monkeypatch):
        monkeypatch.setattr(_http, "retry_delay", lambda attempt: 0)
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            return httpx.Response(404)

        _install_mock(handler)
        with pytest.raises(httpx.HTTPStatusError):
            await _http.get("/api/movies/does-not-exist")
        assert attempts["n"] == 1
