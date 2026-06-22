"""Tests for API versioning"""


# === Version Registry Tests ===

def test_register_version():
    from core.api_versioning import VersionRegistry
    vr = VersionRegistry()
    vr.register("v1", released_at="2026-01-01")
    assert "v1" in vr.versions


def test_get_version():
    from core.api_versioning import VersionRegistry
    vr = VersionRegistry()
    vr.register("v1", released_at="2026-01-01")
    ver = vr.get_version("v1")
    assert ver is not None
    assert ver.version == "v1"


def test_get_version_not_found():
    from core.api_versioning import VersionRegistry
    vr = VersionRegistry()
    assert vr.get_version("v99") is None


def test_get_all_versions():
    from core.api_versioning import VersionRegistry
    vr = VersionRegistry()
    vr.register("v1", released_at="2026-01-01")
    vr.register("v2", released_at="2026-06-01")
    all_versions = vr.get_all_versions()
    assert len(all_versions) == 2
    assert "v1" in all_versions
    assert "v2" in all_versions


def test_get_supported_versions():
    from core.api_versioning import VersionRegistry
    vr = VersionRegistry()
    vr.register("v1", released_at="2026-01-01")
    vr.register("v2", released_at="2026-06-01")
    vr.register("v3", released_at="2027-01-01", sunset_at="2027-01-01")

    supported = vr.get_supported_versions()
    assert "v1" in supported
    assert "v2" in supported
    # v3 is sunset


def test_set_current_version():
    from core.api_versioning import VersionRegistry
    vr = VersionRegistry()
    vr.register("v1")
    vr.register("v2")
    vr.current_version = "v2"
    assert vr.get_current_version().version == "v2"


# === API Version Tests ===

def test_api_version_deprecated():
    from core.api_versioning import APIVersion
    ver = APIVersion(
        version="v1",
        released_at="2026-01-01",
        deprecated_at="2026-06-01"
    )
    assert ver.is_deprecated is True


def test_api_version_not_deprecated():
    from core.api_versioning import APIVersion
    ver = APIVersion(
        version="v2",
        released_at="2026-06-01",
        deprecated_at="2027-01-01"
    )
    assert ver.is_deprecated is False


def test_api_version_sunset():
    from core.api_versioning import APIVersion
    ver = APIVersion(
        version="v1",
        released_at="2026-01-01",
        sunset_at="2026-01-01"
    )
    assert ver.is_sunset is True


# === Deprecation Headers Tests ===

def test_deprecation_headers_deprecated():
    from core.api_versioning import get_deprecation_headers, version_registry
    # Register directly in the global registry
    version_registry.register("v1", released_at="2026-01-01", deprecated_at="2026-06-01")

    headers = get_deprecation_headers("v1")
    assert headers.get("Deprecation") == "true"


def test_deprecation_headers_not_deprecated():
    from core.api_versioning import get_deprecation_headers
    # v2 is already registered globally without deprecation
    headers = get_deprecation_headers("v2")
    assert "Deprecation" not in headers


def test_deprecation_headers_unknown():
    from core.api_versioning import get_deprecation_headers
    headers = get_deprecation_headers("v99")
    assert headers == {}


# === Version Info Tests ===

def test_get_version_info():
    from core.api_versioning import get_version_info
    info = get_version_info()
    assert "current" in info
    assert "supported" in info
    assert "versions" in info
