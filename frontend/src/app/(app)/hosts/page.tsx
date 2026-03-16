"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
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

interface Host {
  id: string;
  display_name: string;
  hostname: string;
  os_type: string;
  ssh_port: number;
  winrm_port: number;
  winrm_use_ssl: boolean;
  site: string;
  site_id: string | null;
  site_locked: boolean;
  is_self: boolean;
  parent_id: string | null;
  roles: string[];
  worker_override: string | null;
  tags: string[];
  credential_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface SiteItem {
  id: string;
  name: string;
  display_name: string;
}

interface Credential {
  id: string;
  name: string;
}

interface Worker {
  name: string;
  status: string;
  queues: string[];
  active_tasks: number;
}

const EMPTY_FORM = {
  display_name: "",
  hostname: "",
  os_type: "linux",
  ssh_port: 22,
  winrm_port: 5986,
  site_id: "" as string,
  is_self: false,
  parent_id: "" as string,
  roles: [] as string[],
  worker_override: "",
  tags: "",
  credential_id: "",
};

const OS_LABELS: Record<string, string> = {
  linux: "Linux",
  windows: "Windows",
  proxmox: "Proxmox VE",
  truenas: "TrueNAS SCALE",
};

export default function HostsPage() {
  const [hosts, setHosts] = useState<Host[]>([]);
  const [sites, setSites] = useState<SiteItem[]>([]);
  const [creds, setCreds] = useState<Credential[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [open, setOpen] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [editingHost, setEditingHost] = useState<Host | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  const [search, setSearch] = useState("");
  const [siteFilter, setSiteFilter] = useState("__all__");
  const [osFilter, setOsFilter] = useState("__all__");
  const [tagFilter, setTagFilter] = useState("__all__");

  const load = useCallback(async () => {
    const [h, s, c, w] = await Promise.all([
      apiFetch<Host[]>("/api/hosts"),
      apiFetch<SiteItem[]>("/api/sites").catch(() => [] as SiteItem[]),
      apiFetch<Credential[]>("/api/credentials"),
      apiFetch<Worker[]>("/api/workers").catch(() => [] as Worker[]),
    ]);
    setHosts(h);
    setSites(s);
    setCreds(c);
    setWorkers(w);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const allSites = useMemo(
    () => [...new Set(hosts.map((h) => h.site || "default"))].sort(),
    [hosts]
  );
  const allTags = useMemo(
    () => [...new Set(hosts.flatMap((h) => h.tags))].sort(),
    [hosts]
  );
  const allQueues = useMemo(
    () => [...new Set(workers.flatMap((w) => w.queues))].sort(),
    [workers]
  );

  const workerByQueue = useMemo(() => {
    const map: Record<string, Worker> = {};
    for (const w of workers) {
      for (const q of w.queues) map[q] = w;
    }
    return map;
  }, [workers]);

  const hasActiveFilters =
    search !== "" ||
    siteFilter !== "__all__" ||
    osFilter !== "__all__" ||
    tagFilter !== "__all__";

  const filteredHosts = useMemo(() => {
    const q = search.toLowerCase();
    return hosts.filter((h) => {
      if (
        q &&
        !h.display_name.toLowerCase().includes(q) &&
        !h.hostname.toLowerCase().includes(q) &&
        !h.tags.some((t) => t.toLowerCase().includes(q))
      )
        return false;
      if (siteFilter !== "__all__" && (h.site || "default") !== siteFilter)
        return false;
      if (osFilter !== "__all__" && h.os_type !== osFilter) return false;
      if (tagFilter !== "__all__" && !h.tags.includes(tagFilter)) return false;
      return true;
    });
  }, [hosts, search, siteFilter, osFilter, tagFilter]);

  const groupedBySite = useMemo(() => {
    const groups: Record<string, Host[]> = {};
    for (const h of filteredHosts) {
      const site = h.site || "default";
      (groups[site] ??= []).push(h);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [filteredHosts]);

  const openCreateDialog = () => {
    setEditingHost(null);
    setForm({ ...EMPTY_FORM });
    setOpen(true);
  };

  const openEditDialog = (h: Host) => {
    setEditingHost(h);
    setForm({
      display_name: h.display_name,
      hostname: h.hostname,
      os_type: h.os_type,
      ssh_port: h.ssh_port,
      winrm_port: h.winrm_port,
      site_id: h.site_id || "",
      is_self: h.is_self,
      parent_id: h.parent_id || "",
      roles: h.roles || [],
      worker_override: h.worker_override || "",
      tags: h.tags.join(", "),
      credential_id: h.credential_id,
    });
    setOpen(true);
  };

  const handleDialogClose = (isOpen: boolean) => {
    setOpen(isOpen);
    if (!isOpen) setEditingHost(null);
  };

  const canSubmit = form.display_name.trim() !== "" && form.hostname.trim() !== "" && form.credential_id !== "";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.credential_id) {
      toast.error("Please select a credential");
      return;
    }
    const selectedSite = sites.find((s) => s.id === form.site_id);
    const payload = {
      display_name: form.display_name,
      hostname: form.hostname,
      os_type: form.os_type,
      ssh_port: form.ssh_port,
      winrm_port: form.winrm_port,
      site: selectedSite?.name || "default",
      site_id: form.site_id || null,
      is_self: form.is_self,
      parent_id: form.parent_id || null,
      roles: form.roles,
      worker_override: form.worker_override || null,
      tags: form.tags
        .split(",")
        .map((t: string) => t.trim())
        .filter(Boolean),
      credential_id: form.credential_id,
    };
    try {
      if (editingHost) {
        await apiFetch(`/api/hosts/${editingHost.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast.success("Host updated");
      } else {
        await apiFetch("/api/hosts", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast.success("Host added");
      }
      setOpen(false);
      setEditingHost(null);
      setForm({ ...EMPTY_FORM });
      load();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to save host");
    }
  };

  const handleDelete = async (id: string) => {
    await apiFetch(`/api/hosts/${id}`, { method: "DELETE" });
    toast.success("Host deleted");
    load();
  };

  const handleTest = async (id: string) => {
    setTesting(id);
    try {
      const result = await apiFetch<{
        success: boolean;
        latency_ms?: number;
        error?: string;
      }>(`/api/hosts/${id}/test`, { method: "POST" });
      if (result.success) {
        toast.success(`Reachable (${result.latency_ms}ms)`);
      } else {
        toast.error(`Unreachable: ${result.error}`);
      }
    } catch {
      toast.error("Test failed");
    } finally {
      setTesting(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Hosts</h1>
          <p className="text-muted-foreground mt-1">
            Manage your host inventory
          </p>
        </div>
        <Button onClick={openCreateDialog}>Add Host</Button>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="Search hosts..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-56"
        />
        <Select value={siteFilter} onValueChange={setSiteFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All sites" />
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
        <Select value={osFilter} onValueChange={setOsFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All types" />
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
          <Select value={tagFilter} onValueChange={setTagFilter}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="All tags" />
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
        {hasActiveFilters && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setSearch("");
              setSiteFilter("__all__");
              setOsFilter("__all__");
              setTagFilter("__all__");
            }}
          >
            Clear filters
          </Button>
        )}
        <span className="text-sm text-muted-foreground ml-auto">
          {filteredHosts.length} of {hosts.length} host(s)
        </span>
      </div>

      {/* Host list grouped by site */}
      {filteredHosts.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            {hosts.length === 0
              ? "No hosts yet. Add one to get started."
              : "No hosts match your filters."}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {groupedBySite.map(([site, siteHosts]) => {
            const siteWorker = workerByQueue[site];
            return (
              <div key={site} className="space-y-3">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block h-2.5 w-2.5 rounded-full ${
                      siteWorker ? "bg-green-500" : "bg-red-500"
                    }`}
                  />
                  <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                    {site}
                  </h2>
                  <span className="text-xs text-muted-foreground">
                    ({siteHosts.length} host
                    {siteHosts.length !== 1 ? "s" : ""})
                  </span>
                  {siteWorker && (
                    <Badge variant="outline" className="text-xs">
                      {siteWorker.name}
                    </Badge>
                  )}
                </div>
                <div className="grid gap-3">
                  {siteHosts.map((h) => (
                    <Card key={h.id}>
                      <CardHeader className="flex flex-row items-center justify-between pb-2">
                        <div className="space-y-1">
                          <CardTitle className="text-base flex items-center gap-2 flex-wrap">
                            {h.display_name}
                            <Badge variant="secondary" className="text-xs">
                              {h.os_type}
                            </Badge>
                            {(h.roles || []).includes("control_plane") && (
                              <Badge
                                variant="outline"
                                className="text-xs border-purple-500 text-purple-600"
                              >
                                control plane
                              </Badge>
                            )}
                            {(h.roles || []).includes("worker") && (
                              <Badge
                                variant="outline"
                                className="text-xs border-amber-500 text-amber-600"
                              >
                                worker
                              </Badge>
                            )}
                            {(h.roles || []).includes("docker_host") && (
                              <Badge
                                variant="outline"
                                className="text-xs border-sky-500 text-sky-600"
                              >
                                docker host
                              </Badge>
                            )}
                            {h.worker_override && (
                              <Badge
                                variant="outline"
                                className="text-xs border-blue-500 text-blue-600"
                              >
                                override: {h.worker_override}
                              </Badge>
                            )}
                            {!h.is_active && (
                              <Badge variant="destructive" className="text-xs">
                                inactive
                              </Badge>
                            )}
                          </CardTitle>
                          <p className="text-sm text-muted-foreground">
                            {h.hostname}
                            {h.parent_id && (() => {
                              const parent = hosts.find((p) => p.id === h.parent_id);
                              return parent ? (
                                <span className="text-xs ml-2 text-muted-foreground">
                                  (on {parent.display_name})
                                </span>
                              ) : null;
                            })()}
                          </p>
                          {h.tags.length > 0 && (
                            <div className="flex gap-1 flex-wrap">
                              {h.tags.map((t) => (
                                <Badge
                                  key={t}
                                  variant="outline"
                                  className="text-xs"
                                >
                                  {t}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openEditDialog(h)}
                          >
                            Edit
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleTest(h.id)}
                            disabled={testing === h.id}
                          >
                            {testing === h.id ? "..." : "Test"}
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleDelete(h.id)}
                          >
                            Delete
                          </Button>
                        </div>
                      </CardHeader>
                    </Card>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={open} onOpenChange={handleDialogClose}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingHost ? "Edit Host" : "New Host"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Display Name <span className="text-red-500">*</span></label>
              <Input
                placeholder="Display name"
                value={form.display_name}
                onChange={(e) =>
                  setForm({ ...form, display_name: e.target.value })
                }
                className="mt-1"
                required
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Hostname / IP <span className="text-red-500">*</span></label>
              <Input
                placeholder="Hostname / IP"
                value={form.hostname}
                onChange={(e) => setForm({ ...form, hostname: e.target.value })}
                className="mt-1"
                required
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">OS Type <span className="text-red-500">*</span></label>
              <Select
                value={form.os_type}
                onValueChange={(v) =>
                  setForm({
                    ...form,
                    os_type: v,
                    ssh_port: v !== "windows" ? form.ssh_port : 22,
                    winrm_port: v === "windows" ? form.winrm_port : 5986,
                  })
                }
              >
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="linux">Linux</SelectItem>
                  <SelectItem value="windows">Windows</SelectItem>
                  <SelectItem value="proxmox">Proxmox VE</SelectItem>
                  <SelectItem value="truenas">TrueNAS SCALE</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.os_type === "windows" && (
              <details className="rounded-md border bg-muted/40 px-3 py-2">
                <summary className="cursor-pointer text-sm font-medium">
                  How to enable WinRM on the target host
                </summary>
                <div className="mt-3 space-y-2 text-xs text-muted-foreground">
                  <p>
                    Run in an{" "}
                    <strong className="text-foreground">
                      elevated PowerShell
                    </strong>{" "}
                    on the Windows host. Works on Server 2016+, Windows 10/11
                    Pro &amp; Enterprise.
                  </p>
                  <div className="rounded-md bg-zinc-950 p-3 overflow-x-auto">
                    <code className="block text-[11px] leading-5 text-zinc-300 whitespace-pre">
                      {`winrm quickconfig -force
winrm set winrm/config/service/auth '@{Basic="true"}'
winrm set winrm/config/service '@{AllowUnencrypted="true"}'

# HTTPS listener (recommended, port 5986)
$cert = New-SelfSignedCertificate \`
  -DnsName $env:COMPUTERNAME \`
  -CertStoreLocation Cert:\\LocalMachine\\My
winrm create winrm/config/Listener\`
  ?Address=*+Transport=HTTPS \`
  "@{Hostname=$env:COMPUTERNAME;\`
    CertificateThumbprint=$($cert.Thumbprint)}"

# Firewall rule
netsh advfirewall firewall add rule \`
  name="WinRM HTTPS" dir=in action=allow \`
  protocol=TCP localport=5986`}
                    </code>
                  </div>
                  <p>
                    Port <strong className="text-foreground">5986</strong> =
                    HTTPS (recommended) {"\u00B7"}{" "}
                    <strong className="text-foreground">5985</strong> = HTTP{" "}
                    {"\u00B7"} Win 11 Home not supported.
                  </p>
                </div>
              </details>
            )}
            <div>
              <label className="text-xs font-medium text-muted-foreground">
                {form.os_type !== "windows" ? "SSH Port" : "WinRM Port"}
              </label>
              <Input
                type="number"
                placeholder={
                  form.os_type !== "windows" ? "SSH Port" : "WinRM Port"
                }
                value={
                  form.os_type !== "windows" ? form.ssh_port : form.winrm_port
                }
                onChange={(e) => {
                  const port = parseInt(e.target.value) || 0;
                  setForm(
                    form.os_type !== "windows"
                      ? { ...form, ssh_port: port }
                      : { ...form, winrm_port: port }
                  );
                }}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Site</label>
              <Select
                value={form.site_id || "__auto__"}
                onValueChange={(v) =>
                  setForm({ ...form, site_id: v === "__auto__" ? "" : v })
                }
              >
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Auto-detect from subnet" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__auto__">Auto-detect</SelectItem>
                  {sites.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.display_name} ({s.name})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Parent Host</label>
              <Select
                value={form.parent_id || "__none__"}
                onValueChange={(v) =>
                  setForm({ ...form, parent_id: v === "__none__" ? "" : v })
                }
              >
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="No parent (top-level)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">No parent (top-level)</SelectItem>
                  {hosts
                    .filter((h) => h.id !== editingHost?.id)
                    .map((h) => (
                      <SelectItem key={h.id} value={h.id}>
                        {h.display_name} ({h.hostname})
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Set the hypervisor or physical machine this host runs on.
              </p>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Roles</label>
              <div className="flex gap-4 mt-1">
                {([
                  ["control_plane", "Control Plane"],
                  ["worker", "Worker"],
                  ["docker_host", "Docker Host"],
                ] as const).map(([role, label]) => (
                  <label key={role} className="flex items-center gap-1.5 text-sm">
                    <input
                      type="checkbox"
                      checked={form.roles.includes(role)}
                      onChange={(e) => {
                        const next = e.target.checked
                          ? [...form.roles, role]
                          : form.roles.filter((r) => r !== role);
                        setForm({ ...form, roles: next, is_self: next.includes("worker") });
                      }}
                      className="rounded border-input"
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Worker Queue Override</label>
              <Select
                value={form.worker_override || "__auto__"}
                onValueChange={(v) =>
                  setForm({
                    ...form,
                    worker_override: v === "__auto__" ? "" : v,
                  })
                }
              >
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Worker override" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__auto__">Auto (use site worker)</SelectItem>
                  {allQueues.map((q) => (
                    <SelectItem key={q} value={q}>
                      {q}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Override which Celery worker handles tasks for this host. Defaults to the worker assigned to the host&apos;s site.
              </p>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Tags</label>
              <Input
                placeholder="Tags (comma-separated)"
                value={form.tags}
                onChange={(e) => setForm({ ...form, tags: e.target.value })}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Credential <span className="text-red-500">*</span></label>
              <Select
                value={form.credential_id || "__none__"}
                onValueChange={(v) => setForm({ ...form, credential_id: v === "__none__" ? "" : v })}
              >
                <SelectTrigger className={`mt-1 ${!form.credential_id ? "border-red-300" : ""}`}>
                  <SelectValue placeholder="Select credential" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__" disabled>Select a credential...</SelectItem>
                  {creds.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" className="w-full" disabled={!canSubmit}>
              {editingHost ? "Save Changes" : "Add Host"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
