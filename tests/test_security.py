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
