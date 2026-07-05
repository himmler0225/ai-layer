"""Tests for Supabase DATABASE_URL normalization."""

from app.config.db.url import database_connect_args, database_url_label, normalize_async_database_url, resolve_database_url


def test_normalize_async_url():
    assert normalize_async_database_url("postgresql://u:p@host/db").startswith("postgresql+asyncpg://")


def test_supabase_ssl_connect_args():
    url = "postgresql://postgres.x:secret@aws-0-ap.pooler.supabase.com:6543/postgres?sslmode=require"
    _, args = resolve_database_url(url)
    assert "ssl" in args


def test_local_no_ssl_by_default():
    url = "postgresql://postgres:postgres@localhost:5432/reviewmine"
    assert database_connect_args(url) == {}


def test_database_url_label_hides_password():
    url = "postgresql://postgres.x:secret@aws-0-ap.pooler.supabase.com:6543/postgres?sslmode=require"
    label = database_url_label(url)
    assert "secret" not in label
    assert "postgres.x@aws-0-ap.pooler.supabase.com:6543/postgres" in label
    assert "ssl=yes" in label
