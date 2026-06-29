from app.services.agent.synthesis import build_synthesis_input


def test_build_synthesis_input_truncates_large_log():
    log = [
        {
            "tool": "youtube_search",
            "inputs": {"keyword": "iphone"},
            "result": {"videos": [{"title": "x" * 5000}]},
        }
        for _ in range(20)
    ]
    items = build_synthesis_input("iPhone review?", log)
    assert len(items) == 1
    assert len(items[0]["content"]) <= 28_500
