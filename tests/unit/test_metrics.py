from core import metrics


def test_counters_and_observations_render() -> None:
    metrics.reset()
    metrics.inc("docvault_publish_total")
    metrics.inc("docvault_publish_total", 2)
    metrics.observe("stage_seconds", 0.5)
    metrics.observe("stage_seconds", 1.5)

    data = metrics.snapshot()
    assert data["counters"]["docvault_publish_total"] == 3
    assert data["observations"]["stage_seconds"] == {"sum": 2.0, "count": 2}

    text = metrics.render()
    assert "docvault_publish_total 3" in text
    assert "stage_seconds_sum 2.000000" in text
    assert "stage_seconds_count 2" in text
    metrics.reset()
    assert metrics.snapshot()["counters"] == {}
