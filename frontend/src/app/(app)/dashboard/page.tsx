"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";

interface ActivityEntry {
  id: string;
  type: "job" | "scan" | "schedule";
  title: string;
  detail: string;
  status: "completed" | "failed" | "running" | "triggered";
  timestamp: string;
  link: string | null;
  scan_at?: string;
  queues?: string | null;
}

interface ScanLogEntry {
  task: string;
  status: string;
  output: { stdout?: string; stderr?: string; msg?: string };
}

interface ScanDetailHost {
  host_id: string;
  display_name: string;
  hostname: string;
  os_type: string;
  status: "compliant" | "non_compliant" | "reboot_required" | "unreachable";
  pending_update_count: number;
  reboot_required: boolean;
  worker_queue: string | null;
  raw_log?: ScanLogEntry[];
}

interface ComplianceSummary {
  total_hosts: number;
  compliant: number;
  non_compliant: number;
  reboot_required: number;
  unreachable: number;
  last_scan_at: string | null;
}

interface HostEntry {
  host_id: string;
  display_name: string;
  hostname: string;
  os_type: string;
  pending_update_count: number;
  scanned_at: string | null;
}

interface WorkerHost {
  id: string;
  display_name: string;
  hostname: string;
  os_type: string;
  site: string;
  worker_override: string | null;
}

interface SiteInfo {
  id: string;
  name: string;
  display_name: string;
  host_count: number;
}

type StatusKey = "compliant" | "non_compliant" | "reboot_required" | "unreachable";

const STATUS_META: Record<StatusKey, { label: string; color: string; badge: string; description: string }> = {
  compliant: {
    label: "Compliant",
    color: "text-green-600",
    badge: "default",
    description: "Fully patched, no pending updates.",
  },
  non_compliant: {
    label: "Non-Compliant",
    color: "text-yellow-600",
    badge: "secondary",
    description: "Pending updates available.",
  },
  reboot_required: {
    label: "Reboot Required",
    color: "text-orange-600",
    badge: "secondary",
    description: "Up to date but a system reboot is pending.",
  },
  unreachable: {
    label: "Unreachable",
    color: "text-red-600",
    badge: "destructive",
    description: "Could not connect during the last scan.",
  },
};

interface WorkerInfo {
  name: string;
  friendly_name: string | null;
  status: string;
  queues: string[];
  active_tasks: number;
  uptime_seconds: number | null;
  total_tasks: number;
}

