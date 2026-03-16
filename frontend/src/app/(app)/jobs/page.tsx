"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

interface Job {
  id: string;
  status: string;
  job_type: string;
  host_ids: string[];
  patch_categories: string[];
  reboot_policy: string;
  started_at: string | null;
  completed_at: string | null;
  host_results: Record<string, unknown>;
  wave_plan: WavePlan | null;
  current_wave: number | null;
  created_at: string;
}

interface WaveHost {
  id: string;
  display_name: string;
  hostname: string;
  os_type: string;
  roles: string[];
}

interface Wave {
  index: number;
  hosts: WaveHost[];
  label: string;
}

interface BlastRadiusEntry {
  host_id: string;
  display_name: string;
  hostname: string;
  reason: string;
}

interface BlastRadius {
  affected: BlastRadiusEntry[];
  summary: string;
}

interface WavePlan {
  waves: Wave[];
  warnings: string[];
  blast_radius?: BlastRadius;
}

interface Host {
  id: string;
  display_name: string;
  hostname: string;
  os_type: string;
  site: string;
  tags: string[];
}

const STATUS_COLOR: Record<string, string> = {
  queued: "secondary",
  running: "default",
  completed: "default",
  failed: "destructive",
};

const OS_LABELS: Record<string, string> = {
  linux: "Linux",
  windows: "Windows",
  proxmox: "Proxmox VE",
  truenas: "TrueNAS SCALE",
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [hosts, setHosts] = useState<Host[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [wavePlan, setWavePlan] = useState<WavePlan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const router = useRouter();

  const [modalSearch, setModalSearch] = useState("");
  const [modalSite, setModalSite] = useState("__all__");
  const [modalOs, setModalOs] = useState("__all__");
  const [modalTag, setModalTag] = useState("__all__");

  const load = useCallback(async () => {
    const [j, h] = await Promise.all([
      apiFetch<Job[]>("/api/jobs"),
      apiFetch<Host[]>("/api/hosts"),
    ]);
    setJobs(j);
    setHosts(h);
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [load]);

  const allSites = useMemo(
    () => [...new Set(hosts.map((h) => h.site || "default"))].sort(),
    [hosts]
  );
  const allTags = useMemo(
    () => [...new Set(hosts.flatMap((h) => h.tags || []))].sort(),
    [hosts]
  );

  const visibleHosts = useMemo(() => {
    const q = modalSearch.toLowerCase();
    return hosts.filter((h) => {
      if (
        q &&
        !h.display_name.toLowerCase().includes(q) &&
        !h.hostname.toLowerCase().includes(q)
      )
        return false;
      if (modalSite !== "__all__" && (h.site || "default") !== modalSite)
        return false;
      if (modalOs !== "__all__" && h.os_type !== modalOs) return false;
      if (modalTag !== "__all__" && !(h.tags || []).includes(modalTag))
        return false;
      return true;
    });
  }, [hosts, modalSearch, modalSite, modalOs, modalTag]);

  const groupedVisible = useMemo(() => {
    const groups: Record<string, Host[]> = {};
    for (const h of visibleHosts) {
      const site = h.site || "default";
      (groups[site] ??= []).push(h);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [visibleHosts]);

  const toggleHost = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleGroup = (siteHosts: Host[]) => {
    setSelected((prev) => {
      const next = new Set(prev);
      const allSelected = siteHosts.every((h) => next.has(h.id));
      for (const h of siteHosts) {
        if (allSelected) next.delete(h.id);
        else next.add(h.id);
      }
      return next;
    });
  };

  const toggleAll = () => {
    setSelected((prev) => {
      const allVisible = visibleHosts.every((h) => prev.has(h.id));
      if (allVisible) {
        const next = new Set(prev);
        for (const h of visibleHosts) next.delete(h.id);
        return next;
      }
      const next = new Set(prev);
      for (const h of visibleHosts) next.add(h.id);
      return next;
    });
  };

  const selectedOsBreakdown = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const h of hosts) {
      if (selected.has(h.id)) {
        counts[h.os_type] = (counts[h.os_type] || 0) + 1;
      }
    }
    return counts;
  }, [hosts, selected]);

  const allVisibleSelected =
    visibleHosts.length > 0 && visibleHosts.every((h) => selected.has(h.id));

  const handleDialogOpen = (isOpen: boolean) => {
    setOpen(isOpen);
    if (isOpen) {
      setModalSearch("");
      setModalSite("__all__");
      setModalOs("__all__");
      setModalTag("__all__");
      setWavePlan(null);
      setConfirmed(false);
    }
  };

  const previewPlan = async () => {
    if (selected.size === 0) return;
    setPlanLoading(true);
    setConfirmed(false);
    try {
      const plan = await apiFetch<WavePlan>("/api/jobs/plan", {
        method: "POST",
        body: JSON.stringify({ host_ids: [...selected] }),
      });
      setWavePlan(plan);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to preview plan");
    } finally {
      setPlanLoading(false);
    }
  };

  const triggerPatch = async () => {
    if (selected.size === 0) return;
    setTriggering(true);
    try {
      await apiFetch("/api/jobs", {
        method: "POST",
        body: JSON.stringify({ host_ids: [...selected] }),
      });
      toast.success("Patch job triggered");
      setOpen(false);
      setSelected(new Set());
      setWavePlan(null);
      load();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed");
    } finally {
      setTriggering(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Jobs</h1>
          <p className="text-muted-foreground mt-1">
            Patch job history and status
          </p>
        </div>
        <Dialog open={open} onOpenChange={handleDialogOpen}>
          <DialogTrigger asChild>
            <Button>New Patch Job</Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>Select Hosts to Patch</DialogTitle>
            </DialogHeader>

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-2">
              <Input
                placeholder="Search..."
                value={modalSearch}
                onChange={(e) => setModalSearch(e.target.value)}
                className="h-8 w-40 text-sm"
              />
              <Select value={modalSite} onValueChange={setModalSite}>
                <SelectTrigger className="h-8 w-32 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All sites</SelectItem>
                  {allSites.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={modalOs} onValueChange={setModalOs}>
                <SelectTrigger className="h-8 w-32 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All types</SelectItem>
                  {Object.entries(OS_LABELS).map(([val, label]) => (
                    <SelectItem key={val} value={val}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {allTags.length > 0 && (
                <Select value={modalTag} onValueChange={setModalTag}>
                  <SelectTrigger className="h-8 w-32 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all__">All tags</SelectItem>
                    {allTags.map((t) => (
                      <SelectItem key={t} value={t}>
                        {t}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            {/* Select all toggle */}
            <label className="flex items-center gap-2 px-2 py-1 text-sm font-medium border-b">
              <input
                type="checkbox"
                checked={allVisibleSelected}
                onChange={toggleAll}
                className="rounded"
              />
              <span>
                {allVisibleSelected ? "Deselect all" : "Select all"}
              </span>
              <span className="text-muted-foreground text-xs ml-auto">
                {visibleHosts.length} visible
              </span>
            </label>

            {/* Grouped host list */}
            <div className="space-y-3 max-h-[28rem] overflow-y-auto">
              {groupedVisible.length === 0 ? (
                <p className="text-center text-sm text-muted-foreground py-4">
                  No hosts match your filters.
                </p>
              ) : (
                groupedVisible.map(([site, siteHosts]) => {
                  const allGroupSelected = siteHosts.every((h) =>
                    selected.has(h.id)
                  );
                  return (
                    <div key={site}>
                      <label className="flex items-center gap-2 px-2 py-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground cursor-pointer hover:bg-muted rounded">
                        <input
                          type="checkbox"
                          checked={allGroupSelected}
                          onChange={() => toggleGroup(siteHosts)}
                          className="rounded"
                        />
                        {site}
                        <span className="font-normal">
                          ({siteHosts.length})
                        </span>
                      </label>
                      <div className="ml-1">
                        {siteHosts.map((h) => (
                          <label
                            key={h.id}
                            className="flex items-center gap-2 p-2 rounded hover:bg-muted cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={selected.has(h.id)}
                              onChange={() => toggleHost(h.id)}
                              className="rounded"
                            />
                            <span className="text-sm">{h.display_name}</span>
                            <Badge
                              variant="secondary"
                              className="text-xs ml-auto"
                            >
                              {h.os_type}
                            </Badge>
                          </label>
                        ))}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Selection summary */}
            <div className="flex items-center gap-2 text-sm text-muted-foreground border-t pt-2">
              <span>
                {selected.size} of {hosts.length} host(s) selected
              </span>
              <div className="flex gap-1 ml-auto">
                {Object.entries(selectedOsBreakdown).map(([os, count]) => (
                  <Badge key={os} variant="outline" className="text-xs">
                    {os}: {count}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Wave plan preview */}
            {selected.size > 0 && (
              <div className="space-y-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={previewPlan}
                  disabled={planLoading}
                  className="w-full text-xs"
                >
                  {planLoading ? "Computing..." : "Preview Execution Plan"}
                </Button>

                {wavePlan && (
                  <div className="rounded-md border bg-muted/40 p-3 space-y-3">
                    <p className="text-xs font-medium">
                      {wavePlan.waves.length} wave(s) planned
                    </p>

                    {wavePlan.warnings.length > 0 && (
                      <div className="space-y-1 rounded bg-amber-500/10 p-2">
                        {wavePlan.warnings.map((w, i) => (
                          <p key={i} className="text-xs text-amber-600 flex gap-1">
                            <span>&#9888;</span> {w}
                          </p>
                        ))}
                      </div>
                    )}

                    {wavePlan.blast_radius && wavePlan.blast_radius.affected.length > 0 && (
                      <div className="rounded bg-red-500/10 p-2 space-y-1">
                        <p className="text-xs font-medium text-red-600">
                          &#9888; Blast Radius: {wavePlan.blast_radius.summary}
                        </p>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {wavePlan.blast_radius.affected.map((a) => (
                            <Badge key={a.host_id} variant="outline" className="text-[10px] border-red-300 text-red-600">
                              {a.display_name}
                            </Badge>
                          ))}
                        </div>
                        <p className="text-[10px] text-red-500 mt-1">
                          These hosts will experience downtime when their parent is patched/rebooted.
                        </p>
                      </div>
                    )}

                    {wavePlan.waves.map((wave) => (
                      <div key={wave.index} className="space-y-1">
                        <p className="text-xs font-medium text-muted-foreground">
                          {wave.label}
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {wave.hosts.map((wh) => (
                            <Badge key={wh.id} variant="outline" className="text-[10px]">
                              {wh.display_name}
                              {wh.roles.includes("control_plane") ? " (CP)" : ""}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))}

                    {(wavePlan.blast_radius?.affected?.length ?? 0) > 0 && (
                      <label className="flex items-center gap-2 text-xs pt-1 border-t">
                        <input
                          type="checkbox"
                          checked={confirmed}
                          onChange={(e) => setConfirmed(e.target.checked)}
                          className="rounded"
                        />
                        <span className="text-red-600 font-medium">
                          I understand the blast radius impact and want to proceed
                        </span>
                      </label>
                    )}
                  </div>
                )}
              </div>
            )}

            <Button
              onClick={triggerPatch}
              disabled={
                selected.size === 0 ||
                triggering ||
                (wavePlan?.blast_radius?.affected?.length
                  ? wavePlan.blast_radius.affected.length > 0 && !confirmed
                  : false)
              }
              className="w-full"
            >
              {triggering
                ? "Triggering..."
                : `Patch ${selected.size} host(s)`}
            </Button>
          </DialogContent>
        </Dialog>
      </div>

      {jobs.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No jobs yet. Trigger a patch to get started.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {jobs.map((j) => (
            <Card
              key={j.id}
              className="cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => router.push(`/jobs/${j.id}`)}
            >
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div className="space-y-1">
                  <CardTitle className="text-base flex items-center gap-2">
                    {j.job_type} job
                    <Badge
                      variant={
                        (STATUS_COLOR[j.status] as
                          | "default"
                          | "secondary"
                          | "destructive") || "secondary"
                      }
                    >
                      {j.status}
                    </Badge>
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {j.host_ids.length} host(s)
                    {j.wave_plan && j.wave_plan.waves && (
                      <span>
                        {" \u00B7 "}
                        {j.status === "running" && j.current_wave != null
                          ? `Wave ${j.current_wave + 1}/${j.wave_plan.waves.length}`
                          : `${j.wave_plan.waves.length} wave(s)`}
                      </span>
                    )}
                    {" \u00B7 "}
                    {new Date(j.created_at).toLocaleString()}
                    {j.completed_at &&
                      ` \u00B7 Completed ${new Date(
                        j.completed_at
                      ).toLocaleString()}`}
                  </p>
                </div>
                <span className="text-xs text-muted-foreground">
                  View logs &rarr;
                </span>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
