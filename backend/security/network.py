"""Where connectors may connect.

Connector settings are typed in by an organization's administrator, so they decide which address Lumina's
server connects to. Without this check someone could point a connector at addresses inside Lumina's own
network (the database, cloud metadata services) and use the server to reach them. Only public internet
addresses are allowed, unless CONNECTORS_ALLOW_PRIVATE_HOSTS is on (local development, where the demo
databases run on this machine).
"""

import ipaddress
import socket

from django.conf import settings


class BlockedAddress(ValueError):
    pass


def _is_public(ip):
    address = ipaddress.ip_address(ip)
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def check_host(host, port=None):
    """Raise BlockedAddress unless every address the host name points to is on the public internet.
    Returns the first resolved address."""
    host = (host or "").strip()
    if not host:
        raise BlockedAddress("Enter the server address.")
    try:
        infos = socket.getaddrinfo(host, port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise BlockedAddress(f"The address {host} could not be found.") from exc
    addresses = [info[4][0] for info in infos]
    if not settings.CONNECTORS_ALLOW_PRIVATE_HOSTS and not all(_is_public(ip) for ip in addresses):
        raise BlockedAddress(f"{host} is a private or internal address. Connectors may only reach public servers.")
    return addresses[0]
