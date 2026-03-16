"use client";

import { useEffect, useState, useCallback } from "react";
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
import { toast } from "sonner";

interface Site {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  subnets: string[];
  is_default: boolean;
  host_count: number;
  created_at: string;
  updated_at: string;
}

export default function SitesPage() {
  const [sites, setSites] = useState<Site[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Site | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<Site | null>(null);

  const [formName, setFormName] = useState("");
  const [formDisplayName, setFormDisplayName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formSubnets, setFormSubnets] = useState("");
  const [formIsDefault, setFormIsDefault] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadSites = useCallback(async () => {
    try {
      const data = await apiFetch<Site[]>("/api/sites");
      setSites(data);
    } catch {
      toast.error("Failed to load sites");
    }
  }, []);

  useEffect(() => {
    loadSites();
  }, [loadSites]);

  const openCreate = () => {
    setEditing(null);
    setFormName("");
    setFormDisplayName("");
    setFormDescription("");
    setFormSubnets("");
    setFormIsDefault(false);
    setDialogOpen(true);
  };

  const openEdit = (site: Site) => {
    setEditing(site);
    setFormName(site.name);
    setFormDisplayName(site.display_name);
    setFormDescription(site.description || "");
    setFormSubnets(site.subnets.join("\n"));
    setFormIsDefault(site.is_default);
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!formName.trim() || !formDisplayName.trim()) {
      toast.error("Name and display name are required");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: formName.trim(),
        display_name: formDisplayName.trim(),
        description: formDescription.trim() || null,
        subnets: formSubnets
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        is_default: formIsDefault,
      };

      if (editing) {
        await apiFetch(`/api/sites/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast.success("Site updated");
      } else {
        await apiFetch("/api/sites", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast.success("Site created");
      }
      setDialogOpen(false);
      await loadSites();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to save site");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    try {
      await apiFetch(`/api/sites/${deleteConfirm.id}`, { method: "DELETE" });
      toast.success("Site deleted");
      setDeleteConfirm(null);
      await loadSites();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to delete site");
    }
  };

  const handleRedetect = async (siteId: string) => {
    try {
      const res = await apiFetch<{ assigned: number }>(
        `/api/sites/${siteId}/detect`,
        { method: "POST" }
      );
      toast.success(
        res.assigned > 0
          ? `Reassigned ${res.assigned} host${res.assigned !== 1 ? "s" : ""}`
          : "No hosts reassigned"
      );
      await loadSites();
    } catch (e: unknown) {
      toast.error(
        e instanceof Error ? e.message : "Failed to run detection"
      );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Sites</h1>
          <p className="text-muted-foreground mt-1">
            Manage sites, subnets, and worker queue mapping
          </p>
        </div>
        <Button onClick={openCreate}>New Site</Button>
      </div>

      {sites.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No sites configured. Create one to get started.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {sites.map((site) => (
            <Card key={site.id} className="relative">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    {site.display_name}
                    {site.is_default && (
                      <Badge variant="outline" className="text-[10px]">
                        default
                      </Badge>
                    )}
                  </CardTitle>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => openEdit(site)}
                    >
                      Edit
                    </Button>
                    {!site.is_default && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs text-red-500 hover:text-red-600"
                        onClick={() => setDeleteConfirm(site)}
                      >
                        Delete
                      </Button>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Queue</span>
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                    {site.name}
                  </code>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Hosts</span>
                  <span className="font-medium">{site.host_count}</span>
                </div>
                {site.subnets.length > 0 ? (
                  <div>
                    <span className="text-xs text-muted-foreground">
                      Subnets
                    </span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {site.subnets.map((s) => (
                        <Badge
                          key={s}
                          variant="outline"
                          className="text-[10px] font-mono"
                        >
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground italic">
                    No subnets configured
                  </p>
                )}
                {site.description && (
                  <p className="text-xs text-muted-foreground">
                    {site.description}
                  </p>
                )}
                {site.subnets.length > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full text-xs"
                    onClick={() => handleRedetect(site.id)}
                  >
                    Re-detect hosts
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit Site" : "New Site"}
            </DialogTitle>
            <DialogDescription>
              {editing
                ? "Update the site configuration."
                : "Create a new site to group hosts and route work to workers."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div>
              <label className="text-xs font-medium text-muted-foreground">
                Queue Name
              </label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. site-a, datacenter-1"
                className="mt-1"
                disabled={!!editing}
              />
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Used as the Celery queue name. Cannot be changed after creation.
              </p>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">
                Display Name
              </label>
              <Input
                value={formDisplayName}
                onChange={(e) => setFormDisplayName(e.target.value)}
                placeholder="e.g. Site A, Datacenter 1"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">
                Description
              </label>
              <Input
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                placeholder="Optional description"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">
                Subnets (one per line)
              </label>
              <textarea
                value={formSubnets}
                onChange={(e) => setFormSubnets(e.target.value)}
                placeholder={"192.168.1.0/24\n10.0.0.0/16"}
                rows={3}
                className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Hosts with IPs in these subnets will be auto-assigned to this
                site.
              </p>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={formIsDefault}
                onChange={(e) => setFormIsDefault(e.target.checked)}
                className="rounded"
              />
              Default site (fallback when no subnet matches)
            </label>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? "Saving..." : editing ? "Update" : "Create"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog
        open={!!deleteConfirm}
        onOpenChange={() => setDeleteConfirm(null)}
      >
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Site</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete{" "}
              <strong>{deleteConfirm?.display_name}</strong>?
              {deleteConfirm && deleteConfirm.host_count > 0 && (
                <span className="block mt-1 text-amber-600">
                  {deleteConfirm.host_count} host
                  {deleteConfirm.host_count !== 1 ? "s" : ""} will be
                  reassigned to the default site.
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 mt-4">
            <Button
              variant="outline"
              onClick={() => setDeleteConfirm(null)}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
