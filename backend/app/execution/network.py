"""Destination validation and DNS pinning for untrusted external agents."""
import ipaddress
import socket
from urllib.parse import urlsplit
import anyio
import httpx

LOCAL_SAMPLE_URL = "http://127.0.0.1:9001/agent"

class DestinationError(ValueError):
    pass

def is_public_ip(address: str) -> bool:
    try:
        if "%" in address:
            return False
        ip = ipaddress.ip_address(address)
        if str(ip) == "168.63.129.16":  # Azure platform/metadata virtual IP
            return False
        # Reject transition/mapped forms even if they encode a public IPv4 address.
        return ip.is_global and not ip.is_multicast and not ip.is_reserved and not (isinstance(ip, ipaddress.IPv6Address) and (ip.ipv4_mapped or ip.sixtofour or ip.teredo or ip not in ipaddress.ip_network("2000::/3")))
    except ValueError:
        return False

def validate_external_url(value: str) -> str:
    # Require an ASCII URL. Encoded paths are allowed, encoded authority is not.
    if len(value) > 2048 or any(ord(c) <= 32 or ord(c) >= 127 for c in value) or "\\" in value:
        raise DestinationError("Use an ASCII HTTPS endpoint without whitespace or backslashes.")
    try:
        parts = urlsplit(value)
        host = parts.hostname
        if (parts.scheme != "https" or not host or parts.port not in (None, 443)
                or parts.username is not None or parts.password is not None or parts.query or parts.fragment
                or "%" in parts.netloc):
            raise ValueError()
    except ValueError:
        raise DestinationError("External endpoints require HTTPS on port 443, without credentials, query, or fragment.") from None
    host = host.lower()
    if host.endswith(".") or host in ("localhost", "metadata.google.internal") or host.endswith((".localhost", ".local", ".internal")):
        raise DestinationError("Local and internal destinations are not allowed.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if "." not in host or any(not part or not all(c.isalnum() or c == "-" for c in part) or part.startswith("-") or part.endswith("-") for part in host.split(".")):
            raise DestinationError("Use a valid public hostname.") from None
    else:
        if not is_public_ip(host):
            raise DestinationError("The endpoint must use a public destination.")
    return str(httpx.URL(value).copy_with(port=None))

async def resolve_public(host: str) -> str:
    try:
        records = await anyio.to_thread.run_sync(
            lambda: socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM), abandon_on_cancel=True
        )
    except OSError as exc:
        # Preserve the typed cause for provider diagnostics; never expose its text.
        raise DestinationError("dns_error") from exc
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not is_public_ip(address) for address in addresses):
        raise DestinationError("destination_blocked")
    return addresses[0]

def pinned_request_url(endpoint: str, address: str) -> tuple[httpx.URL, dict, dict]:
    url = httpx.URL(endpoint)
    # The TCP connection uses the numeric IP; TLS SNI and certificate validation
    # still use the original hostname via HTTPX/httpcore's sni_hostname extension.
    return url.copy_with(host=address), {"Host": url.netloc.decode("ascii")}, {"sni_hostname": url.host}

