import asyncio
import ipaddress
import socket

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site import Site


async def resolve_to_ip(hostname: str) -> str | None:
    """Resolve a hostname to its first IPv4 address, or return it as-is if
    it's already a valid IP.  Returns None when resolution fails."""
    try:
        ipaddress.ip_address(hostname)
        return hostname
    except ValueError:
        pass

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(
            hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM,
        )
        for family, *_rest, sockaddr in infos:
            ip = sockaddr[0]
            try:
                ipaddress.ip_address(ip)
                return ip
            except ValueError:
                continue
    except socket.gaierror:
        pass
    return None


def match_site_for_ip(ip_str: str, sites: list[Site]) -> Site | None:
    """Return the first site whose subnets contain the given IP, or None."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return None

    for site in sites:
        for subnet_str in site.subnets or []:
            try:
                network = ipaddress.ip_network(subnet_str, strict=False)
                if addr in network:
                    return site
            except ValueError:
                continue
    return None


async def detect_site(ip_or_hostname: str, db: AsyncSession) -> Site | None:
    """Resolve the hostname if needed, then match against site subnets."""
    ip = await resolve_to_ip(ip_or_hostname)
    if not ip:
        return None
    result = await db.execute(select(Site))
    sites = list(result.scalars().all())
    return match_site_for_ip(ip, sites)


async def get_default_site(db: AsyncSession) -> Site | None:
    """Return the site marked as default, or the one named 'default'."""
    result = await db.execute(
        select(Site).where(Site.is_default == True)  # noqa: E712
    )
    site = result.scalar_one_or_none()
    if site:
        return site
    result = await db.execute(select(Site).where(Site.name == "default"))
    return result.scalar_one_or_none()


async def auto_assign_site(
    ip_or_hostname: str, db: AsyncSession
) -> Site | None:
    """Resolve hostname to IP, match against site subnets, fall back to default."""
    site = await detect_site(ip_or_hostname, db)
    if site:
        return site
    return await get_default_site(db)


def validate_subnets(subnets: list[str]) -> list[str]:
    """Validate and normalize a list of CIDR strings. Raises ValueError."""
    validated = []
    for s in subnets:
        s = s.strip()
        if not s:
            continue
        try:
            net = ipaddress.ip_network(s, strict=False)
            validated.append(str(net))
        except ValueError:
            raise ValueError(f"Invalid CIDR notation: {s}")
    return validated
