"""Tests for billing module"""
import pytest
import tempfile
import shutil


@pytest.fixture
def billing_manager():
    from core.billing import BillingManager
    temp_dir = tempfile.mkdtemp()
    manager = BillingManager(data_dir=temp_dir)
    yield manager
    shutil.rmtree(temp_dir)


# === Usage Recording Tests ===

def test_record_usage(billing_manager):
    record = billing_manager.record_usage(
        tenant_id="tenant_1",
        provider="openai",
        model="gpt-4",
        input_tokens=100,
        output_tokens=50,
        cost=0.01
    )
    assert record.id.startswith("usage_")
    assert record.tenant_id == "tenant_1"
    assert record.total_tokens == 150


def test_record_usage_with_metadata(billing_manager):
    record = billing_manager.record_usage(
        tenant_id="tenant_1",
        provider="openai",
        model="gpt-4",
        input_tokens=100,
        output_tokens=50,
        cost=0.01,
        user_id="user_1",
        metadata={"task_type": "coding"}
    )
    assert record.user_id == "user_1"
    assert record.metadata["task_type"] == "coding"


# === Usage Summary Tests ===

def test_get_tenant_usage(billing_manager):
    billing_manager.record_usage("tenant_1", "openai", "gpt-4", 100, 50, 0.01)
    billing_manager.record_usage("tenant_1", "openai", "gpt-4", 200, 100, 0.02)
    billing_manager.record_usage("tenant_1", "anthropic", "claude-3", 150, 75, 0.015)

    usage = billing_manager.get_tenant_usage("tenant_1")
    assert usage["tenant_id"] == "tenant_1"
    assert usage["total_requests"] == 3
    assert "openai" in usage["by_provider"]
    assert "anthropic" in usage["by_provider"]


def test_get_tenant_usage_with_dates(billing_manager):
    billing_manager.record_usage("tenant_1", "openai", "gpt-4", 100, 50, 0.01)

    usage = billing_manager.get_tenant_usage("tenant_1", start_date="2020-01-01", end_date="2030-12-31")
    assert usage["total_requests"] == 1


def test_get_user_usage(billing_manager):
    billing_manager.record_usage("tenant_1", "openai", "gpt-4", 100, 50, 0.01, user_id="user_1")
    billing_manager.record_usage("tenant_1", "openai", "gpt-4", 100, 50, 0.01, user_id="user_2")

    usage = billing_manager.get_user_usage("tenant_1", "user_1")
    assert usage["total_requests"] == 1


# === Invoice Tests ===

def test_generate_invoice(billing_manager):
    billing_manager.record_usage("tenant_1", "openai", "gpt-4", 100, 50, 0.01)
    billing_manager.record_usage("tenant_1", "anthropic", "claude-3", 150, 75, 0.015)

    invoice = billing_manager.generate_invoice("tenant_1", "2020-01-01", "2030-12-31")
    assert invoice.id.startswith("inv_")
    assert invoice.total_requests == 2
    assert "openai" in invoice.breakdown


def test_get_invoices(billing_manager):
    billing_manager.record_usage("tenant_1", "openai", "gpt-4", 100, 50, 0.01)
    billing_manager.generate_invoice("tenant_1", "2020-01-01", "2030-12-31")

    invoices = billing_manager.get_invoices("tenant_1")
    assert len(invoices) == 1


def test_mark_invoice_paid(billing_manager):
    billing_manager.record_usage("tenant_1", "openai", "gpt-4", 100, 50, 0.01)
    invoice = billing_manager.generate_invoice("tenant_1", "2020-01-01", "2030-12-31")

    result = billing_manager.mark_invoice_paid(invoice.id)
    assert result is True

    updated_invoice = billing_manager.invoices[invoice.id]
    assert updated_invoice.status == "paid"
    assert updated_invoice.paid_at is not None


# === Cost Alerts Tests ===

def test_cost_alerts_threshold(billing_manager):
    # Record usage that exceeds threshold
    for i in range(100):
        billing_manager.record_usage("tenant_1", "openai", "gpt-4", 1000, 500, 1.0)

    alerts = billing_manager.get_cost_alerts("tenant_1", threshold=50.0)
    assert len(alerts) > 0
    assert alerts[0]["type"] == "cost_threshold"


def test_no_alerts_under_threshold(billing_manager):
    billing_manager.record_usage("tenant_1", "openai", "gpt-4", 100, 50, 0.01)

    alerts = billing_manager.get_cost_alerts("tenant_1", threshold=100.0)
    assert len(alerts) == 0
