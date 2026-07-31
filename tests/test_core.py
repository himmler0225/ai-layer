import pytest

from app.ingest.processing.curate import curate_review_rows, merge_curated
from app.ingest.processing.quality import is_indexable_comment
from app.rag.movie_hint import enrich_short_followup_task, is_short_followup, wants_catalog
from app.services.agent.tooling import filter_tools_by_platform, prepare_tools, serialize_result


def test_filter_tools_youtube_only():
    tools = [
        {"name": "youtube_search"},
        {"name": "tiktok_search"},
    ]
    filtered = filter_tools_by_platform(tools, "tìm video youtube về iphone")
    assert [t["name"] for t in filtered] == ["youtube_search"]


def test_prepare_tools_movie_context():
    tools = [
        {"name": "youtube_search"},
        {"name": "search_movie_summary"},
        {"name": "tiktok_profile"},
    ]
    task = "[Phim đang xem]\nTên: Dune Part Two\n[Câu hỏi hiện tại]\nReview giúp tôi"
    narrowed = prepare_tools(tools, task)
    names = {t["name"] for t in narrowed}
    assert "search_movie_summary" in names
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
        {"id": "a", "content": "good review here", "likes": 5, "movie_id": "m1"},
        {"id": "b", "content": "better review here", "likes": 50, "movie_id": "m1"},
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
            "movie_id": "m1",
            "rank": 1,
        }
    ]
    new_rows = [
        {
            "id": "new",
            "content": "brand new review text",
            "likes": 99,
            "movie_id": "m1",
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


def test_short_followup_detection():
    assert is_short_followup("Lấy đi")
    assert is_short_followup("tiếp đi")
    assert not is_short_followup("tôi muốn xem bình luận thô")


def test_prepare_tools_raw_comments_from_history():
    tools = [
        {"name": "youtube_get_comments"},
        {"name": "search_movie_summary"},
        {"name": "tiktok_search"},
    ]
    task = (
        "[Lịch sử hội thoại]\n"
        "User: tôi muốn xem bình luận thô\n"
        "Assistant: đang lấy...\n"
        "\n[Câu hỏi hiện tại]\n"
        "Lấy đi"
    )
    narrowed = prepare_tools(tools, task)
    names = {t["name"] for t in narrowed}
    assert "youtube_get_comments" in names
    assert "search_movie_summary" not in names


def test_prepare_tools_review_from_history():
    tools = [
        {"name": "youtube_search"},
        {"name": "search_movie_summary"},
        {"name": "tiktok_profile"},
    ]
    task = (
        "[Lịch sử hội thoại]\n"
        "User: Người ta nói gì về phim resident evil\n"
        "\n[Câu hỏi hiện tại]\n"
        "tiếp đi"
    )
    narrowed = prepare_tools(tools, task)
    names = {t["name"] for t in narrowed}
    assert "search_movie_summary" in names
    assert "tiktok_profile" not in names


def test_enrich_short_followup_adds_hints():
    task = (
        "[Lịch sử hội thoại]\n"
        "User: review phim Dune Part Two\n"
        "\n[Câu hỏi hiện tại]\n"
        "Lấy đi"
    )
    enriched = enrich_short_followup_task(task)
    assert "[Ngữ cảnh từ lịch sử]" in enriched
    assert "Dune Part Two" in enriched


def test_wants_catalog_intent():
    assert wants_catalog("Tôi muốn xem 1 phim tình cảm của Trung")
    assert wants_catalog("gợi ý phim hành động Hàn Quốc")
    assert not wants_catalog("review phim Dune Part Two")


def test_prepare_tools_catalog_narrows_to_movie():
    tools = [
        {"name": "youtube_search"},
        {"name": "movie_list_by_genre"},
        {"name": "movie_get_metadata"},
        {"name": "search_movie_summary"},
    ]
    task = "Tôi muốn xem 1 phim tình cảm của Trung"
    narrowed = prepare_tools(tools, task)
    names = {t["name"] for t in narrowed}
    assert names == {"movie_list_by_genre", "movie_get_metadata"}
    assert "youtube_search" not in names
    assert "search_movie_summary" not in names


def test_catalog_fallback_romance_china():
    from app.services.agent.guards import catalog_fallback_call, catalog_forced_tool_choice

    task = "Tôi muốn xem 1 phim tình cảm của Trung"
    tools = [
        {"name": "movie_list_by_genre"},
        {"name": "movie_list_by_country"},
        {"name": "movie_get_metadata"},
    ]
    forced = catalog_forced_tool_choice(task, tools)
    assert forced == {"type": "function", "function": {"name": "movie_list_by_genre"}}

    call = catalog_fallback_call(task, tools)
    assert call is not None
    assert call.name == "movie_list_by_genre"
    assert "tinh-cam" in call.arguments
    assert "trung-quoc" in call.arguments
