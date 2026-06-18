"""Tests for structured logging and SLA monitoring"""
import pytest
import tempfile
import shutil


@pytest.fixture
def logger():
    from logging_sla import StructuredLogger
    temp_dir = tempfile.mkdtemp()
    log = StructuredLogger(log_dir=temp_dir)
    yield log
    shutil.rmtree(temp_dir)


@pytest.fixture
def sla_monitor():
    from logging_sla import SLAMonitor
    temp_dir = tempfile.mkdtemp()
    monitor = SLAMonitor(data_dir=temp_dir)
    yield monitor
    shutil.rmtree(temp_dir)


# === Structured Logger Tests ===

def test_logger_log_info(logger):
    logger.info("Test message", module="test")
    logger._flush()

    entries = logger.query(module="test")
    assert len(entries) >= 1
    assert entries[0]["level"] == "INFO"
    assert entries[0]["message"] == "Test message"


def test_logger_log_error(logger):
    logger.error("Error occurred", module="test", error="something went wrong")
    logger._flush()

    entries = logger.query(level="ERROR")
    assert len(entries) >= 1
    assert entries[0]["error"] == "something went wrong"


def test_logger_with_context(logger):
    logger.info("Request processed", module="api", request_id="req_123", provider="openai")
    logger._flush()

    entries = logger.query(module="api")
    assert len(entries) >= 1
    assert entries[0]["request_id"] == "req_123"
    assert entries[0]["provider"] == "openai"


def test_logger_query_filters(logger):
    logger.info("Message 1", module="api")
    logger.info("Message 2", module="db")
    logger.error("Error 1", module="api")
    logger._flush()

    # Filter by level
    errors = logger.query(level="ERROR")
    assert len(errors) == 1

    # Filter by module
    api_logs = logger.query(module="api")
    assert len(api_logs) == 2


def test_logger_stats(logger):
    logger.info("Info 1", module="api")
    logger.info("Info 2", module="api")
    logger.error("Error 1", module="api")
    logger._flush()

    stats = logger.get_stats(minutes=60)
    assert stats["total"] >= 3
    assert stats["error_count"] >= 1


# === SLA Monitor Tests ===

def test_register_metric(sla_monitor):
    sla_monitor.register_metric("test_metric", 95.0)
    assert "test_metric" in sla_monitor.metrics


def test_record_value_healthy(sla_monitor):
    sla_monitor.register_metric("availability", 99.0)
    sla_monitor.record_value("availability", 99.5)

    status = sla_monitor.get_status()
    assert status["availability"]["status"] == "healthy"


def test_record_value_breach(sla_monitor):
    sla_monitor.register_metric("availability", 99.0)
    sla_monitor.record_value("availability", 95.0)

    status = sla_monitor.get_status()
    assert status["availability"]["status"] == "breach"
    assert status["availability"]["breaches"] == 1


def test_breach_summary(sla_monitor):
    sla_monitor.register_metric("latency", 2000.0)
    sla_monitor.record_value("latency", 3000.0, higher_is_worse=True)
    sla_monitor.record_value("latency", 2500.0, higher_is_worse=True)

    # Verify breaches were recorded
    status = sla_monitor.get_status()
    assert status["latency"]["breaches"] == 2

    # Verify breach log has entries
    assert len(sla_monitor.breach_log) >= 2


def test_get_status(sla_monitor):
    sla_monitor.register_metric("metric1", 99.0)
    sla_monitor.register_metric("metric2", 100.0)

    status = sla_monitor.get_status()
    assert len(status) == 2
    assert "metric1" in status
    assert "metric2" in status
