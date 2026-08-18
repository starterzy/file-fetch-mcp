import ipaddress
import socket
from urllib.parse import urlparse


class UrlBlocked(ValueError):
    pass


def _blocked_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast


def validate_url(url: str, *, allow_private: bool = False):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UrlBlocked("only HTTP and HTTPS URLs are allowed")
    host = parsed.hostname.rstrip(".")
    if not allow_private:
        try:
            if _blocked_ip(host):
                raise UrlBlocked("private or local addresses are not allowed")
        except ValueError:
            try:
                addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))}
            except OSError as exc:
                raise UrlBlocked("host could not be resolved") from exc
            if not addresses or any(_blocked_ip(address) for address in addresses):
                raise UrlBlocked("host resolves to a private or local address")
    if parsed.username or parsed.password:
        raise UrlBlocked("URL credentials are not allowed")
    return parsed
