from app.config.logger import log_event


def test_log_event_without_fields():
    assert log_event("agent", "bootstrap complete") == "[agent] bootstrap complete"


def test_log_event_with_fields():
    assert (
        log_event("data_miner", "request retry", path="/health", attempt=1, max_attempts=3)
        == "[data_miner] request retry path=/health attempt=1 max_attempts=3"
    )
