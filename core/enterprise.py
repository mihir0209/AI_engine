"""
Multi-tenancy and RBAC module for AI Engine
Provides tenant isolation, API key scoping, and role-based access control
"""
import os
import json
import secrets
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Role(Enum):
    """User roles"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class Permission(Enum):
    """Permissions"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    MANAGE_PROVIDERS = "manage_providers"
    MANAGE_USERS = "manage_users"
    VIEW_ANALYTICS = "view_analytics"
    MANAGE_BILLING = "manage_billing"


# Role to permissions mapping
ROLE_PERMISSIONS = {
    Role.ADMIN: [p for p in Permission],  # All permissions
    Role.USER: [
        Permission.READ,
        Permission.WRITE,
        Permission.VIEW_ANALYTICS
    ],
    Role.VIEWER: [
        Permission.READ
    ]
}


@dataclass
class Tenant:
    """Tenant configuration"""
    id: str
    name: str
    api_key: str
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    quotas: Dict[str, int] = field(default_factory=lambda: {
        "daily_requests": 1000,
        "monthly_requests": 30000,
        "max_tokens_per_day": 1000000,
        "max_concurrent_requests": 10
    })
    usage: Dict[str, Any] = field(default_factory=lambda: {
        "daily_requests": 0,
        "monthly_requests": 0,
        "tokens_used_today": 0,
        "last_reset": datetime.now().isoformat()
    })
    settings: Dict[str, Any] = field(default_factory=lambda: {
        "allowed_providers": [],  # Empty = all allowed
        "blocked_providers": [],
        "default_model": "auto",
        "rate_limit_per_minute": 60
    })


@dataclass
class User:
    """User within a tenant"""
    id: str
    tenant_id: str
    username: str
    email: str
    role: Role
    api_key: str
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_login: Optional[str] = None
    permissions: List[Permission] = field(default_factory=list)

    def __post_init__(self):
        # Auto-assign permissions based on role if not provided
        if not self.permissions:
            self.permissions = ROLE_PERMISSIONS.get(self.role, [])


