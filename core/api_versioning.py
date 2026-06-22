"""
API versioning support for AI Engine
Provides version-aware request routing and deprecation warnings
"""
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import functools


@dataclass
class APIVersion:
    """API version definition"""
    version: str
    released_at: str
    deprecated_at: Optional[str] = None
    sunset_at: Optional[str] = None
    description: str = ""

    @property
    def is_deprecated(self) -> bool:
        if not self.deprecated_at:
            return False
        return datetime.now() >= datetime.fromisoformat(self.deprecated_at)

    @property
    def is_sunset(self) -> bool:
        if not self.sunset_at:
            return False
        return datetime.now() >= datetime.fromisoformat(self.sunset_at)


class VersionRegistry:
    """Registry of API versions"""

    def __init__(self):
        self.versions: Dict[str, APIVersion] = {}
        self.current_version: str = "v1"
        self.default_version: str = "v1"

    def register(self, version: str, released_at: str = None, **kwargs):
        """Register an API version"""
        if released_at is None:
            released_at = datetime.now().isoformat()

        self.versions[version] = APIVersion(
            version=version,
            released_at=released_at,
            **kwargs
        )

    def get_version(self, version: str) -> Optional[APIVersion]:
        """Get version info"""
        return self.versions.get(version)

    def get_all_versions(self) -> Dict[str, Dict]:
        """Get all versions with status"""
        return {
            ver: {
                "released": v.released_at,
                "deprecated": v.deprecated_at,
                "sunset": v.sunset_at,
                "is_deprecated": v.is_deprecated,
                "is_sunset": v.is_sunset,
                "description": v.description
            }
            for ver, v in self.versions.items()
        }

    def get_current_version(self) -> APIVersion:
        """Get current version"""
        return self.versions.get(self.current_version)

    def get_supported_versions(self) -> list:
        """Get list of supported (non-sunset) versions"""
        return [v for v, ver in self.versions.items() if not ver.is_sunset]


# Global registry
version_registry = VersionRegistry()

# Register versions
version_registry.register("v1", released_at="2026-01-01", description="Initial release")
version_registry.register("v2", released_at="2026-06-18", description="Enhanced with advanced features")


def requires_version(min_version: str = None, max_version: str = None):
    """Decorator to require specific API version"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract version from kwargs or use default
            version = kwargs.get("api_version", version_registry.current_version)

            ver_info = version_registry.get_version(version)
            if not ver_info:
                raise ValueError(f"API version {version} not found")

            if ver_info.is_sunset:
                raise ValueError(f"API version {version} has been sunset")

            if min_version and version < min_version:
                raise ValueError(f"Minimum version is {min_version}")

            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_deprecation_headers(version: str) -> Dict[str, str]:
    """Get deprecation headers for a version"""
    ver_info = version_registry.get_version(version)
    if not ver_info:
        return {}

    headers = {}

    if ver_info.is_deprecated:
        headers["Deprecation"] = "true"
        if ver_info.sunset_at:
            headers["Sunset"] = ver_info.sunset_at

    return headers


def get_version_info() -> Dict:
    """Get API version information"""
    return {
        "current": version_registry.current_version,
        "default": version_registry.default_version,
        "supported": version_registry.get_supported_versions(),
        "versions": version_registry.get_all_versions()
    }
