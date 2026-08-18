import pytest

from file_fetch_mcp.security import UrlBlocked, validate_url


def test_allows_anonymous_http_and_https():
    assert validate_url("http://example.com/file.pdf").scheme == "http"
    assert validate_url("https://example.com/file.pdf").scheme == "https"


@pytest.mark.parametrize(
    "url",
    ["file:///C:/secret.txt", "ftp://example.com/a", "http://localhost/a", "http://127.0.0.1/a"],
)
def test_blocks_unsafe_urls(url):
    with pytest.raises(UrlBlocked):
        validate_url(url)


def test_blocks_private_literal_ip():
    with pytest.raises(UrlBlocked):
        validate_url("http://10.0.0.5/a.pdf")


def test_allows_private_literal_ip_when_explicitly_enabled():
    assert validate_url("http://10.0.0.5/a.pdf", allow_private=True).hostname == "10.0.0.5"


def test_allows_localhost_when_explicitly_enabled():
    assert validate_url("http://localhost/a.pdf", allow_private=True).hostname == "localhost"
