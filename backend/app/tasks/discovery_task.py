from __future__ import annotations

import ipaddress
import logging
from datetime import datetime, timezone

import nmap

from app.database import SyncSession
from app.models.discovery import DiscoveryScan, DiscoveredHost
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

MANAGEMENT_PORTS = "22,80,443,3389,5985,5986,8006"

NMAP_FLAGS: dict[str, str] = {
    "quick": f"-sT -Pn -R -p {MANAGEMENT_PORTS} --host-timeout 10s -T4",
    "standard": f"-sT -Pn -R -p {MANAGEMENT_PORTS} -sV --version-light --host-timeout 30s -T3 --max-hostgroup 128 --max-parallelism 64",
    "deep": f"-sT -Pn -R -p {MANAGEMENT_PORTS} -sV -O --osscan-guess --host-timeout 45s -T3 --max-hostgroup 32 --max-parallelism 16 --max-retries 1",
}

CHUNK_PREFIX_LEN = 24


def _infer_os(
    nmap_os_match: str | None,
    os_accuracy: int,
    open_ports: list[dict],
    banners: dict[int, str],
) -> tuple[str, str | None, int]:
    """Return (os_type, os_guess, confidence) from layered signals."""

    port_numbers = {p["port"] for p in open_ports}

    if nmap_os_match and os_accuracy > 0:
        lower = nmap_os_match.lower()
        if "windows" in lower:
            return "windows", nmap_os_match, os_accuracy
        if "proxmox" in lower or "pve" in lower:
            return "proxmox", nmap_os_match, os_accuracy
        if "freenas" in lower or "truenas" in lower:
            return "truenas", nmap_os_match, os_accuracy
        if any(k in lower for k in ("linux", "ubuntu", "debian", "centos", "rhel", "fedora")):
            return "linux", nmap_os_match, os_accuracy

    ssh_banner = banners.get(22, "").lower()
    if ssh_banner:
        if "pve" in ssh_banner or "proxmox" in ssh_banner:
            return "proxmox", f"SSH banner: {banners[22]}", 80
        if "truenas" in ssh_banner or "freenas" in ssh_banner:
            return "truenas", f"SSH banner: {banners[22]}", 75

    for port in (443, 80):
        http_banner = banners.get(port, "").lower()
        if "truenas" in http_banner:
            return "truenas", f"HTTP banner: {banners[port]}", 75
        if "pve" in http_banner or "proxmox" in http_banner:
            return "proxmox", f"HTTP banner: {banners[port]}", 75

    pve_banner = banners.get(8006, "").lower()
    if pve_banner and ("pve" in pve_banner or "proxmox" in pve_banner):
        return "proxmox", f"PVE API: {banners[8006]}", 85

    if 5985 in port_numbers or 5986 in port_numbers or 3389 in port_numbers:
        return "windows", "WinRM/RDP port open", 60
    if 8006 in port_numbers:
        return "proxmox", "Port 8006 (Proxmox API) open", 55
    if 22 in port_numbers:
        return "linux", "SSH port open", 40

    return "unknown", None, 0


def _parse_host(nm: nmap.PortScanner, addr: str, depth: str) -> dict:
    """Extract structured data from a single nmap host result."""
    host_data = nm[addr] if addr in nm.all_hosts() else {}

    hostname = None
    hostnames = host_data.get("hostnames", [])
    for hn in hostnames:
        name = hn.get("name", "")
        if name and name != addr:
            hostname = name
            break

    open_ports: list[dict] = []
    banners: dict[int, str] = {}

    for proto in ("tcp", "udp"):
        port_data = host_data.get(proto, {})
        for port_num, port_info in port_data.items():
            if port_info.get("state") != "open":
                continue
            service = port_info.get("name", "")
            product = port_info.get("product", "")
            version = port_info.get("version", "")
            banner = " ".join(filter(None, [product, version])).strip()
            open_ports.append(
                {"port": int(port_num), "service": service, "banner": banner}
            )
            if banner:
                banners[int(port_num)] = banner

    nmap_os_match = None
    os_accuracy = 0
    os_matches = host_data.get("osmatch", [])
    if os_matches:
        best = os_matches[0]
        nmap_os_match = best.get("name")
        os_accuracy = int(best.get("accuracy", 0))

    os_type, os_guess, confidence = _infer_os(nmap_os_match, os_accuracy, open_ports, banners)

    return {
        "ip_address": addr,
        "hostname": hostname,
        "os_guess": os_guess,
        "os_type": os_type,
        "os_confidence": confidence,
        "open_ports": open_ports,
    }


