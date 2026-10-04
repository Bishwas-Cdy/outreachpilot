import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    pass


def _is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return bool(ip.is_global)


def validate_public_url(url: str, *, require_https: bool = False) -> str:
    parsed = urlparse(url)
    allowed_schemes = {"https"} if require_https else {"http", "https"}
    if parsed.scheme.lower() not in allowed_schemes:
        raise UnsafeURLError("URL must use an allowed HTTP scheme")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeURLError("URL must have a public hostname and no embedded credentials")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise UnsafeURLError("Localhost targets are blocked")
    try:
        direct_ip = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            addresses = {str(item[4][0]) for item in socket.getaddrinfo(hostname, parsed.port)}
        except socket.gaierror as exc:
            raise UnsafeURLError("Hostname could not be resolved") from exc
        if not addresses or any(not _is_public_ip(address) for address in addresses):
            raise UnsafeURLError("Hostname resolves to a non-public network") from None
    else:
        if not direct_ip.is_global:
            raise UnsafeURLError("Private, loopback, reserved, and link-local targets are blocked")
    return url
