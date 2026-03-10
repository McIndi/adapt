from adapt.security_urls import is_safe_next_path, normalize_next_path, login_redirect_url


def test_is_safe_next_path_accepts_relative_paths():
    assert is_safe_next_path("/") is True
    assert is_safe_next_path("/profile") is True
    assert is_safe_next_path("/admin/?tab=users") is True


def test_is_safe_next_path_rejects_external_and_protocol_relative():
    assert is_safe_next_path("https://evil.example") is False
    assert is_safe_next_path("//evil.example") is False
    assert is_safe_next_path("javascript:alert(1)") is False


def test_normalize_next_path_fallback():
    assert normalize_next_path("https://evil.example") == "/"
    assert normalize_next_path(None) == "/"


def test_login_redirect_url_encodes_safe_next():
    assert login_redirect_url("/admin/") == "/auth/login?next=/admin/"
    assert login_redirect_url("https://evil.example") == "/auth/login?next=/"