export default function DashboardPage() {
  const [data, setData] = useState<ComplianceSummary | null>(null);
  const [scanning, setScanning] = useState(false);
  const [detailKey, setDetailKey] = useState<StatusKey | null>(null);
  const [detailHosts, setDetailHosts] = useState<Record<StatusKey, HostEntry[]> | null>(null);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [workers, setWorkers] = useState<WorkerInfo[]>([]);

  const [selectedWorker, setSelectedWorker] = useState<WorkerInfo | null>(null);
  const [workerHosts, setWorkerHosts] = useState<WorkerHost[]>([]);
  const [workerHostsLoading, setWorkerHostsLoading] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [renaming, setRenaming] = useState(false);

  const [scanModalOpen, setScanModalOpen] = useState(false);
  const [scanSites, setScanSites] = useState<SiteInfo[]>([]);
  const [selectedSites, setSelectedSites] = useState<Set<string>>(new Set());
  const [scanSitesLoading, setScanSitesLoading] = useState(false);

  const [scanDetailOpen, setScanDetailOpen] = useState(false);
  const [scanDetailTime, setScanDetailTime] = useState<string | null>(null);
  const [scanDetailHosts, setScanDetailHosts] = useState<ScanDetailHost[]>([]);
  const [scanDetailQueues, setScanDetailQueues] = useState<string[]>([]);
  const [scanDetailLoading, setScanDetailLoading] = useState(false);
  const [expandedScanHosts, setExpandedScanHosts] = useState<Set<string>>(new Set());

  const router = useRouter();

  const load = useCallback(async () => {
    try {
      const summary = await apiFetch<ComplianceSummary>("/api/compliance/summary");
      setData(summary);
    } catch {
      /* no data yet */
    }
  }, []);

  const loadActivity = useCallback(async () => {
    try {
      const entries = await apiFetch<ActivityEntry[]>("/api/activity?limit=15");
      setActivity(entries);
    } catch {
      /* no activity yet */
    }
  }, []);

  const loadWorkers = useCallback(async () => {
    try {
      const w = await apiFetch<WorkerInfo[]>("/api/workers");
      setWorkers(w);
    } catch {
      setWorkers([]);
    }
  }, []);

  useEffect(() => {
    load();
    loadActivity();
    loadWorkers();
  }, [load, loadActivity, loadWorkers]);

  const openScanModal = async () => {
    setScanModalOpen(true);
    setScanSitesLoading(true);
    try {
      const sites = await apiFetch<SiteInfo[]>("/api/sites");
      setScanSites(sites.filter((s) => s.host_count > 0));
      setSelectedSites(new Set(sites.filter((s) => s.host_count > 0).map((s) => s.id)));
    } catch {
      toast.error("Failed to load sites");
      setScanSites([]);
    } finally {
      setScanSitesLoading(false);
    }
  };

  const triggerScan = async () => {
    setScanning(true);
    setScanModalOpen(false);
    try {
      const body: Record<string, unknown> = {};
      if (selectedSites.size > 0 && selectedSites.size < scanSites.length) {
        body.site_ids = [...selectedSites];
      }
      await apiFetch("/api/compliance/scan", {
        method: "POST",
        body: JSON.stringify(body),
      });
      const totalHosts = scanSites
        .filter((s) => selectedSites.has(s.id))
        .reduce((sum, s) => sum + s.host_count, 0);
      toast.success(
        `Scan triggered for ${totalHosts} host(s) across ${selectedSites.size} site(s)`
      );
      const poll = setInterval(async () => {
        await load();
        await loadActivity();
      }, 5000);
      setTimeout(() => {
        clearInterval(poll);
        setScanning(false);
      }, 60000);
    } catch {
      toast.error("Failed to trigger scan");
      setScanning(false);
    }
  };

  const openDetail = async (key: StatusKey) => {
    if (data && data[key] === 0) return;
    try {
      const groups = await apiFetch<Record<StatusKey, HostEntry[]>>("/api/compliance/hosts-by-status");
      setDetailHosts(groups);
      setDetailKey(key);
    } catch {
      toast.error("Failed to load details");
    }
  };

  const openScanDetail = async (scanAt: string) => {
    setScanDetailTime(scanAt);
    setScanDetailOpen(true);
    setScanDetailLoading(true);
    setExpandedScanHosts(new Set());
    try {
      const data = await apiFetch<{ scanned_at: string; queues: string[]; hosts: ScanDetailHost[] }>(
        `/api/compliance/scan-details?at=${encodeURIComponent(scanAt)}`
      );
      setScanDetailHosts(data.hosts);
      setScanDetailQueues(data.queues || []);
    } catch {
      toast.error("Failed to load scan details");
      setScanDetailHosts([]);
      setScanDetailQueues([]);
    } finally {
      setScanDetailLoading(false);
    }
  };

  const openWorkerDetail = async (w: WorkerInfo) => {
    setSelectedWorker(w);
    setRenameValue(w.friendly_name || "");
    setWorkerHostsLoading(true);
    try {
      const hosts = await apiFetch<WorkerHost[]>(
        `/api/workers/${encodeURIComponent(w.name)}/hosts`
      );
      setWorkerHosts(hosts);
    } catch {
      setWorkerHosts([]);
    } finally {
      setWorkerHostsLoading(false);
    }
  };

  const saveRename = async () => {
    if (!selectedWorker || !renameValue.trim()) return;
    setRenaming(true);
    try {
      await apiFetch(
        `/api/workers/${encodeURIComponent(selectedWorker.name)}/rename`,
        { method: "PUT", body: JSON.stringify({ friendly_name: renameValue.trim() }) }
      );
      setWorkers((prev) =>
        prev.map((w) =>
          w.name === selectedWorker.name
            ? { ...w, friendly_name: renameValue.trim() }
            : w
        )
      );
      setSelectedWorker((prev) =>
        prev ? { ...prev, friendly_name: renameValue.trim() } : prev
      );
      toast.success("Worker renamed");
    } catch {
      toast.error("Failed to rename worker");
    } finally {
      setRenaming(false);
    }
  };

  const stats: { label: string; value: number; color: string; key: StatusKey | null }[] = data
    ? [
        { label: "Total Hosts", value: data.total_hosts, color: "text-foreground", key: null },
        { label: "Compliant", value: data.compliant, color: "text-green-600", key: "compliant" },
        { label: "Non-Compliant", value: data.non_compliant, color: "text-yellow-600", key: "non_compliant" },
        { label: "Reboot Required", value: data.reboot_required, color: "text-orange-600", key: "reboot_required" },
        { label: "Unreachable", value: data.unreachable, color: "text-red-600", key: "unreachable" },
      ]
    : [];

  const activeHosts = detailKey && detailHosts ? detailHosts[detailKey] : [];
  const activeMeta = detailKey ? STATUS_META[detailKey] : null;

  const workerDisplayName = (w: WorkerInfo) => w.friendly_name || w.name;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground mt-1">Patch compliance overview</p>
        </div>
        <Button onClick={openScanModal} disabled={scanning}>
          {scanning ? "Scanning..." : "Scan Now"}
        </Button>
      </div>

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {stats.map((s) => (
              <Card
                key={s.label}
                className={
                  s.key
                    ? s.value > 0
                      ? "cursor-pointer hover:border-primary/50 transition-colors"
                      : ""
                    : s.value > 0
                    ? "cursor-pointer hover:border-primary/50 transition-colors"
                    : ""
                }
                onClick={() =>
                  s.key
                    ? openDetail(s.key)
                    : s.value > 0 && router.push("/hosts")
                }
              >
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {s.label}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className={`text-3xl font-bold ${s.color}`}>{s.value}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          {data.last_scan_at && (
            <p className="text-sm text-muted-foreground">
              Last scan: {new Date(data.last_scan_at).toLocaleString()}
            </p>
          )}
        </>
      ) : (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No compliance data yet. Add hosts and run a scan to see results.
          </CardContent>
        </Card>
      )}

      {/* Workers */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Workers</CardTitle>
        </CardHeader>
        <CardContent>
          {workers.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-2">
              No workers connected.
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {workers.map((w) => (
                <div
                  key={w.name}
                  className="flex items-start gap-3 rounded-md border px-3 py-2 cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => openWorkerDetail(w)}
                >
                  <span className="mt-1.5 inline-block h-2.5 w-2.5 rounded-full bg-green-500 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">
                      {workerDisplayName(w)}
                    </p>
                    {w.friendly_name && (
                      <p className="text-[10px] text-muted-foreground truncate">
                        {w.name}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {w.queues.join(", ")} &middot; {w.active_tasks} active
                      {w.uptime_seconds != null && (
                        <> &middot; up {formatUptime(w.uptime_seconds)}</>
                      )}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Scan scope modal */}
      <Dialog open={scanModalOpen} onOpenChange={setScanModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Run Compliance Scan</DialogTitle>
            <DialogDescription>
              Select which sites to include in the scan.
            </DialogDescription>
          </DialogHeader>
          {scanSitesLoading ? (
            <p className="text-sm text-muted-foreground py-4 text-center">Loading sites...</p>
          ) : scanSites.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No sites with active hosts found.
            </p>
          ) : (
            <>
              <label className="flex items-center gap-2 px-2 py-1 text-sm font-medium border-b">
                <input
                  type="checkbox"
                  checked={selectedSites.size === scanSites.length}
                  onChange={() => {
                    if (selectedSites.size === scanSites.length) {
                      setSelectedSites(new Set());
                    } else {
                      setSelectedSites(new Set(scanSites.map((s) => s.id)));
                    }
                  }}
                  className="rounded"
                />
                <span>All sites</span>
                <span className="text-muted-foreground text-xs ml-auto">
                  {scanSites.reduce((sum, s) => sum + s.host_count, 0)} hosts total
                </span>
              </label>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {scanSites.map((site) => (
                  <label
                    key={site.id}
                    className="flex items-center gap-2 px-2 py-2 rounded hover:bg-muted cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedSites.has(site.id)}
                      onChange={() => {
                        setSelectedSites((prev) => {
                          const next = new Set(prev);
                          if (next.has(site.id)) next.delete(site.id);
                          else next.add(site.id);
                          return next;
                        });
                      }}
                      className="rounded"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">{site.display_name}</p>
                      <p className="text-[10px] text-muted-foreground">{site.name}</p>
                    </div>
                    <Badge variant="outline" className="text-xs shrink-0">
                      {site.host_count} host{site.host_count !== 1 ? "s" : ""}
                    </Badge>
                  </label>
                ))}
              </div>
              <div className="flex items-center justify-between pt-2 border-t">
                <p className="text-sm text-muted-foreground">
                  {selectedSites.size} of {scanSites.length} site(s) selected
                  {" \u00B7 "}
                  {scanSites
                    .filter((s) => selectedSites.has(s.id))
                    .reduce((sum, s) => sum + s.host_count, 0)}{" "}
                  host(s)
                </p>
                <Button
                  onClick={triggerScan}
                  disabled={selectedSites.size === 0}
                  size="sm"
                >
                  Run Scan
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Compliance detail modal */}
      <Dialog open={detailKey !== null} onOpenChange={(open) => !open && setDetailKey(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {activeMeta?.label}
              <Badge variant="secondary">{activeHosts.length}</Badge>
            </DialogTitle>
            <DialogDescription>{activeMeta?.description}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2 mt-2">
            {activeHosts.length === 0 ? (
              <p className="text-sm text-muted-foreground">No hosts in this category.</p>
            ) : (
              activeHosts.map((h) => (
                <div
                  key={h.host_id}
                  className="flex items-center justify-between rounded-md border px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="font-medium text-sm truncate">{h.display_name}</p>
                    <p className="text-xs text-muted-foreground truncate">{h.hostname}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-3">
                    <Badge variant="outline" className="text-xs">
                      {h.os_type}
                    </Badge>
                    {h.pending_update_count > 0 && (
                      <Badge variant="secondary" className="text-xs">
                        {h.pending_update_count} update{h.pending_update_count !== 1 ? "s" : ""}
                      </Badge>
                    )}
                    {h.scanned_at && (
                      <span className="text-[10px] text-muted-foreground">
                        {new Date(h.scanned_at).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Worker detail modal */}
      <Dialog
        open={selectedWorker !== null}
        onOpenChange={(open) => !open && setSelectedWorker(null)}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
          {selectedWorker && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <span className="inline-block h-2.5 w-2.5 rounded-full bg-green-500 shrink-0" />
                  {workerDisplayName(selectedWorker)}
                </DialogTitle>
                <DialogDescription className="truncate">
                  {selectedWorker.name}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 mt-2">
                {/* Rename */}
                <div>
                  <label className="text-xs font-medium text-muted-foreground">
                    Friendly Name
                  </label>
                  <div className="flex gap-2 mt-1">
                    <Input
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      placeholder="e.g. Site-A Primary"
                      className="h-8 text-sm"
                    />
                    <Button
                      size="sm"
                      onClick={saveRename}
                      disabled={
                        renaming ||
                        !renameValue.trim() ||
                        renameValue.trim() === (selectedWorker.friendly_name || "")
                      }
                    >
                      {renaming ? "Saving..." : "Save"}
                    </Button>
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="rounded-md border px-3 py-2 text-center">
                    <p className="text-lg font-bold">{selectedWorker.active_tasks}</p>
                    <p className="text-[10px] text-muted-foreground">Active Tasks</p>
                  </div>
                  <div className="rounded-md border px-3 py-2 text-center">
                    <p className="text-lg font-bold">{selectedWorker.total_tasks}</p>
                    <p className="text-[10px] text-muted-foreground">Total Processed</p>
                  </div>
                  <div className="rounded-md border px-3 py-2 text-center">
                    <p className="text-lg font-bold">
                      {selectedWorker.uptime_seconds != null
                        ? formatUptime(selectedWorker.uptime_seconds)
                        : "—"}
                    </p>
                    <p className="text-[10px] text-muted-foreground">Uptime</p>
                  </div>
                </div>

                {/* Queues */}
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Queues</p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedWorker.queues.map((q) => (
                      <Badge key={q} variant="outline" className="text-xs">
                        {q}
                      </Badge>
                    ))}
                    {selectedWorker.queues.length === 0 && (
                      <span className="text-xs text-muted-foreground">None</span>
                    )}
                  </div>
                </div>

                {/* Assigned hosts */}
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">
                    Assigned Hosts
                    {!workerHostsLoading && (
                      <span className="ml-1 text-muted-foreground">({workerHosts.length})</span>
                    )}
                  </p>
                  {workerHostsLoading ? (
                    <p className="text-xs text-muted-foreground py-2">Loading...</p>
                  ) : workerHosts.length === 0 ? (
                    <p className="text-xs text-muted-foreground py-2">
                      No hosts routed to this worker.
                    </p>
                  ) : (
                    <div className="space-y-1.5 max-h-48 overflow-y-auto">
                      {workerHosts.map((h) => (
                        <div
                          key={h.id}
                          className="flex items-center justify-between rounded-md border px-3 py-1.5"
                        >
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">{h.display_name}</p>
                            <p className="text-[10px] text-muted-foreground truncate">
                              {h.hostname}
                            </p>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0 ml-2">
                            <Badge variant="outline" className="text-[10px]">
                              {h.os_type}
                            </Badge>
                            {h.worker_override && (
                              <Badge variant="secondary" className="text-[10px]">
                                override
                              </Badge>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Scan detail modal */}
      <Dialog open={scanDetailOpen} onOpenChange={(open) => !open && setScanDetailOpen(false)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              Scan Results
              {scanDetailQueues.length > 0 && scanDetailQueues.map((q) => (
                <Badge key={q} variant="secondary" className="text-[10px]">
                  {q}
                </Badge>
              ))}
            </DialogTitle>
            <DialogDescription>
              {scanDetailTime && new Date(scanDetailTime).toLocaleString()}
              {!scanDetailLoading && ` \u00B7 ${scanDetailHosts.length} host${scanDetailHosts.length !== 1 ? "s" : ""}`}
            </DialogDescription>
          </DialogHeader>
          {scanDetailLoading ? (
            <p className="text-sm text-muted-foreground py-4 text-center">Loading...</p>
          ) : scanDetailHosts.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No scan results found.</p>
          ) : (
            <div className="space-y-1.5 mt-2">
              {scanDetailHosts.map((h) => {
                const hasLog = h.raw_log && h.raw_log.length > 0;
                const isExpanded = expandedScanHosts.has(h.host_id);
                return (
                  <div key={h.host_id} className="rounded-md border overflow-hidden">
                    <div
                      className={`flex items-center justify-between px-3 py-2 ${
                        hasLog ? "cursor-pointer hover:bg-muted/50" : ""
                      }`}
                      onClick={() => {
                        if (!hasLog) return;
                        setExpandedScanHosts((prev) => {
                          const next = new Set(prev);
                          if (next.has(h.host_id)) next.delete(h.host_id);
                          else next.add(h.host_id);
                          return next;
                        });
                      }}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        {hasLog && (
                          <span className="text-[10px] text-muted-foreground shrink-0 w-3">
                            {isExpanded ? "\u25BC" : "\u25B6"}
                          </span>
                        )}
                        <span
                          className={`inline-block h-2 w-2 rounded-full shrink-0 ${
                            h.status === "compliant"
                              ? "bg-green-500"
                              : h.status === "unreachable"
                              ? "bg-red-500"
                              : h.status === "reboot_required"
                              ? "bg-orange-500"
                              : "bg-yellow-500"
                          }`}
                        />
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">{h.display_name}</p>
                          <p className="text-[10px] text-muted-foreground truncate">{h.hostname}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0 ml-3">
                        {h.worker_queue && (
                          <Badge variant="outline" className="text-[10px] text-muted-foreground">
                            {h.worker_queue}
                          </Badge>
                        )}
                        <Badge variant="outline" className="text-[10px]">
                          {h.os_type}
                        </Badge>
                        <Badge
                          variant={h.status === "compliant" ? "default" : "secondary"}
                          className="text-[10px]"
                        >
                          {h.status === "compliant"
                            ? "Compliant"
                            : h.status === "unreachable"
                            ? "Unreachable"
                            : h.status === "reboot_required"
                            ? "Reboot"
                            : `${h.pending_update_count} update${h.pending_update_count !== 1 ? "s" : ""}`}
                        </Badge>
                      </div>
                    </div>
                    {isExpanded && h.raw_log && (
                      <div className="border-t bg-muted/30 px-3 py-2 space-y-1">
                        {h.raw_log.map((entry, i) => {
                          const detail =
                            entry.output?.msg || entry.output?.stdout || entry.output?.stderr || "";
                          return (
                            <div key={i} className="font-mono text-[11px] leading-relaxed">
                              <span
                                className={
                                  entry.status === "ok"
                                    ? "text-green-600"
                                    : entry.status === "failed"
                                    ? "text-red-600"
                                    : entry.status === "unreachable"
                                    ? "text-red-400"
                                    : "text-muted-foreground"
                                }
                              >
                                [{entry.status}]
                              </span>{" "}
                              <span className="text-foreground">{entry.task}</span>
                              {detail && (
                                <span className="text-muted-foreground ml-2 break-all">
                                  {detail.length > 200
                                    ? detail.slice(0, 200) + "\u2026"
                                    : detail}
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {activity.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No activity yet. Run a scan or trigger a patch job.
            </p>
          ) : (
            <div className="space-y-0 divide-y">
              {activity.map((entry) => {
                const clickable = entry.link || entry.scan_at;
                return (
                <div
                  key={entry.id}
                  className={`flex items-start gap-3 py-3 first:pt-0 last:pb-0 ${
                    clickable ? "cursor-pointer hover:bg-muted/50 -mx-2 px-2 rounded-md" : ""
                  }`}
                  onClick={() => {
                    if (entry.scan_at) {
                      openScanDetail(entry.scan_at);
                    } else if (entry.link) {
                      router.push(entry.link);
                    }
                  }}
                >
                  <div className="mt-1.5 shrink-0">
                    <div
                      className={`h-2 w-2 rounded-full ${
                        entry.status === "completed"
                          ? "bg-green-500"
                          : entry.status === "failed"
                          ? "bg-red-500"
                          : entry.status === "running"
                          ? "bg-blue-500 animate-pulse"
                          : "bg-zinc-400"
                      }`}
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className="text-[10px] px-1.5 py-0 shrink-0"
                      >
                        {entry.type}
                      </Badge>
                      {entry.queues && (
                        <Badge
                          variant="secondary"
                          className="text-[10px] px-1.5 py-0 shrink-0"
                        >
                          {entry.queues}
                        </Badge>
                      )}
                      <p className="text-sm font-medium truncate">{entry.title}</p>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {entry.detail}
                    </p>
                  </div>
                  <span className="text-[10px] text-muted-foreground shrink-0 mt-0.5">
                    {timeAgo(entry.timestamp)}
                  </span>
                </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function formatUptime(seconds: number): string {
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
