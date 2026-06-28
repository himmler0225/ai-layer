import pytest

from app.ingest.processing.curate import curate_review_rows, merge_curated
from app.ingest.processing.quality import is_indexable_comment
from app.services.agent.platform import filter_tools_by_platform, prepare_tools
from app.services.agent.serialize import serialize_result


def test_filter_tools_youtube_only():
    tools = [
        {"name": "youtube_search"},
        {"name": "tiktok_search"},
    ]
    filtered = filter_tools_by_platform(tools, "tìm video youtube về iphone")
    assert [t["name"] for t in filtered] == ["youtube_search"]


def test_prepare_tools_product_context():
    tools = [
        {"name": "youtube_search"},
        {"name": "search_product_summary"},
        {"name": "tiktok_profile"},
    ]
    task = "[Sản phẩm đang xem]\nTên: iPhone 16\n[Câu hỏi hiện tại]\nReview giúp tôi"
    narrowed = prepare_tools(tools, task)
    names = {t["name"] for t in narrowed}
    assert "search_product_summary" in names
    assert "tiktok_profile" not in names


def test_serialize_trims_comments(monkeypatch):
    import app.config.settings as settings

    monkeypatch.setattr(settings, "AGENT_MAX_RESULT_CHARS", 5000)
    monkeypatch.setattr(settings, "AGENT_MAX_COMMENT_LEN", 20)
    monkeypatch.setattr(settings, "AGENT_MAX_COMMENTS", 10)

    raw = {
        "comments": [
            {"content": "x" * 80, "likes": 1},
            {"content": "ok review", "likes": 2},
        ]
    }
    out = serialize_result(raw)
    assert "ok review" in out
    assert "x" * 80 not in out


def test_curate_review_rows_ranking():
    rows = [
        {"id": "a", "content": "good review here", "likes": 5, "product_id": "p1"},
        {"id": "b", "content": "better review here", "likes": 50, "product_id": "p1"},
    ]
    curated = curate_review_rows(rows, top_n=2)
    assert len(curated) == 2
    assert curated[0]["raw_review_id"] == "b"
    assert curated[0]["rank"] == 1


def test_merge_curated_incremental():
    existing = [
        {
            "raw_review_id": "old",
            "content": "existing review text",
            "likes": 10,
            "product_id": "p1",
            "rank": 1,
        }
    ]
    new_rows = [
        {
            "id": "new",
            "content": "brand new review text",
            "likes": 99,
            "product_id": "p1",
        },
    ]
    merged = merge_curated(existing, new_rows, top_n=5)
    assert merged[0]["raw_review_id"] == "new"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", False),
        ("spam", False),
        ("Đây là review dài đủ để index", True),
    ],
)
def test_is_indexable_comment(text, expected):
    assert is_indexable_comment(text) is expected
