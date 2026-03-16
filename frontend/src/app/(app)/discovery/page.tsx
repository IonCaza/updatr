"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";
import { toast } from "sonner";

interface DiscoveredHost {
  id: string;
  ip_address: string;
  hostname: string | null;
  os_guess: string | null;
  os_type: string;
  os_confidence: number;
  open_ports: { port: number; service: string; banner: string }[];
  imported: boolean;
}

interface ScanResult {
  id: string;
  target: string;
  depth: string;
  status: string;
  host_count: number;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  hosts: DiscoveredHost[];
}

interface ScanSummary {
  id: string;
  target: string;
  depth: string;
  status: string;
  host_count: number;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

interface Credential {
  id: string;
  name: string;
  type: string;
}

type SortField = "ip" | "hostname" | "os" | "ports";
type SortDir = "asc" | "desc";
type GroupField = "none" | "os" | "subnet";

interface HostImportConfig {
  os_type: string;
  credential_id: string;
}

const DEPTH_OPTIONS = [
  {
    value: "quick",
    label: "Quick",
    time: "~10-20s",
    description: "Ping sweep + DNS reverse lookup. Finds live hosts only.",
  },
  {
    value: "standard",
    label: "Standard",
    time: "~30-60s",
    description: "Port scan of management ports + banner grab. Infers OS type.",
  },
  {
    value: "deep",
    label: "Deep",
    time: "~2-5min",
    description:
      "Full OS fingerprint via TCP/IP stack analysis. Most accurate.",
  },
];

const OS_COLORS: Record<string, string> = {
  windows: "bg-blue-100 text-blue-800",
  linux: "bg-green-100 text-green-800",
  proxmox: "bg-purple-100 text-purple-800",
  truenas: "bg-orange-100 text-orange-800",
  unknown: "bg-zinc-100 text-zinc-600",
};

const OS_LABELS: Record<string, string> = {
  windows: "Windows",
  linux: "Linux",
  proxmox: "Proxmox",
  truenas: "TrueNAS",
  unknown: "Unknown",
};

const OS_IMPORT_OPTIONS = [
  { value: "linux", label: "Linux" },
  { value: "windows", label: "Windows" },
  { value: "proxmox", label: "Proxmox" },
  { value: "truenas", label: "TrueNAS" },
];

function ipToNum(ip: string): number {
  return ip
    .split(".")
    .reduce((acc, octet) => acc * 256 + parseInt(octet, 10), 0);
}

function subnetKey(ip: string): string {
  return ip.split(".").slice(0, 3).join(".") + ".0/24";
}

function timeAgo(iso: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(iso).getTime()) / 1000
  );
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function DiscoveryPage() {
  const [target, setTarget] = useState("");
  const [depth, setDepth] = useState("standard");
  const [scanning, setScanning] = useState(false);
  const [currentScan, setCurrentScan] = useState<ScanResult | null>(null);
  const [pastScans, setPastScans] = useState<ScanSummary[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");

  const [sortBy, setSortBy] = useState<SortField>("ip");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [groupBy, setGroupBy] = useState<GroupField>("none");
  const [hideUnknown, setHideUnknown] = useState(true);

  const [importOpen, setImportOpen] = useState(false);
  const [creds, setCreds] = useState<Credential[]>([]);
  const [defaultCredId, setDefaultCredId] = useState("");
  const [importSite, setImportSite] = useState("default");
  const [importing, setImporting] = useState(false);
  const [importOverrides, setImportOverrides] = useState<
    Record<string, HostImportConfig>
  >({});

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadPastScans = useCallback(async () => {
    try {
      const scans = await apiFetch<ScanSummary[]>("/api/discovery/scans");
      setPastScans(scans);
    } catch {
      /* empty */
    }
  }, []);

  const loadCredentials = useCallback(async () => {
    try {
      const c = await apiFetch<Credential[]>("/api/credentials");
      setCreds(c);
    } catch {
      /* empty */
    }
  }, []);

  useEffect(() => {
    loadPastScans();
    loadCredentials();
  }, [loadPastScans, loadCredentials]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const pollScan = useCallback(
    (scanId: string) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const data = await apiFetch<ScanResult>(
            `/api/discovery/${scanId}`
          );
          setCurrentScan(data);
          if (data.status === "completed" || data.status === "failed") {
            stopPolling();
            setScanning(false);
            loadPastScans();
            if (data.status === "failed") {
              toast.error(`Scan failed: ${data.error || "Unknown error"}`);
            } else {
              toast.success(
                `Scan complete \u2014 found ${data.host_count} host${data.host_count !== 1 ? "s" : ""}`
              );
            }
          }
        } catch {
          stopPolling();
          setScanning(false);
        }
      }, 2000);
    },
    [stopPolling, loadPastScans]
  );

  const startScan = async () => {
    if (!target.trim()) {
      toast.error("Enter a target subnet or IP range");
      return;
    }
    setScanning(true);
    setCurrentScan(null);
    setSelected(new Set());
    try {
      const res = await apiFetch<{ scan_id: string }>(
        "/api/discovery/scan",
        {
          method: "POST",
          body: JSON.stringify({ target: target.trim(), depth }),
        }
      );
      setCurrentScan({
        id: res.scan_id,
        target: target.trim(),
        depth,
        status: "pending",
        host_count: 0,
        error: null,
        started_at: new Date().toISOString(),
        completed_at: null,
        hosts: [],
      });
      pollScan(res.scan_id);
    } catch (e: unknown) {
      setScanning(false);
      toast.error(e instanceof Error ? e.message : "Failed to start scan");
    }
  };

  const loadScanResult = async (scanId: string) => {
    try {
      const data = await apiFetch<ScanResult>(`/api/discovery/${scanId}`);
      setCurrentScan(data);
      setSelected(new Set());
      setSearch("");
    } catch {
      toast.error("Failed to load scan results");
    }
  };

  // --- Processed host list with filtering, sorting, grouping ---

  const processedHosts = useMemo(() => {
    if (!currentScan) return [];
    let hosts = [...currentScan.hosts];

    if (hideUnknown) {
      hosts = hosts.filter((h) => h.os_type !== "unknown");
    }

    if (search) {
      const q = search.toLowerCase();
      hosts = hosts.filter(
        (h) =>
          h.ip_address.includes(q) ||
          (h.hostname || "").toLowerCase().includes(q) ||
          (h.os_guess || "").toLowerCase().includes(q) ||
          h.os_type.toLowerCase().includes(q) ||
          h.open_ports.some(
            (p) =>
              String(p.port).includes(q) ||
              (p.service || "").toLowerCase().includes(q)
          )
      );
    }

    hosts.sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case "ip":
          cmp = ipToNum(a.ip_address) - ipToNum(b.ip_address);
          break;
        case "hostname":
          cmp = (a.hostname || "\uffff").localeCompare(
            b.hostname || "\uffff"
          );
          break;
        case "os":
          cmp = a.os_type.localeCompare(b.os_type);
          break;
        case "ports":
          cmp = a.open_ports.length - b.open_ports.length;
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    return hosts;
  }, [currentScan, search, hideUnknown, sortBy, sortDir]);

  const groupedHosts = useMemo(() => {
    if (groupBy === "none") {
      return [{ key: "", hosts: processedHosts }];
    }

    const groups: Record<string, DiscoveredHost[]> = {};
    for (const h of processedHosts) {
      const key =
        groupBy === "os"
          ? OS_LABELS[h.os_type] || h.os_type
          : subnetKey(h.ip_address);
      if (!groups[key]) groups[key] = [];
      groups[key].push(h);
    }

    return Object.entries(groups)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, hosts]) => ({ key, hosts }));
  }, [processedHosts, groupBy]);

  const hiddenCount = useMemo(() => {
    if (!currentScan || !hideUnknown) return 0;
    return currentScan.hosts.filter((h) => h.os_type === "unknown").length;
  }, [currentScan, hideUnknown]);

  // --- Selection ---

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    const importable = processedHosts.filter((h) => !h.imported);
    if (selected.size === importable.length && importable.length > 0) {
      setSelected(new Set());
    } else {
      setSelected(new Set(importable.map((h) => h.id)));
    }
  };

  // --- Import modal ---

  const openImportModal = () => {
    if (!currentScan) return;
    const configs: Record<string, HostImportConfig> = {};
    for (const h of currentScan.hosts) {
      if (selected.has(h.id)) {
        configs[h.id] = {
          os_type: h.os_type !== "unknown" ? h.os_type : "linux",
          credential_id: "",
        };
      }
    }
    setImportOverrides(configs);
    setImportOpen(true);
  };

  const setOverride = (
    hostId: string,
    field: keyof HostImportConfig,
    value: string
  ) => {
    setImportOverrides((prev) => ({
      ...prev,
      [hostId]: { ...prev[hostId], [field]: value },
    }));
  };

  const selectedHostsForImport = useMemo(() => {
    if (!currentScan) return [];
    return currentScan.hosts.filter((h) => selected.has(h.id));
  }, [currentScan, selected]);

  const doImport = async () => {
    if (!defaultCredId) {
      toast.error("Select a default credential");
      return;
    }
    setImporting(true);
    try {
      const hosts = Array.from(selected).map((id) => ({
        host_id: id,
        os_type: importOverrides[id]?.os_type || null,
        credential_id: importOverrides[id]?.credential_id || null,
      }));
      const res = await apiFetch<{ imported: number; skipped: number }>(
        "/api/discovery/import",
        {
          method: "POST",
          body: JSON.stringify({
            hosts,
            default_credential_id: defaultCredId,
            site: importSite || "default",
          }),
        }
      );
      toast.success(
        `Imported ${res.imported} host${res.imported !== 1 ? "s" : ""}` +
          (res.skipped ? `, ${res.skipped} skipped (already exist)` : "")
      );
      setImportOpen(false);
      setSelected(new Set());
      if (currentScan) {
        await loadScanResult(currentScan.id);
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  const depthInfo = DEPTH_OPTIONS.find((d) => d.value === depth);
  const isCompleted = currentScan?.status === "completed";
  const hasHosts = isCompleted && processedHosts.length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Discovery</h1>
        <p className="text-muted-foreground mt-1">
          Scan your network to find and import hosts
        </p>
      </div>

      {/* Scan controls */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-4">
            <div className="flex gap-3">
              <Input
                placeholder="192.168.1.0/24 or 10.0.0.1-10.0.0.50"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                className="flex-1"
                disabled={scanning}
              />
              <Button
                onClick={startScan}
                disabled={scanning || !target.trim()}
              >
                {scanning ? "Scanning..." : "Scan"}
              </Button>
            </div>

            <div className="flex gap-2">
              {DEPTH_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => !scanning && setDepth(opt.value)}
                  disabled={scanning}
                  className={`flex-1 rounded-md border px-3 py-2 text-left transition-colors ${
                    depth === opt.value
                      ? "border-primary bg-primary/5"
                      : "hover:bg-muted/50"
                  } ${scanning ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{opt.label}</span>
                    <Badge variant="outline" className="text-[10px]">
                      {opt.time}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {opt.description}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Active scan / results */}
      {currentScan && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                {currentScan.status === "running" ||
                currentScan.status === "pending" ? (
                  <>
                    <span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-500 animate-pulse" />
                    Scanning {currentScan.target}...
                  </>
                ) : currentScan.status === "failed" ? (
                  <>
                    <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" />
                    Scan Failed
                  </>
                ) : (
                  <>
                    <span className="inline-block h-2.5 w-2.5 rounded-full bg-green-500" />
                    {currentScan.host_count} host
                    {currentScan.host_count !== 1 ? "s" : ""} found
                    {hiddenCount > 0 && (
                      <span className="text-xs font-normal text-muted-foreground ml-1">
                        ({hiddenCount} unidentified hidden)
                      </span>
                    )}
                  </>
                )}
                <Badge variant="outline" className="text-[10px] ml-1">
                  {currentScan.depth}
                </Badge>
              </CardTitle>
              {hasHosts && (
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={selectAll}
                    disabled={
                      processedHosts.filter((h) => !h.imported).length === 0
                    }
                  >
                    {selected.size ===
                      processedHosts.filter((h) => !h.imported).length &&
                    processedHosts.filter((h) => !h.imported).length > 0
                      ? "Deselect All"
                      : "Select All"}
                  </Button>
                  <Button
                    size="sm"
                    disabled={selected.size === 0}
                    onClick={openImportModal}
                  >
                    Import {selected.size > 0 ? `(${selected.size})` : ""}
                  </Button>
                </div>
              )}
            </div>

            {/* Toolbar: search + sort/group/filter */}
            {isCompleted && currentScan.hosts.length > 0 && (
              <div className="mt-2 space-y-2">
                <Input
                  placeholder="Filter by IP, hostname, OS, port..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="h-8 text-sm"
                />
                <div className="flex items-center gap-3 flex-wrap">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] text-muted-foreground">
                      Sort
                    </span>
                    <Select
                      value={sortBy}
                      onValueChange={(v) => setSortBy(v as SortField)}
                    >
                      <SelectTrigger className="h-7 w-[120px] text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ip">IP Address</SelectItem>
                        <SelectItem value="hostname">Hostname</SelectItem>
                        <SelectItem value="os">OS Type</SelectItem>
                        <SelectItem value="ports">Open Ports</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 w-7 p-0 text-xs"
                      onClick={() =>
                        setSortDir((d) => (d === "asc" ? "desc" : "asc"))
                      }
                    >
                      {sortDir === "asc" ? "\u2191" : "\u2193"}
                    </Button>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] text-muted-foreground">
                      Group
                    </span>
                    <Select
                      value={groupBy}
                      onValueChange={(v) => setGroupBy(v as GroupField)}
                    >
                      <SelectTrigger className="h-7 w-[110px] text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">None</SelectItem>
                        <SelectItem value="os">OS Type</SelectItem>
                        <SelectItem value="subnet">Subnet</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <button
                    onClick={() => setHideUnknown(!hideUnknown)}
                    className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <div
                      className={`h-3.5 w-3.5 rounded border-2 flex items-center justify-center transition-colors ${
                        hideUnknown
                          ? "bg-primary border-primary"
                          : "border-muted-foreground/40"
                      }`}
                    >
                      {hideUnknown && (
                        <svg
                          viewBox="0 0 12 12"
                          className="h-2.5 w-2.5 text-primary-foreground"
                        >
                          <path
                            d="M2.5 6l2.5 2.5 4.5-5"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                    </div>
                    Hide unidentified
                  </button>
                </div>
              </div>
            )}
          </CardHeader>
          <CardContent>
            {(currentScan.status === "running" ||
              currentScan.status === "pending") && (
              <div className="py-8 text-center">
                <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                <p className="text-sm text-muted-foreground mt-3">
                  Running {depthInfo?.label.toLowerCase()} scan on{" "}
                  {currentScan.target}...
                </p>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Estimated time: {depthInfo?.time} per /24
                </p>
              </div>
            )}

            {currentScan.status === "failed" && (
              <p className="text-sm text-red-600 py-4">
                {currentScan.error || "An unknown error occurred."}
              </p>
            )}

            {isCompleted && (
              <>
                {processedHosts.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-4 text-center">
                    {currentScan.hosts.length === 0
                      ? "No hosts found on the target network."
                      : search
                        ? "No results match your filter."
                        : "All discovered hosts are hidden by current filters."}
                  </p>
                ) : (
                  <div className="space-y-1">
                    {groupedHosts.map((group) => (
                      <div key={group.key || "__all"}>
                        {group.key && (
                          <div className="flex items-center gap-2 px-1 pt-3 pb-1">
                            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                              {group.key}
                            </span>
                            <Badge
                              variant="outline"
                              className="text-[9px] px-1 py-0"
                            >
                              {group.hosts.length}
                            </Badge>
                          </div>
                        )}
                        <div className="space-y-1">
                          {group.hosts.map((h) => (
                            <HostRow
                              key={h.id}
                              host={h}
                              isSelected={selected.has(h.id)}
                              onToggle={() =>
                                !h.imported && toggleSelect(h.id)
                              }
                            />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Import dialog */}
      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              Import {selected.size} Host
              {selected.size !== 1 ? "s" : ""}
            </DialogTitle>
            <DialogDescription>
              Set default credential and site, then optionally override OS or
              credential per host.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            {/* Defaults row */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Default Credential
                </label>
                <Select
                  value={defaultCredId}
                  onValueChange={setDefaultCredId}
                >
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select credential..." />
                  </SelectTrigger>
                  <SelectContent>
                    {creds.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Site
                </label>
                <Input
                  value={importSite}
                  onChange={(e) => setImportSite(e.target.value)}
                  placeholder="default"
                  className="mt-1"
                />
              </div>
            </div>

            {/* Per-host overrides */}
            {selectedHostsForImport.length > 0 && (
              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Per-Host Settings
                </label>
                <div className="mt-1 border rounded-md max-h-[320px] overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-muted/80 backdrop-blur-sm">
                      <tr className="text-[11px] text-muted-foreground">
                        <th className="text-left px-3 py-1.5 font-medium">
                          Host
                        </th>
                        <th className="text-left px-3 py-1.5 font-medium">
                          Detected
                        </th>
                        <th className="text-left px-3 py-1.5 font-medium">
                          OS Override
                        </th>
                        <th className="text-left px-3 py-1.5 font-medium">
                          Credential
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedHostsForImport.map((h) => {
                        const cfg = importOverrides[h.id];
                        return (
                          <tr key={h.id} className="border-t">
                            <td className="px-3 py-2">
                              <div className="font-mono text-xs">
                                {h.ip_address}
                              </div>
                              {h.hostname && (
                                <div className="text-[10px] text-muted-foreground truncate max-w-[160px]">
                                  {h.hostname}
                                </div>
                              )}
                            </td>
                            <td className="px-3 py-2">
                              <Badge
                                className={`text-[10px] ${OS_COLORS[h.os_type] || OS_COLORS.unknown}`}
                              >
                                {OS_LABELS[h.os_type] || h.os_type}
                                {h.os_confidence > 0 && (
                                  <span className="ml-1 opacity-70">
                                    {h.os_confidence}%
                                  </span>
                                )}
                              </Badge>
                            </td>
                            <td className="px-3 py-2">
                              <select
                                className="h-7 w-full rounded-md border bg-background px-2 text-xs"
                                value={cfg?.os_type || "linux"}
                                onChange={(e) =>
                                  setOverride(
                                    h.id,
                                    "os_type",
                                    e.target.value
                                  )
                                }
                              >
                                {OS_IMPORT_OPTIONS.map((o) => (
                                  <option key={o.value} value={o.value}>
                                    {o.label}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="px-3 py-2">
                              <select
                                className="h-7 w-full rounded-md border bg-background px-2 text-xs"
                                value={cfg?.credential_id || ""}
                                onChange={(e) =>
                                  setOverride(
                                    h.id,
                                    "credential_id",
                                    e.target.value
                                  )
                                }
                              >
                                <option value="">Use default</option>
                                {creds.map((c) => (
                                  <option key={c.id} value={c.id}>
                                    {c.name}
                                  </option>
                                ))}
                              </select>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setImportOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={doImport}
                disabled={importing || !defaultCredId}
              >
                {importing ? "Importing..." : "Import"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Past scans */}
      {pastScans.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Scan History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5">
              {pastScans.map((s) => (
                <div
                  key={s.id}
                  onClick={() => loadScanResult(s.id)}
                  className="flex items-center justify-between rounded-md border px-3 py-2 cursor-pointer hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className={`inline-block h-2 w-2 rounded-full shrink-0 ${
                        s.status === "completed"
                          ? "bg-green-500"
                          : s.status === "failed"
                            ? "bg-red-500"
                            : "bg-blue-500 animate-pulse"
                      }`}
                    />
                    <span className="text-sm font-mono">{s.target}</span>
                    <Badge variant="outline" className="text-[10px]">
                      {s.depth}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-3">
                    {s.status === "completed" && (
                      <span className="text-xs text-muted-foreground">
                        {s.host_count} host{s.host_count !== 1 ? "s" : ""}
                      </span>
                    )}
                    {s.status === "failed" && (
                      <span className="text-xs text-red-500">failed</span>
                    )}
                    {s.started_at && (
                      <span className="text-[10px] text-muted-foreground">
                        {timeAgo(s.started_at)}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function HostRow({
  host: h,
  isSelected,
  onToggle,
}: {
  host: DiscoveredHost;
  isSelected: boolean;
  onToggle: () => void;
}) {
  const osColor = OS_COLORS[h.os_type] || OS_COLORS.unknown;

  return (
    <div
      onClick={onToggle}
      className={`rounded-md border px-3 py-2 transition-colors ${
        h.imported ? "opacity-60" : "cursor-pointer hover:bg-muted/50"
      } ${isSelected ? "border-primary bg-primary/5" : ""}`}
    >
      <div className="flex items-center gap-3">
        {/* Checkbox */}
        <div className="shrink-0 w-5 flex justify-center">
          {h.imported ? (
            <span className="text-green-600 text-sm">&#10003;</span>
          ) : (
            <div
              className={`h-4 w-4 rounded border-2 flex items-center justify-center transition-colors ${
                isSelected
                  ? "bg-primary border-primary"
                  : "border-muted-foreground/40"
              }`}
            >
              {isSelected && (
                <svg
                  viewBox="0 0 12 12"
                  className="h-full w-full text-primary-foreground"
                >
                  <path
                    d="M2.5 6l2.5 2.5 4.5-5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </div>
          )}
        </div>

        {/* Host info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-mono font-medium">
              {h.ip_address}
            </span>
            {h.hostname && (
              <span className="text-xs text-muted-foreground truncate">
                {h.hostname}
              </span>
            )}
          </div>
          {h.os_guess && (
            <p className="text-[10px] text-muted-foreground truncate mt-0.5">
              {h.os_guess}
            </p>
          )}
        </div>

        {/* OS badge */}
        <div className="shrink-0">
          <Badge className={`text-[10px] ${osColor}`}>
            {OS_LABELS[h.os_type] || h.os_type}
            {h.os_confidence > 0 && (
              <span className="ml-1 opacity-70">{h.os_confidence}%</span>
            )}
          </Badge>
        </div>
      </div>

      {/* Port badges - second row */}
      {h.open_ports.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5 ml-8">
          {h.open_ports.map((p) => (
            <Tooltip key={p.port}>
              <TooltipTrigger asChild>
                <span>
                  <Badge
                    variant="outline"
                    className="text-[9px] px-1.5 py-0 cursor-help font-mono"
                  >
                    {p.port}
                    {p.service ? `/${p.service}` : ""}
                  </Badge>
                </span>
              </TooltipTrigger>
              <TooltipContent side="top">
                <div className="space-y-0.5">
                  <p className="font-medium">
                    Port {p.port} &mdash; {p.service || "unknown service"}
                  </p>
                  {p.banner && (
                    <p className="opacity-80 max-w-[250px] break-words">
                      {p.banner}
                    </p>
                  )}
                </div>
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
      )}
    </div>
  );
}
