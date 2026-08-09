"""movie-aggregator-api HTTP client — movie catalog (kkphim/ophim/vsmov)."""

from app.clients.movie_aggregator._http import close_client
from app.clients.movie_aggregator.movies import (
    movie_get_countries,
    movie_get_detail,
    movie_get_genres,
    movie_list_by_country,
    movie_list_by_genre,
    movie_list_by_type,
    movie_list_by_year,
    movie_list_new,
    movie_search,
)

__all__ = [
    "close_client",
    "movie_get_countries",
    "movie_get_detail",
    "movie_get_genres",
    "movie_list_by_country",
    "movie_list_by_genre",
    "movie_list_by_type",
    "movie_list_by_year",
    "movie_list_new",
    "movie_search",
]
