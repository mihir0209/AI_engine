"""Tests for statistics_manager.py module"""
import os
import pytest
from datetime import datetime

from statistics_manager import StatisticsManager, KeyStatistics, get_stats_manager


@pytest.fixture
def stats_manager(tmp_path):
    stats_file = str(tmp_path / "test_stats.json")
    return StatisticsManager(stats_file=stats_file)


def test_key_statistics_defaults():
    ks = KeyStatistics()
    assert ks.requests == 0
    assert ks.successes == 0
    assert ks.failures == 0
    assert ks.last_used is None
    assert ks.rate_limited is False
    assert ks.weight == 1.0
    assert ks.total_response_time == 0.0
    assert ks.successful_response_time == 0.0


def test_key_statistics_success_rate():
    ks = KeyStatistics(requests=10, successes=7)
    assert ks.success_rate() == 70.0

    ks_zero = KeyStatistics()
    assert ks_zero.success_rate() == 0.0


def test_key_statistics_avg_response_time():
    ks = KeyStatistics(successes=5, successful_response_time=10.0)
    assert ks.avg_successful_response_time() == 2.0

    ks_zero = KeyStatistics()
    assert ks_zero.avg_successful_response_time() == 0.0


def test_key_statistics_to_dict():
    ks = KeyStatistics(requests=5, successes=3, weight=1.5)
    d = ks.to_dict()
    assert d["requests"] == 5
    assert d["successes"] == 3
    assert d["weight"] == 1.5
    assert d["last_used"] is None


def test_key_statistics_to_dict_with_datetime():
    now = datetime.now()
    ks = KeyStatistics(last_used=now)
    d = ks.to_dict()
    assert d["last_used"] == now.isoformat()


def test_key_statistics_from_dict():
    data = {
        "requests": 10,
        "successes": 8,
        "failures": 2,
        "rate_limited": False,
        "weight": 0.9,
        "total_response_time": 5.0,
        "successful_response_time": 4.0,
        "last_used": "2026-01-15T10:30:00"
    }
    ks = KeyStatistics.from_dict(data)
    assert ks.requests == 10
    assert ks.successes == 8
    assert ks.last_used == datetime.fromisoformat("2026-01-15T10:30:00")


def test_key_statistics_from_dict_missing_fields():
    ks = KeyStatistics.from_dict({"requests": 5})
    assert ks.requests == 5
    assert ks.successful_response_time == 0.0
    assert ks.last_used is None


def test_key_statistics_from_dict_invalid_datetime():
    ks = KeyStatistics.from_dict({"last_used": "invalid"})
    assert ks.last_used is None


def test_stats_manager_init(stats_manager):
    assert stats_manager.statistics == {}


def test_stats_manager_update(stats_manager):
    stats_manager.update_statistics("provider1", "key_0", success=True, response_time=1.5)
    ks = stats_manager.get_statistics("provider1", "key_0")
    assert ks is not None
    assert ks.requests == 1
    assert ks.successes == 1
    assert ks.total_response_time == 1.5
    assert ks.successful_response_time == 1.5


def test_stats_manager_update_failure(stats_manager):
    stats_manager.update_statistics("provider1", "key_0", success=False, response_time=2.0)
    ks = stats_manager.get_statistics("provider1", "key_0")
    assert ks.failures == 1
    assert ks.successes == 0


def test_stats_manager_weight_adjustment(stats_manager):
    # Success should decrease weight
    for _ in range(5):
        stats_manager.update_statistics("p1", "key_0", success=True, response_time=1.0)
    ks = stats_manager.get_statistics("p1", "key_0")
    assert ks.weight < 1.0

    # Failure should increase weight
    for _ in range(5):
        stats_manager.update_statistics("p1", "key_0", success=False, response_time=1.0)
    ks = stats_manager.get_statistics("p1", "key_0")
    assert ks.weight > 1.0


def test_stats_manager_mark_rate_limited(stats_manager):
    stats_manager.update_statistics("p1", "key_0", success=True)
    stats_manager.mark_rate_limited("p1", "key_0")
    ks = stats_manager.get_statistics("p1", "key_0")
    assert ks.rate_limited is True
    assert ks.weight == 2.0


def test_stats_manager_save_and_load(tmp_path):
    stats_file = str(tmp_path / "save_test.json")
    sm1 = StatisticsManager(stats_file=stats_file)
    sm1.update_statistics("p1", "key_0", success=True, response_time=1.0)
    sm1.update_statistics("p1", "key_0", success=True, response_time=2.0)
    sm1._save_statistics()

    sm2 = StatisticsManager(stats_file=stats_file)
    ks = sm2.get_statistics("p1", "key_0")
    assert ks is not None
    assert ks.requests == 2
    assert ks.successes == 2


def test_stats_manager_get_provider_report(stats_manager):
    stats_manager.update_statistics("p1", "key_0", success=True)
    stats_manager.update_statistics("p1", "key_1", success=False)
    report = stats_manager.get_provider_report("p1")
    assert "Key #1" in report
    assert "Key #2" in report


def test_stats_manager_get_provider_report_empty(stats_manager):
    report = stats_manager.get_provider_report("nonexistent")
    assert report == {}


def test_stats_manager_get_stats_summary(stats_manager):
    stats_manager.update_statistics("p1", "key_0", success=True)
    stats_manager.update_statistics("p2", "key_0", success=True)
    summary = stats_manager.get_stats_summary()
    assert summary["total_providers"] == 2
    assert summary["total_keys"] == 2
    assert summary["total_requests"] == 2


def test_stats_manager_save_now(stats_manager):
    stats_manager.update_statistics("p1", "key_0", success=True)
    stats_manager.save_now()
    assert os.path.exists(stats_manager.stats_file)


def test_stats_manager_load_nonexistent(tmp_path):
    sm = StatisticsManager(stats_file=str(tmp_path / "nonexistent.json"))
    assert sm.statistics == {}


def test_stats_manager_load_corrupted(tmp_path):
    stats_file = str(tmp_path / "corrupted.json")
    with open(stats_file, "w") as f:
        f.write("not valid json {{{")
    sm = StatisticsManager(stats_file=stats_file)
    assert sm.statistics == {}


def test_get_stats_manager():
    sm = get_stats_manager()
    assert sm is not None
    assert isinstance(sm, StatisticsManager)
