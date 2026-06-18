"""Tests for enterprise features: tenancy, RBAC, audit logging"""
import pytest
import tempfile
import shutil


@pytest.fixture
def tenant_manager():
    from enterprise import TenantManager
    temp_dir = tempfile.mkdtemp()
    manager = TenantManager(data_dir=temp_dir)
    yield manager
    shutil.rmtree(temp_dir)


@pytest.fixture
def audit_logger():
    from enterprise import AuditLogger
    temp_dir = tempfile.mkdtemp()
    logger = AuditLogger(log_dir=temp_dir)
    yield logger
    shutil.rmtree(temp_dir)


# === Tenant Tests ===

def test_create_tenant(tenant_manager):
    tenant = tenant_manager.create_tenant("Test Tenant")
    assert tenant.id.startswith("tenant_")
    assert tenant.name == "Test Tenant"
    assert tenant.api_key.startswith("sk_")


def test_get_tenant(tenant_manager):
    tenant = tenant_manager.create_tenant("Test Tenant")
    retrieved = tenant_manager.get_tenant(tenant.id)
    assert retrieved is not None
    assert retrieved.name == "Test Tenant"


def test_get_tenant_by_api_key(tenant_manager):
    tenant = tenant_manager.create_tenant("Test Tenant")
    retrieved = tenant_manager.get_tenant_by_api_key(tenant.api_key)
    assert retrieved is not None
    assert retrieved.id == tenant.id


def test_tenant_quotas():
    from enterprise import Tenant
    tenant = Tenant(id="test", name="Test", api_key="sk_test")
    assert "daily_requests" in tenant.quotas
    assert "monthly_requests" in tenant.quotas


# === User Tests ===

def test_create_user(tenant_manager):
    from enterprise import Role
    tenant = tenant_manager.create_tenant("Test Tenant")
    user = tenant_manager.create_user(tenant.id, "testuser", "test@example.com", Role.USER)
    assert user is not None
    assert user.username == "testuser"
    assert user.role == Role.USER


def test_get_user(tenant_manager):
    from enterprise import Role
    tenant = tenant_manager.create_tenant("Test Tenant")
    user = tenant_manager.create_user(tenant.id, "testuser", "test@example.com", Role.ADMIN)
    retrieved = tenant_manager.get_user(user.id)
    assert retrieved is not None
    assert retrieved.username == "testuser"


def test_get_user_by_api_key(tenant_manager):
    from enterprise import Role
    tenant = tenant_manager.create_tenant("Test Tenant")
    user = tenant_manager.create_user(tenant.id, "testuser", "test@example.com", Role.USER)
    retrieved = tenant_manager.get_user_by_api_key(user.api_key)
    assert retrieved is not None
    assert retrieved.id == user.id


def test_get_tenant_users(tenant_manager):
    from enterprise import Role
    tenant = tenant_manager.create_tenant("Test Tenant")
    tenant_manager.create_user(tenant.id, "user1", "user1@example.com", Role.USER)
    tenant_manager.create_user(tenant.id, "user2", "user2@example.com", Role.VIEWER)

    users = tenant_manager.get_tenant_users(tenant.id)
    assert len(users) == 2


# === Permission Tests ===

def test_admin_has_all_permissions(tenant_manager):
    from enterprise import Role, Permission
    tenant = tenant_manager.create_tenant("Test Tenant")
    user = tenant_manager.create_user(tenant.id, "admin", "admin@example.com", Role.ADMIN)

    for perm in Permission:
        assert tenant_manager.check_permission(user.api_key, perm)


def test_user_limited_permissions(tenant_manager):
    from enterprise import Role, Permission
    tenant = tenant_manager.create_tenant("Test Tenant")
    user = tenant_manager.create_user(tenant.id, "user", "user@example.com", Role.USER)

    assert tenant_manager.check_permission(user.api_key, Permission.READ)
    assert tenant_manager.check_permission(user.api_key, Permission.WRITE)
    assert not tenant_manager.check_permission(user.api_key, Permission.DELETE)
    assert not tenant_manager.check_permission(user.api_key, Permission.MANAGE_PROVIDERS)


def test_viewer_read_only(tenant_manager):
    from enterprise import Role, Permission
    tenant = tenant_manager.create_tenant("Test Tenant")
    user = tenant_manager.create_user(tenant.id, "viewer", "viewer@example.com", Role.VIEWER)

    assert tenant_manager.check_permission(user.api_key, Permission.READ)
    assert not tenant_manager.check_permission(user.api_key, Permission.WRITE)
    assert not tenant_manager.check_permission(user.api_key, Permission.DELETE)


# === Quota Tests ===

def test_check_quota(tenant_manager):
    tenant = tenant_manager.create_tenant("Test Tenant")
    assert tenant_manager.check_quota(tenant.id, "daily_requests")


def test_increment_usage(tenant_manager):
    tenant = tenant_manager.create_tenant("Test Tenant")
    tenant_manager.increment_usage(tenant.id, "daily_requests", 10)

    stats = tenant_manager.get_tenant_stats(tenant.id)
    assert stats["usage"]["daily_requests"] == 10


def test_quota_exceeded(tenant_manager):
    tenant = tenant_manager.create_tenant("Test Tenant", quotas={"daily_requests": 5})
    tenant_manager.increment_usage(tenant.id, "daily_requests", 10)

    assert not tenant_manager.check_quota(tenant.id, "daily_requests")


# === Audit Logger Tests ===

def test_audit_log(audit_logger):
    audit_logger.log("login", "user_123", "tenant_456", {"method": "password"})

    events = audit_logger.query(tenant_id="tenant_456")
    assert len(events) == 1
    assert events[0]["event_type"] == "login"


def test_audit_query_filters(audit_logger):
    audit_logger.log("login", "user_1", "tenant_1")
    audit_logger.log("logout", "user_1", "tenant_1")
    audit_logger.log("login", "user_2", "tenant_2")

    # Filter by event type
    events = audit_logger.query(event_type="login")
    assert len(events) == 2

    # Filter by tenant
    events = audit_logger.query(tenant_id="tenant_1")
    assert len(events) == 2

    # Filter by user
    events = audit_logger.query(user_id="user_2")
    assert len(events) == 1


def test_audit_log_details(audit_logger):
    audit_logger.log("api_call", "user_1", "tenant_1",
                     details={"endpoint": "/v1/chat", "status": 200},
                     ip_address="192.168.1.1")

    events = audit_logger.query()
    assert len(events) == 1
    assert events[0]["details"]["endpoint"] == "/v1/chat"
    assert events[0]["ip_address"] == "192.168.1.1"
