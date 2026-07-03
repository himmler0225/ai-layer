from app.services.agent.guards import (
    apply_tool_budget,
    count_tool_name,
    should_force_synthesis,
    tool_signature,
)


def test_no_force_after_search_budget_block():
    """Sau khi search lần 2 bị chặn budget, phải cho model gọi comments."""
    log = [
        {
            "tool": "youtube_search",
            "inputs": {"keyword": "iphone 16 pro max review"},
            "result": {"results": [{"video_id": "abc123", "title": "Review"}]},
        },
        {
            "tool": "youtube_search",
            "inputs": {"keyword": "iphone 16 pro max users say"},
            "result": {"error": "search_budget_exhausted", "video_ids": ["abc123"]},
        },
    ]
    assert should_force_synthesis(log, iteration=2, max_iter=15) is False


def test_force_after_same_non_search_tool():
    log = [
        {"tool": "youtube_get_comments_batch", "inputs": {"video_ids": ["a"]}},
        {"tool": "youtube_get_comments_batch", "inputs": {"video_ids": ["a"]}},
    ]
    assert should_force_synthesis(log, iteration=2, max_iter=15) is True


def test_force_after_identical_signature_non_search():
    log = [
        {"tool": "youtube_get_transcript", "inputs": {"video_id": "x"}},
    ] * 2
    assert should_force_synthesis(log, iteration=2, max_iter=15) is True


def test_force_on_stubborn_search():
    log = [
        {"tool": "youtube_search", "inputs": {"keyword": "a"}, "result": {"results": []}},
    ] + [
        {
            "tool": "youtube_search",
            "inputs": {"keyword": f"k{i}"},
            "result": {"error": "search_budget_exhausted"},
        }
        for i in range(3)
    ]
    assert should_force_synthesis(log, iteration=4, max_iter=15) is True


def test_force_on_max_iter():
    log = [{"tool": "youtube_search", "inputs": {"keyword": "x"}}]
    assert should_force_synthesis(log, iteration=15, max_iter=15) is True


def test_no_force_on_first_search():
    log = [{"tool": "youtube_search", "inputs": {"keyword": "a"}}]
    assert should_force_synthesis(log, iteration=1, max_iter=15) is False


def test_tool_budget_removes_youtube_search_after_one():
    ctx = {
        "tools": [{"name": "youtube_search"}, {"name": "youtube_get_comments_batch"}],
        "tool_call_log": [{"tool": "youtube_search", "inputs": {"keyword": "x"}, "result": {}}],
    }
    apply_tool_budget(ctx)
    names = {t["name"] for t in ctx["tools"]}
    assert "youtube_search" not in names
    assert "youtube_get_comments_batch" in names


def test_search_budget_exhausted():
    from app.services.agent.guards import is_search_budget_exhausted

    log = [{"tool": "youtube_search", "inputs": {}}]
    assert is_search_budget_exhausted("youtube_search", log) is True
    assert is_search_budget_exhausted("youtube_get_comments_batch", log) is False


def test_search_budget_message_includes_video_ids():
    from app.services.agent.guards import search_budget_message

    log = [
        {
            "tool": "youtube_search",
            "inputs": {"keyword": "iphone"},
            "result": {"results": [{"video_id": "vid1", "title": "t"}]},
        },
    ]
    msg = search_budget_message("youtube_search", log)
    assert msg["video_ids"] == ["vid1"]


def test_tool_signature_stable():
    assert tool_signature("youtube_search", {"keyword": "x"}) == tool_signature("youtube_search", {"keyword": "x"})


def test_count_tool_name():
    log = [
        {"tool": "youtube_search", "inputs": {"keyword": "a"}},
        {"tool": "youtube_search", "inputs": {"keyword": "b"}},
    ]
    assert count_tool_name(log, "youtube_search") == 2