class TenantManager:
    """Manages tenants and users"""

    def __init__(self, data_dir: str = "data/tenants"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.tenants: Dict[str, Tenant] = {}
        self.users: Dict[str, User] = {}
        self._tenant_key_index: Dict[str, Tenant] = {}
        self._user_key_index: Dict[str, User] = {}
        self._load_data()

    def _rebuild_key_indexes(self):
        """Rebuild O(1) API key lookup indexes"""
        self._tenant_key_index = {t.api_key: t for t in self.tenants.values()}
        self._user_key_index = {u.api_key: u for u in self.users.values()}

    def _load_data(self):
        """Load tenant and user data from disk"""
        # Load tenants
        tenants_file = os.path.join(self.data_dir, "tenants.json")
        if os.path.exists(tenants_file):
            with open(tenants_file, "r") as f:
                data = json.load(f)
                for tid, tdata in data.items():
                    self.tenants[tid] = Tenant(**tdata)

        # Load users
        users_file = os.path.join(self.data_dir, "users.json")
        if os.path.exists(users_file):
            with open(users_file, "r") as f:
                data = json.load(f)
                for uid, udata in data.items():
                    udata["role"] = Role(udata["role"])
                    udata["permissions"] = [Permission(p) for p in udata.get("permissions", [])]
                    self.users[uid] = User(**udata)
        self._rebuild_key_indexes()

    def _save_data(self):
        """Save tenant and user data to disk"""
        # Save tenants
        tenants_file = os.path.join(self.data_dir, "tenants.json")
        with open(tenants_file, "w") as f:
            json.dump({tid: t.__dict__ for tid, t in self.tenants.items()}, f, indent=2)

        # Save users
        users_file = os.path.join(self.data_dir, "users.json")
        with open(users_file, "w") as f:
            json.dump({uid: {**u.__dict__, "role": u.role.value, "permissions": [p.value for p in u.permissions]}
                      for uid, u in self.users.items()}, f, indent=2)

    def create_tenant(self, name: str, quotas: Dict = None) -> Tenant:
        """Create a new tenant"""
        tenant_id = f"tenant_{secrets.token_hex(8)}"
        api_key = f"sk_{secrets.token_hex(24)}"

        tenant = Tenant(
            id=tenant_id,
            name=name,
            api_key=api_key,
            quotas=quotas or {}
        )

        self.tenants[tenant_id] = tenant
        self._rebuild_key_indexes()
        self._save_data()
        return tenant

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        return self.tenants.get(tenant_id)

    def get_tenant_by_api_key(self, api_key: str) -> Optional[Tenant]:
        """Get tenant by API key (O(1) via index)"""
        return self._tenant_key_index.get(api_key)

    def create_user(self, tenant_id: str, username: str, email: str, role: Role) -> Optional[User]:
        """Create a new user in a tenant"""
        if tenant_id not in self.tenants:
            return None

        user_id = f"user_{secrets.token_hex(8)}"
        api_key = f"sk_{secrets.token_hex(24)}"

        user = User(
            id=user_id,
            tenant_id=tenant_id,
            username=username,
            email=email,
            role=role,
            api_key=api_key
        )

        self.users[user_id] = user
        self._rebuild_key_indexes()
        self._save_data()
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.users.get(user_id)

    def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """Get user by API key (O(1) via index)"""
        return self._user_key_index.get(api_key)

    def get_tenant_users(self, tenant_id: str) -> List[User]:
        """Get all users for a tenant"""
        return [u for u in self.users.values() if u.tenant_id == tenant_id]

    def check_permission(self, api_key: str, permission: Permission) -> bool:
        """Check if an API key has a specific permission"""
        # Check tenant API key
        tenant = self.get_tenant_by_api_key(api_key)
        if tenant:
            return True  # Tenant API keys have all permissions

        # Check user API key
        user = self.get_user_by_api_key(api_key)
        if user and user.enabled:
            return permission in user.permissions

        return False

    def check_quota(self, tenant_id: str, quota_type: str) -> bool:
        """Check if tenant has quota available"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False

        # Reset daily quota if needed
        self._reset_daily_quota_if_needed(tenant)

        usage = tenant.usage.get(quota_type, 0)
        limit = tenant.quotas.get(quota_type, float('inf'))

        return usage < limit

    def increment_usage(self, tenant_id: str, quota_type: str, amount: int = 1):
        """Increment tenant usage"""
        tenant = self.get_tenant(tenant_id)
        if tenant:
            if quota_type not in tenant.usage:
                tenant.usage[quota_type] = 0
            tenant.usage[quota_type] += amount
            self._save_data()

    def _reset_daily_quota_if_needed(self, tenant: Tenant):
        """Reset daily quotas if a new day has started"""
        last_reset = tenant.usage.get("last_reset")
        if last_reset:
            last_reset_date = datetime.fromisoformat(last_reset).date()
            if last_reset_date < datetime.now().date():
                tenant.usage["daily_requests"] = 0
                tenant.usage["tokens_used_today"] = 0
                tenant.usage["last_reset"] = datetime.now().isoformat()
                self._save_data()

    def get_tenant_stats(self, tenant_id: str) -> Dict:
        """Get tenant usage statistics"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return {}

        return {
            "tenant_id": tenant_id,
            "name": tenant.name,
            "quotas": tenant.quotas,
            "usage": tenant.usage,
            "remaining": {
                "daily_requests": tenant.quotas.get("daily_requests", 0) - tenant.usage.get("daily_requests", 0),
                "monthly_requests": tenant.quotas.get("monthly_requests", 0) - tenant.usage.get("monthly_requests", 0)
            }
        }


class AuditLogger:
    """Audit logging for compliance"""

    def __init__(self, log_dir: str = "logs/audit"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def log(self, event_type: str, user_id: str, tenant_id: str,
            details: Dict = None, ip_address: str = None):
        """Log an audit event"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "details": details or {},
            "ip_address": ip_address
        }

        # Write to daily log file
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"audit_{date_str}.jsonl")

        with open(log_file, "a") as f:
            f.write(json.dumps(event) + "\n")

    def query(self, tenant_id: str = None, user_id: str = None,
              event_type: str = None, start_date: str = None,
              end_date: str = None, limit: int = 100) -> List[Dict]:
        """Query audit logs"""
        events = []

        # Read all log files
        for log_file in sorted(os.listdir(self.log_dir), reverse=True):
            if not log_file.endswith(".jsonl"):
                continue

            with open(os.path.join(self.log_dir, log_file), "r") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())

                        # Apply filters
                        if tenant_id and event.get("tenant_id") != tenant_id:
                            continue
                        if user_id and event.get("user_id") != user_id:
                            continue
                        if event_type and event.get("event_type") != event_type:
                            continue
                        if start_date and event.get("timestamp") < start_date:
                            continue
                        if end_date and event.get("timestamp") > end_date:
                            continue

                        events.append(event)

                        if len(events) >= limit:
                            return events
                    except json.JSONDecodeError:
                        continue

        return events


# Global instances
tenant_manager = TenantManager()
audit_logger = AuditLogger()