def _split_into_chunks(target: str) -> list[str]:
    """Break a target string into /24-or-smaller chunks for safe scanning.

    Accepts space-separated CIDR blocks (as produced by the target normalizer).
    Any block larger than /24 is split; /24 and smaller pass through as-is.
    Single IPs and hostnames pass through unchanged.
    """
    chunks: list[str] = []
    for part in target.split():
        part = part.strip()
        if not part:
            continue
        try:
            net = ipaddress.ip_network(part, strict=False)
            if net.prefixlen < CHUNK_PREFIX_LEN:
                chunks.extend(
                    str(subnet)
                    for subnet in net.subnets(new_prefix=CHUNK_PREFIX_LEN)
                )
            else:
                chunks.append(str(net))
        except ValueError:
            chunks.append(part)
    return chunks


def _scan_chunk(nm: nmap.PortScanner, target: str, flags: str, scan_id: str, depth: str) -> tuple[list[dict], int]:
    """Run nmap on a single chunk, return (discovered, skipped)."""
    logger.info("discovery_scan %s: scanning chunk %s", scan_id, target)
    nm.scan(hosts=target, arguments=flags)

    discovered: list[dict] = []
    skipped = 0
    for addr in nm.all_hosts():
        if nm[addr].state() != "up":
            skipped += 1
            continue
        host_info = _parse_host(nm, addr, depth)
        if not host_info["open_ports"] and not host_info["hostname"]:
            skipped += 1
            continue
        logger.info("discovery_scan %s: found %s -> %s (%s, %d%%)",
                    scan_id, addr, host_info["os_type"],
                    host_info.get("hostname") or "no rDNS",
                    host_info["os_confidence"])
        discovered.append(host_info)

    return discovered, skipped


@celery_app.task(name="discovery_scan", bind=True)
def discovery_scan(self, scan_id: str):
    with SyncSession() as db:
        scan = db.get(DiscoveryScan, scan_id)
        if not scan:
            return {"error": "scan not found"}

        scan.status = "running"
        db.commit()

    try:
        flags = NMAP_FLAGS.get(scan.depth, NMAP_FLAGS["standard"])
        chunks = _split_into_chunks(scan.target)

        logger.info(
            "discovery_scan %s: target=%s depth=%s chunks=%d flags=%s",
            scan_id, scan.target, scan.depth, len(chunks), flags,
        )

        total_found = 0
        total_skipped = 0

        for i, chunk in enumerate(chunks):
            nm = nmap.PortScanner()
            logger.info(
                "discovery_scan %s: chunk %d/%d: %s",
                scan_id, i + 1, len(chunks), chunk,
            )

            chunk_discovered, chunk_skipped = _scan_chunk(nm, chunk, flags, scan_id, scan.depth)
            total_skipped += chunk_skipped

            if chunk_discovered:
                with SyncSession() as db:
                    for info in chunk_discovered:
                        db.add(DiscoveredHost(scan_id=scan_id, **info))
                    scan_obj = db.get(DiscoveryScan, scan_id)
                    if scan_obj:
                        scan_obj.host_count = (scan_obj.host_count or 0) + len(chunk_discovered)
                    db.commit()
                total_found += len(chunk_discovered)

            logger.info(
                "discovery_scan %s: chunk %d/%d done -- %d found, %d skipped",
                scan_id, i + 1, len(chunks), len(chunk_discovered), chunk_skipped,
            )
            del nm

        with SyncSession() as db:
            scan_obj = db.get(DiscoveryScan, scan_id)
            if scan_obj:
                scan_obj.status = "completed"
                scan_obj.host_count = total_found
                scan_obj.completed_at = datetime.now(timezone.utc)
                db.commit()

        logger.info(
            "discovery_scan %s: complete -- %d hosts found, %d skipped across %d chunks",
            scan_id, total_found, total_skipped, len(chunks),
        )
        return {"status": "completed", "hosts_found": total_found}

    except Exception as exc:
        logger.exception("discovery_scan %s failed: %s", scan_id, exc)
        with SyncSession() as db:
            scan = db.get(DiscoveryScan, scan_id)
            if scan:
                scan.status = "failed"
                scan.error = str(exc)[:1000]
                scan.completed_at = datetime.now(timezone.utc)
                db.commit()
        raise
