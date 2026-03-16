"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { toast } from "sonner";

interface RegistryConfig {
  id: string;
  name: string;
  url: string;
  project: string;
  username: string;
  build_host_id: string;
  repo_path: string;
  external_database_url: string | null;
  external_redis_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface DockerHost {
  id: string;
  display_name: string;
  hostname: string;
  site: string;
  roles: string[];
}

interface ImageBuild {
  id: string;
  registry_id: string;
  image_tag: string;
  git_ref: string;
  status: string;
  build_log: string | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

interface DeploymentStatus {
  deployment_id: string | null;
  host_id: string;
  hostname: string;
  display_name: string;
  site: string;
  current_tag: string | null;
  status: string;
  worker_site: string;
  deployed_at: string | null;
  last_health_check: string | null;
  worker_online: boolean;
}

interface DeploymentOverview {
  registry_configured: boolean;
  registry: RegistryConfig | null;
  latest_build: ImageBuild | null;
  deployments: DeploymentStatus[];
}

const statusColors: Record<string, string> = {
  completed: "bg-green-500",
  running: "bg-green-500",
  "running (compose)": "bg-green-500",
  building: "bg-blue-500",
  pushing: "bg-blue-500",
  deploying: "bg-blue-500",
  pending: "bg-yellow-500",
  failed: "bg-red-500",
  stopped: "bg-gray-500",
  unhealthy: "bg-orange-500",
  not_deployed: "bg-gray-400",
  removing: "bg-orange-500",
  removed: "bg-gray-400",
};

function HelpBlurb({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-dashed border-border bg-muted/30">
      <button
        type="button"
        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span>{title}</span>
        <span className="text-[10px]">{open ? "\u25B2" : "\u25BC"}</span>
      </button>
      {open && (
        <div className="border-t border-dashed border-border px-3 py-2.5 text-xs text-muted-foreground space-y-2">
          {children}
        </div>
      )}
    </div>
  );
}

function PrereqItem({
  title,
  done,
  children,
}: {
  title: string;
  done: boolean | null;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [manualCheck, setManualCheck] = useState(false);
  const isManual = done === null;
  const checked = isManual ? manualCheck : done;
  const icon = checked === true ? "\u2705" : checked === false ? "\u274C" : "\u2B1C";
  return (
    <div className="rounded-md border border-border bg-card">
      <div className="flex w-full items-center gap-2.5 px-3 py-2.5 text-sm">
        {isManual ? (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setManualCheck(!manualCheck); }}
            className="text-base leading-none shrink-0 hover:scale-110 transition-transform cursor-pointer"
            title="Click to mark as done"
          >
            {manualCheck ? "\u2705" : "\u2B1C"}
          </button>
        ) : (
          <span className="text-base leading-none shrink-0">{icon}</span>
        )}
        <button
          type="button"
          className="flex flex-1 items-center justify-between text-left hover:bg-muted/50 transition-colors -my-2.5 py-2.5 -mr-3 pr-3"
          onClick={() => setOpen(!open)}
        >
          <span className="font-medium">{title}</span>
          <span className="text-[10px] text-muted-foreground">{open ? "\u25B2" : "\u25BC"}</span>
        </button>
      </div>
      {open && (
        <div className="border-t px-3 py-2.5 text-xs text-muted-foreground space-y-1.5 pl-9">
          {children}
        </div>
      )}
    </div>
  );
}

function ConnectivityTest({ url, endpoint, label, hint }: { url: string; endpoint: string; label: string; hint?: string }) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  const handleTest = async () => {
    setTesting(true);
    setResult(null);
    try {
      const res = await apiFetch<{ success: boolean; message: string }>(
        endpoint,
        { method: "POST", body: JSON.stringify({ url }) },
      );
      setResult(res);
    } catch (e: unknown) {
      setResult({ success: false, message: e instanceof Error ? e.message : "Test failed" });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="mt-1.5">
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 px-2.5 text-xs"
          onClick={handleTest}
          disabled={testing || !url}
        >
          {testing ? "Testing..." : `Test ${label}`}
        </Button>
        {result && (
          <span className={`text-xs ${result.success ? "text-green-600" : "text-red-500"}`}>
            {result.message}
          </span>
        )}
      </div>
      {hint && <p className="text-[10px] text-muted-foreground mt-1">{hint}</p>}
    </div>
  );
}

export default function SettingsPage() {
  const [overview, setOverview] = useState<DeploymentOverview | null>(null);
  const [dockerHosts, setDockerHosts] = useState<DockerHost[]>([]);
  const [builds, setBuilds] = useState<ImageBuild[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("registry");

  const showWizard = overview !== null && !overview.registry_configured;

  const loadAll = useCallback(async () => {
    try {
      const [status, hosts, buildList] = await Promise.all([
        apiFetch<DeploymentOverview>("/api/deployment/status"),
        apiFetch<DockerHost[]>("/api/deployment/docker-hosts").catch(() => []),
        apiFetch<ImageBuild[]>("/api/deployment/builds").catch(() => []),
      ]);
      setOverview(status);
      setDockerHosts(hosts);
      setBuilds(buildList);
    } catch {
      toast.error("Failed to load deployment status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (showWizard) {
    return (
      <SetupWizard
        dockerHosts={dockerHosts}
        onComplete={loadAll}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Manage registry, image builds, and worker deployments
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="registry">Registry</TabsTrigger>
          <TabsTrigger value="builds">Builds</TabsTrigger>
          <TabsTrigger value="workers">Workers</TabsTrigger>
        </TabsList>

        <TabsContent value="registry" className="mt-4">
          <RegistryTab
            registry={overview?.registry ?? null}
            dockerHosts={dockerHosts}
            onSaved={loadAll}
          />
        </TabsContent>

        <TabsContent value="builds" className="mt-4">
          <BuildsTab builds={builds} onBuildTriggered={loadAll} />
        </TabsContent>

        <TabsContent value="workers" className="mt-4">
          <WorkersTab
            deployments={overview?.deployments ?? []}
            builds={builds}
            onAction={loadAll}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Registry Tab
// ---------------------------------------------------------------------------

function RegistryTab({
  registry,
  dockerHosts,
  onSaved,
}: {
  registry: RegistryConfig | null;
  dockerHosts: DockerHost[];
  onSaved: () => void;
}) {
  const [url, setUrl] = useState(registry?.url ?? "");
  const [project, setProject] = useState(registry?.project ?? "updatr");
  const [username, setUsername] = useState(registry?.username ?? "");
  const [password, setPassword] = useState("");
  const [buildHostId, setBuildHostId] = useState(registry?.build_host_id ?? "");
  const [repoPath, setRepoPath] = useState(registry?.repo_path ?? "/opt/updatr");
  const [extDbUrl, setExtDbUrl] = useState(registry?.external_database_url ?? "");
  const [extRedisUrl, setExtRedisUrl] = useState(registry?.external_redis_url ?? "");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const handleTest = async () => {
    if (!url || !username) {
      toast.error("URL and username are required to test");
      return;
    }
    if (!registry && !password) {
      toast.error("Password is required for first-time test");
      return;
    }
    setTesting(true);
    try {
      const result = await apiFetch<{ success: boolean; message: string; harbor_version: string | null }>(
        "/api/deployment/registry/test",
        { method: "POST", body: JSON.stringify({ url, username, password: password || null }) }
      );
      if (result.success) {
        toast.success(`${result.message}${result.harbor_version ? ` (v${result.harbor_version})` : ""}`);
      } else {
        toast.error(result.message);
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Test failed");
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!url || !username || !buildHostId) {
      toast.error("URL, username, and build host are required");
      return;
    }
    if (!registry && !password) {
      toast.error("Password is required for new configuration");
      return;
    }
    setSaving(true);
    try {
      await apiFetch("/api/deployment/registry", {
        method: "POST",
        body: JSON.stringify({
          url,
          project,
          username,
          password: password || null,
          build_host_id: buildHostId,
          repo_path: repoPath,
          external_database_url: extDbUrl || null,
          external_redis_url: extRedisUrl || null,
        }),
      });
      toast.success("Registry configuration saved");
      onSaved();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Harbor Registry</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground">Harbor URL</label>
            <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://harbor.yourdomain.com" className="mt-1" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Project</label>
            <Input value={project} onChange={(e) => setProject(e.target.value)} placeholder="updatr" className="mt-1" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground">Username</label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="admin or robot$name" className="mt-1" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Password</label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={registry ? "(unchanged)" : "Password"} className="mt-1" />
          </div>
        </div>
        <HelpBlurb title="What credentials should I use?">
          <p>
            <strong>Harbor admin account</strong> &mdash; The simplest option. Use the <code className="bg-muted px-1 rounded">admin</code> username and the password you set in <code className="bg-muted px-1 rounded">harbor.yml</code> during installation. This grants full access to push images and manage the project.
          </p>
          <p>
            <strong>Robot account (recommended for production)</strong> &mdash; In Harbor, go to your project &rarr; <em>Robot Accounts</em> &rarr; <em>New Robot Account</em>. Give it <code className="bg-muted px-1 rounded">push</code> + <code className="bg-muted px-1 rounded">pull</code> permissions. The username will look like <code className="bg-muted px-1 rounded">robot$updatr+deployer</code> and you&apos;ll receive a generated token as the password. Robot accounts are scoped, auditable, and revocable without affecting your admin login.
          </p>
          <p>
            <strong>Project name</strong> must match an existing project in Harbor. The default is <code className="bg-muted px-1 rounded">updatr</code>. Create it in Harbor under <em>Projects</em> &rarr; <em>New Project</em> if it doesn&apos;t exist.
          </p>
        </HelpBlurb>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleTest} disabled={testing}>
            {testing ? "Testing..." : "Test Connection"}
          </Button>
        </div>

        <div className="border-t pt-4">
          <h3 className="text-sm font-medium mb-3">Build Configuration</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Build Host</label>
              <Select value={buildHostId} onValueChange={setBuildHostId}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Select a docker host" />
                </SelectTrigger>
                <SelectContent>
                  {dockerHosts.map((h) => (
                    <SelectItem key={h.id} value={h.id}>
                      {h.display_name} ({h.hostname})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {dockerHosts.length === 0 && (
                <p className="text-[10px] text-amber-600 mt-1">
                  No hosts with &quot;docker_host&quot; role found. Add the role to a host first.
                </p>
              )}
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Repo Path on Build Host</label>
              <Input value={repoPath} onChange={(e) => setRepoPath(e.target.value)} placeholder="/opt/updatr" className="mt-1 font-mono text-sm" />
            </div>
          </div>
          <div className="mt-3">
            <HelpBlurb title="How does the build host work?">
              <p>
                The build host is a machine with Docker installed where worker images are built and pushed to Harbor. Ideally this is the same machine running Harbor (the push is instant over localhost).
              </p>
              <p>
                <strong>Prerequisites on the build host:</strong> Docker must be installed, the updatr git repository must be cloned at the path specified above, and the host must be reachable via SSH using the credentials assigned to it in the Hosts page.
              </p>
              <p>
                The host must have the <code className="bg-muted px-1 rounded">docker_host</code> role assigned. You can add this in <em>Hosts</em> &rarr; Edit &rarr; Roles.
              </p>
            </HelpBlurb>
          </div>
        </div>

        <div className="border-t pt-4">
          <h3 className="text-sm font-medium mb-3">Remote Worker URLs</h3>
          <p className="text-xs text-muted-foreground mb-3">
            Routable URLs that deployed workers use to connect back to the control plane&apos;s database and Redis.
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground">External Database URL</label>
              <Input value={extDbUrl} onChange={(e) => setExtDbUrl(e.target.value)} placeholder="postgresql+asyncpg://user:pass@10.0.0.1:5432/updatr" className="mt-1 font-mono text-xs" />
              <ConnectivityTest url={extDbUrl} endpoint="/api/deployment/test-database" label="Database" hint="Tests connectivity from the control plane." />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">External Redis URL</label>
              <Input value={extRedisUrl} onChange={(e) => setExtRedisUrl(e.target.value)} placeholder="redis://:password@10.0.0.1:6379/0" className="mt-1 font-mono text-xs" />
              <ConnectivityTest url={extRedisUrl} endpoint="/api/deployment/test-redis" label="Redis" hint="Tests connectivity from the control plane." />
            </div>
          </div>
          <div className="mt-3">
            <HelpBlurb title="Why are external URLs needed?">
              <p>
                The control plane&apos;s Docker Compose uses internal service names like <code className="bg-muted px-1 rounded">postgres</code> and <code className="bg-muted px-1 rounded">redis</code> that only resolve inside its own Docker network. Remote workers on other machines can&apos;t reach those names.
              </p>
              <p>
                Enter the LAN IP or VPN address of the machine running Postgres and Redis. These are the same addresses you&apos;d use in the <code className="bg-muted px-1 rounded">docker-compose.worker.yml</code> environment variables. For example: <code className="bg-muted px-1 rounded">postgresql+asyncpg://updatr:pass@10.1.2.5:5432/updatr</code>
              </p>
              <p>
                Make sure the Postgres and Redis ports are exposed to the network (check <code className="bg-muted px-1 rounded">POSTGRES_BIND</code> and <code className="bg-muted px-1 rounded">REDIS_BIND</code> in your <code className="bg-muted px-1 rounded">.env</code> &mdash; they default to <code className="bg-muted px-1 rounded">127.0.0.1</code> which blocks remote access).
              </p>
            </HelpBlurb>
          </div>
        </div>

        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save Configuration"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Builds Tab
// ---------------------------------------------------------------------------

function BuildsTab({
  builds,
  onBuildTriggered,
}: {
  builds: ImageBuild[];
  onBuildTriggered: () => void;
}) {
  const [tag, setTag] = useState("");
  const [gitRef, setGitRef] = useState("main");
  const [building, setBuilding] = useState(false);
  const [expandedBuild, setExpandedBuild] = useState<string | null>(null);
  const [pollBuildId, setPollBuildId] = useState<string | null>(null);
  const [polledBuild, setPolledBuild] = useState<ImageBuild | null>(null);

  useEffect(() => {
    if (!pollBuildId) return;
    const interval = setInterval(async () => {
      try {
        const b = await apiFetch<ImageBuild>(`/api/deployment/builds/${pollBuildId}`);
        setPolledBuild(b);
        if (b.status === "completed" || b.status === "failed") {
          clearInterval(interval);
          setPollBuildId(null);
          onBuildTriggered();
          if (b.status === "completed") toast.success(`Build ${b.image_tag} completed`);
          else toast.error(`Build ${b.image_tag} failed: ${b.error}`);
        }
      } catch { /* ignore polling errors */ }
    }, 3000);
    return () => clearInterval(interval);
  }, [pollBuildId, onBuildTriggered]);

  const handleBuild = async () => {
    if (!tag.trim()) {
      toast.error("Image tag is required");
      return;
    }
    setBuilding(true);
    try {
      const result = await apiFetch<ImageBuild>("/api/deployment/builds", {
        method: "POST",
        body: JSON.stringify({ image_tag: tag.trim(), git_ref: gitRef.trim() }),
      });
      toast.success(`Build started for ${tag}`);
      setPollBuildId(result.id);
      setExpandedBuild(result.id);
      setTag("");
      onBuildTriggered();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to start build");
    } finally {
      setBuilding(false);
    }
  };

  const displayBuilds = builds.map((b) =>
    polledBuild && b.id === polledBuild.id ? polledBuild : b
  );

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Build New Image</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <label className="text-xs font-medium text-muted-foreground">Image Tag</label>
              <Input value={tag} onChange={(e) => setTag(e.target.value)} placeholder="e.g. 1.0.0 or latest" className="mt-1" />
            </div>
            <div className="w-40">
              <label className="text-xs font-medium text-muted-foreground">Git Ref</label>
              <Input value={gitRef} onChange={(e) => setGitRef(e.target.value)} placeholder="main" className="mt-1" />
            </div>
            <Button onClick={handleBuild} disabled={building}>
              {building ? "Starting..." : "Build & Push"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Build History</CardTitle>
        </CardHeader>
        <CardContent>
          {displayBuilds.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No builds yet. Build your first image above.
            </p>
          ) : (
            <div className="space-y-2">
              {displayBuilds.map((b) => (
                <div key={b.id} className="border rounded-md">
                  <button
                    className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-accent/50 transition-colors"
                    onClick={() => setExpandedBuild(expandedBuild === b.id ? null : b.id)}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${statusColors[b.status] || "bg-gray-400"}`} />
                      <span className="font-mono text-sm font-medium">{b.image_tag}</span>
                      <Badge variant="outline" className="text-[10px]">{b.status}</Badge>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{b.git_ref}</span>
                      <span>{b.started_at ? new Date(b.started_at).toLocaleString() : "Pending"}</span>
                    </div>
                  </button>
                  {expandedBuild === b.id && (
                    <div className="border-t px-4 py-3">
                      {b.error && (
                        <p className="text-sm text-red-500 mb-2">{b.error}</p>
                      )}
                      <pre className="text-xs bg-muted p-3 rounded-md overflow-auto max-h-80 whitespace-pre-wrap">
                        {b.build_log || "No log output yet..."}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Workers Tab
// ---------------------------------------------------------------------------

function WorkersTab({
  deployments,
  builds,
  onAction,
}: {
  deployments: DeploymentStatus[];
  builds: ImageBuild[];
  onAction: () => void;
}) {
  const [deployDialogOpen, setDeployDialogOpen] = useState(false);
  const [selectedHosts, setSelectedHosts] = useState<string[]>([]);
  const [deployTag, setDeployTag] = useState("");
  const [deploying, setDeploying] = useState(false);

  const completedBuilds = builds.filter((b) => b.status === "completed");
  const allHostIds = deployments.map((d) => d.host_id);

  const openDeployDialog = (hostIds?: string[]) => {
    setSelectedHosts(hostIds || allHostIds);
    setDeployTag(completedBuilds[0]?.image_tag || "");
    setDeployDialogOpen(true);
  };

  const handleDeploy = async () => {
    if (!deployTag || selectedHosts.length === 0) {
      toast.error("Select an image tag and at least one host");
      return;
    }
    setDeploying(true);
    try {
      await apiFetch("/api/deployment/deploy", {
        method: "POST",
        body: JSON.stringify({ host_ids: selectedHosts, image_tag: deployTag }),
      });
      toast.success(`Deploying ${deployTag} to ${selectedHosts.length} host(s)`);
      setDeployDialogOpen(false);
      onAction();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Deploy failed");
    } finally {
      setDeploying(false);
    }
  };

  const handleStop = async (deploymentId: string) => {
    try {
      await apiFetch(`/api/deployment/deployments/${deploymentId}/stop`, { method: "POST" });
      toast.success("Stopping worker...");
      onAction();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Stop failed");
    }
  };

  const handleRestart = async (deploymentId: string) => {
    try {
      await apiFetch(`/api/deployment/deployments/${deploymentId}/restart`, { method: "POST" });
      toast.success("Restarting worker...");
      onAction();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Restart failed");
    }
  };

  const handleRemove = async (deploymentId: string) => {
    if (!confirm("Remove this worker? This will stop the container, remove images, and delete the deploy directory on the remote host.")) return;
    try {
      await apiFetch(`/api/deployment/deployments/${deploymentId}/remove`, { method: "POST" });
      toast.success("Removing worker...");
      onAction();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Remove failed");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => openDeployDialog()} disabled={deployments.length === 0 || completedBuilds.length === 0}>
          Deploy All
        </Button>
      </div>

      {deployments.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No Docker hosts found. Add the &quot;docker_host&quot; role to hosts that should run workers.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Host</th>
                  <th className="px-4 py-3 font-medium">Site</th>
                  <th className="px-4 py-3 font-medium">Image Tag</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Deployed</th>
                  <th className="px-4 py-3 font-medium">Health</th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {deployments.map((d) => (
                  <tr key={d.host_id} className="border-b last:border-0">
                    <td className="px-4 py-3">
                      <div className="font-medium">{d.display_name}</div>
                      <div className="text-xs text-muted-foreground">{d.hostname}</div>
                    </td>
                    <td className="px-4 py-3">
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{d.site}</code>
                    </td>
                    <td className="px-4 py-3">
                      {d.current_tag ? (
                        <span className="font-mono text-xs">{d.current_tag}</span>
                      ) : (
                        <span className="text-xs text-muted-foreground">--</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${statusColors[d.status] || "bg-gray-400"}`} />
                        <span className="text-xs">{d.status}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {d.deployed_at ? new Date(d.deployed_at).toLocaleString() : "--"}
                    </td>
                    <td className="px-4 py-3">
                      {d.last_health_check ? (
                        <span className="text-xs text-muted-foreground">
                          {new Date(d.last_health_check).toLocaleTimeString()}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">--</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => openDeployDialog([d.host_id])}>
                          Deploy
                        </Button>
                        {(d.status === "running" || d.status === "unhealthy") && (
                          <>
                            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => d.deployment_id && handleRestart(d.deployment_id)}>
                              Restart
                            </Button>
                            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs text-red-500 hover:text-red-600" onClick={() => d.deployment_id && handleStop(d.deployment_id)}>
                              Stop
                            </Button>
                          </>
                        )}
                        {d.deployment_id && d.status !== "running (compose)" && (
                          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs text-red-500 hover:text-red-600" onClick={() => handleRemove(d.deployment_id!)}>
                            Remove
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      <Dialog open={deployDialogOpen} onOpenChange={setDeployDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Deploy Workers</DialogTitle>
            <DialogDescription>
              Select an image tag to deploy to {selectedHosts.length} host{selectedHosts.length !== 1 ? "s" : ""}.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Image Tag</label>
              <Select value={deployTag} onValueChange={setDeployTag}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Select an image tag" />
                </SelectTrigger>
                <SelectContent>
                  {completedBuilds.map((b) => (
                    <SelectItem key={b.id} value={b.image_tag}>
                      {b.image_tag} ({new Date(b.completed_at!).toLocaleDateString()})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {completedBuilds.length === 0 && (
                <p className="text-[10px] text-amber-600 mt-1">
                  No completed builds found. Build an image first.
                </p>
              )}
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDeployDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleDeploy} disabled={deploying || !deployTag}>
                {deploying ? "Deploying..." : "Deploy"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Setup Wizard (shown when no registry is configured)
// ---------------------------------------------------------------------------

function SetupWizard({
  dockerHosts,
  onComplete,
}: {
  dockerHosts: DockerHost[];
  onComplete: () => void;
}) {
  const [step, setStep] = useState(1);

  const [url, setUrl] = useState("");
  const [project, setProject] = useState("updatr");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [buildHostId, setBuildHostId] = useState("");
  const [repoPath, setRepoPath] = useState("/opt/updatr");
  const [extDbUrl, setExtDbUrl] = useState("");
  const [extRedisUrl, setExtRedisUrl] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await apiFetch<{ success: boolean; message: string }>(
        "/api/deployment/registry/test",
        { method: "POST", body: JSON.stringify({ url, username, password }) }
      );
      setTestResult(result);
    } catch (e: unknown) {
      setTestResult({ success: false, message: e instanceof Error ? e.message : "Test failed" });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiFetch("/api/deployment/registry", {
        method: "POST",
        body: JSON.stringify({
          url,
          project,
          username,
          password,
          build_host_id: buildHostId,
          repo_path: repoPath,
          external_database_url: extDbUrl || null,
          external_redis_url: extRedisUrl || null,
        }),
      });
      toast.success("Registry configured successfully");
      onComplete();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const STEPS = ["Prerequisites", "Registry", "Build Host", "External URLs"] as const;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Deployment Setup</h1>
        <p className="text-muted-foreground mt-1">
          Configure your Harbor registry and build host to enable worker deployments.
        </p>
      </div>

      <div className="flex items-center gap-2 text-sm">
        {STEPS.map((label, i) => {
          const s = i + 1;
          return (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                  s === step
                    ? "bg-primary text-primary-foreground"
                    : s < step
                      ? "bg-primary/20 text-primary"
                      : "bg-muted text-muted-foreground"
                }`}
              >
                {s < step ? "\u2713" : s}
              </div>
              <span className={`whitespace-nowrap ${s === step ? "font-medium" : "text-muted-foreground"}`}>
                {label}
              </span>
              {s < STEPS.length && <div className="w-8 h-px bg-border shrink-0" />}
            </div>
          );
        })}
      </div>

      <Card>
        <CardContent className="pt-6">
          {step === 1 && (
            <div className="space-y-4">
              <p className="text-sm">
                Before configuring deployment, make sure the following prerequisites are in place.
              </p>
              <div className="space-y-3">
                <PrereqItem
                  title="Harbor registry is deployed and accessible"
                  done={null}
                >
                  Install Harbor on a machine reachable from this network. You&apos;ll need the HTTPS URL
                  (e.g. <code className="bg-muted px-1 rounded text-xs">https://harbor.yourdomain.com</code>).
                  <p className="mt-1.5">
                    <strong>TLS certificate trust:</strong> If Harbor uses a self-signed or internal CA certificate,
                    Docker on every build/deploy host must trust it. On each host:
                  </p>
                  <code className="block bg-muted px-2 py-1 rounded text-xs mt-1 font-mono whitespace-pre">{
`sudo mkdir -p /etc/docker/certs.d/harbor.yourdomain.com
# Copy your CA cert (the root CA that signed Harbor's cert)
sudo cp your-ca.crt /etc/docker/certs.d/harbor.yourdomain.com/ca.crt`
                  }</code>
                  <p className="mt-1">
                    No Docker restart needed. If you don&apos;t have the CA cert file, extract it:
                  </p>
                  <code className="block bg-muted px-2 py-1 rounded text-xs mt-1 font-mono whitespace-pre">{
`openssl s_client -showcerts -connect harbor.yourdomain.com:443 \\
  </dev/null 2>/dev/null | openssl x509 -outform PEM > ca.crt`
                  }</code>
                </PrereqItem>
                <PrereqItem
                  title="Docker hosts trust the Harbor TLS certificate"
                  done={null}
                >
                  If Harbor uses a self-signed or internal CA certificate, every Docker host that builds
                  or pulls images must trust it. On <strong>each</strong> Docker host (build host + deploy targets):
                  <code className="block bg-muted px-2 py-1 rounded text-xs mt-1.5 font-mono whitespace-pre">{
`sudo mkdir -p /etc/docker/certs.d/harbor.yourdomain.com
sudo cp your-ca.crt /etc/docker/certs.d/harbor.yourdomain.com/ca.crt
sudo systemctl restart docker`
                  }</code>
                  <p className="mt-1.5">
                    If you don&apos;t have the CA cert file, extract it from the running Harbor instance:
                  </p>
                  <code className="block bg-muted px-2 py-1 rounded text-xs mt-1 font-mono whitespace-pre">{
`openssl s_client -showcerts -connect harbor.yourdomain.com:443 \\
  </dev/null 2>/dev/null | openssl x509 -outform PEM > ca.crt`
                  }</code>
                  <p className="mt-1.5">
                    Without this, <code className="bg-muted px-1 rounded">docker login</code> and{" "}
                    <code className="bg-muted px-1 rounded">docker pull</code> will fail with{" "}
                    <em>&quot;x509: certificate signed by unknown authority&quot;</em>.
                  </p>
                </PrereqItem>
                <PrereqItem
                  title="Docker is installed on all deploy target hosts"
                  done={null}
                >
                  Every host where you want to deploy a remote worker needs Docker Engine and the
                  Compose plugin installed. On Ubuntu:
                  <code className="block bg-muted px-2 py-1 rounded text-xs mt-1.5 font-mono whitespace-pre">{
`sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \\
  -o /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) \\
  signed-by=/etc/apt/keyrings/docker.asc] \\
  https://download.docker.com/linux/ubuntu \\
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \\
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli \\
  containerd.io docker-compose-plugin`
                  }</code>
                  <p className="mt-2.5">
                    <strong className="text-foreground">Critical:</strong> The SSH user that updatr connects with
                    must be in the <code className="bg-muted px-1 rounded">docker</code> group, otherwise{" "}
                    <code className="bg-muted px-1 rounded">docker pull</code> and{" "}
                    <code className="bg-muted px-1 rounded">docker compose</code> will fail with{" "}
                    <em>&quot;permission denied while trying to connect to the Docker daemon socket&quot;</em>.
                  </p>
                  <code className="block bg-muted px-2 py-1 rounded text-xs mt-1.5 font-mono whitespace-pre">{
`# Replace 'youruser' with the SSH user from the credential
sudo usermod -aG docker youruser

# Apply immediately (or log out and back in)
newgrp docker`
                  }</code>
                  <p className="mt-1.5">
                    The SSH user must also have <strong className="text-foreground">sudo access</strong> (passwordless
                    or password-based with the password stored in the credential) for initial directory setup
                    on the deploy target.
                  </p>
                </PrereqItem>
                <PrereqItem
                  title="A project exists in Harbor"
                  done={null}
                >
                  Log into the Harbor web UI and create a project (e.g. <code className="bg-muted px-1 rounded text-xs">updatr</code>)
                  under <em>Projects</em> &rarr; <em>New Project</em>. Images will be pushed to
                  {" "}<code className="bg-muted px-1 rounded text-xs">harbor.example.com/updatr/worker:tag</code>.
                </PrereqItem>
                <PrereqItem
                  title="Harbor credentials are ready"
                  done={null}
                >
                  Either the <code className="bg-muted px-1 rounded text-xs">admin</code> password
                  from <code className="bg-muted px-1 rounded text-xs">harbor.yml</code>, or a robot account
                  with push + pull permissions created under your project&apos;s <em>Robot Accounts</em> tab.
                </PrereqItem>
                <PrereqItem
                  title="Build host is registered with the Docker Host role"
                  done={dockerHosts.length > 0}
                >
                  Go to <em>Hosts</em> &rarr; <em>Add Host</em> (or edit an existing one) and check
                  the <strong>Docker Host</strong> role. This machine needs Docker installed and SSH
                  access configured with a credential. Typically this is the same machine running Harbor.
                </PrereqItem>
                <PrereqItem
                  title="Git repository is cloned on the build host"
                  done={null}
                >
                  SSH into the build host and clone the updatr repo. The directory
                  must be owned by the same user that the SSH credential uses &mdash; the build
                  process runs <code className="bg-muted px-1 rounded text-xs">git pull</code> and
                  {" "}<code className="bg-muted px-1 rounded text-xs">docker build</code> as that user.
                  <code className="block bg-muted px-2 py-1 rounded text-xs mt-1.5 font-mono whitespace-pre">{
`# Clone as the SSH user (not root)
sudo mkdir -p /opt/updatr
sudo chown $(whoami):$(whoami) /opt/updatr
git clone https://your-repo-url.git /opt/updatr`
                  }</code>
                  <p className="mt-1.5">
                    If the repo was cloned as root, fix ownership:
                    {" "}<code className="bg-muted px-1 rounded text-xs">sudo chown -R youruser:youruser /opt/updatr</code>
                  </p>
                </PrereqItem>
                <PrereqItem
                  title="Postgres and Redis are network-accessible"
                  done={null}
                >
                  Remote workers connect to the control plane&apos;s database and Redis over the network.
                  Check that <code className="bg-muted px-1 rounded text-xs">POSTGRES_BIND</code> and
                  {" "}<code className="bg-muted px-1 rounded text-xs">REDIS_BIND</code> in your
                  {" "}<code className="bg-muted px-1 rounded text-xs">.env</code> are set to
                  {" "}<code className="bg-muted px-1 rounded text-xs">0.0.0.0</code> (or the LAN IP),
                  not <code className="bg-muted px-1 rounded text-xs">127.0.0.1</code>.
                </PrereqItem>
              </div>
              <div className="flex justify-end">
                <Button onClick={() => setStep(2)}>
                  I&apos;m Ready &mdash; Configure Registry
                </Button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Harbor URL</label>
                <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://harbor.yourdomain.com" className="mt-1" />
                <p className="text-[10px] text-muted-foreground mt-1">
                  The base URL of your Harbor instance, including the protocol (https://).
                </p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Username</label>
                  <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="admin or robot$name" className="mt-1" />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Password</label>
                  <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Project</label>
                <Input value={project} onChange={(e) => setProject(e.target.value)} placeholder="updatr" className="mt-1" />
              </div>
              <HelpBlurb title="Which credentials should I use?">
                <p>
                  <strong>Harbor admin account</strong> &mdash; Use the <code className="bg-muted px-1 rounded">admin</code> username and the password from your <code className="bg-muted px-1 rounded">harbor.yml</code>. This is the quickest way to get started.
                </p>
                <p>
                  <strong>Robot account (recommended for production)</strong> &mdash; In Harbor, navigate to your project &rarr; <em>Robot Accounts</em> &rarr; <em>New Robot Account</em>. Grant <code className="bg-muted px-1 rounded">push</code> and <code className="bg-muted px-1 rounded">pull</code> permissions. The username will look like <code className="bg-muted px-1 rounded">robot$updatr+deployer</code> and you&apos;ll receive a generated token as the password. Robot accounts are scoped to a single project, auditable, and can be revoked without affecting your admin login.
                </p>
                <p>
                  <strong>Project</strong> must already exist in Harbor. Log in to the Harbor web UI and create it under <em>Projects</em> &rarr; <em>New Project</em> if needed.
                </p>
              </HelpBlurb>
              <div className="flex items-center gap-3">
                <Button variant="outline" onClick={handleTest} disabled={testing || !url || !username || !password}>
                  {testing ? "Testing..." : "Test Connection"}
                </Button>
                {testResult && (
                  <span className={`text-sm ${testResult.success ? "text-green-600" : "text-red-500"}`}>
                    {testResult.message}
                  </span>
                )}
              </div>
              <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
                <Button onClick={() => setStep(3)} disabled={!url || !username || !password}>
                  Next
                </Button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Build Host</label>
                <Select value={buildHostId} onValueChange={setBuildHostId}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select a docker host" />
                  </SelectTrigger>
                  <SelectContent>
                    {dockerHosts.map((h) => (
                      <SelectItem key={h.id} value={h.id}>
                        {h.display_name} ({h.hostname})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {dockerHosts.length === 0 && (
                  <p className="text-xs text-amber-600 mt-2">
                    No hosts have the &quot;docker_host&quot; role. Go to <em>Hosts</em> and add the role first, then return here.
                  </p>
                )}
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Repository Path</label>
                <Input value={repoPath} onChange={(e) => setRepoPath(e.target.value)} placeholder="/opt/updatr" className="mt-1 font-mono" />
              </div>
              <HelpBlurb title="What is the build host and repo path?">
                <p>
                  The <strong>build host</strong> is a machine with Docker installed where worker images are built and pushed to Harbor. For simplicity, this is often the same machine running Harbor &mdash; the image push happens over localhost and is near-instant.
                </p>
                <p>
                  The <strong>repo path</strong> is the filesystem location on the build host where the updatr git repository has been cloned (e.g. <code className="bg-muted px-1 rounded">git clone https://... /opt/updatr</code>). The build process will SSH into this host, run <code className="bg-muted px-1 rounded">git pull</code> at that path, and then <code className="bg-muted px-1 rounded">docker build</code> using the Dockerfile there.
                </p>
                <p>
                  The host must already be registered in the <em>Hosts</em> page with the <code className="bg-muted px-1 rounded">docker_host</code> role and valid SSH credentials assigned.
                </p>
              </HelpBlurb>
              <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(2)}>Back</Button>
                <Button onClick={() => setStep(4)} disabled={!buildHostId}>Next</Button>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Remote workers need routable URLs to reach this control plane&apos;s database and Redis.
              </p>
              <div>
                <label className="text-xs font-medium text-muted-foreground">External Database URL</label>
                <Input value={extDbUrl} onChange={(e) => setExtDbUrl(e.target.value)} placeholder="postgresql+asyncpg://user:pass@10.0.0.1:5432/updatr" className="mt-1 font-mono text-xs" />
                <ConnectivityTest url={extDbUrl} endpoint="/api/deployment/test-database" label="Database" hint="Tests connectivity from the control plane." />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">External Redis URL</label>
                <Input value={extRedisUrl} onChange={(e) => setExtRedisUrl(e.target.value)} placeholder="redis://:password@10.0.0.1:6379/0" className="mt-1 font-mono text-xs" />
                <ConnectivityTest url={extRedisUrl} endpoint="/api/deployment/test-redis" label="Redis" hint="Tests connectivity from the control plane." />
              </div>
              <HelpBlurb title="Why do workers need these URLs?">
                <p>
                  The control plane&apos;s Docker Compose uses internal service names like <code className="bg-muted px-1 rounded">postgres</code> and <code className="bg-muted px-1 rounded">redis</code>. These names only resolve inside the control plane&apos;s Docker network &mdash; remote workers on other machines can&apos;t reach them.
                </p>
                <p>
                  Enter the LAN IP (or VPN address) of the machine running your Postgres and Redis instances. For example: <code className="bg-muted px-1 rounded">postgresql+asyncpg://updatr:yourpass@10.1.2.5:5432/updatr</code> and <code className="bg-muted px-1 rounded">redis://:yourpass@10.1.2.5:6379/0</code>.
                </p>
                <p>
                  <strong>Important:</strong> The Postgres and Redis ports must be accessible from the network. Check <code className="bg-muted px-1 rounded">POSTGRES_BIND</code> and <code className="bg-muted px-1 rounded">REDIS_BIND</code> in your control plane&apos;s <code className="bg-muted px-1 rounded">.env</code> &mdash; they default to <code className="bg-muted px-1 rounded">127.0.0.1</code> (localhost only). Change them to <code className="bg-muted px-1 rounded">0.0.0.0</code> or the specific LAN IP to allow remote connections.
                </p>
                <p>
                  You can skip these for now and configure them later from the Registry tab. Workers won&apos;t be deployable until both URLs are set.
                </p>
              </HelpBlurb>
              <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(3)}>Back</Button>
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? "Saving..." : "Complete Setup"}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
