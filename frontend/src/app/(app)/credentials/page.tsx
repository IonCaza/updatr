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

interface Credential {
  id: string;
  name: string;
  type: string;
  username: string;
  created_at: string;
  updated_at: string;
}

const TYPES = [
  { value: "ssh-password", label: "SSH Password" },
  { value: "ssh-key", label: "SSH Key" },
  { value: "winrm-password", label: "WinRM Password" },
];

const EMPTY_FORM = {
  name: "",
  type: "ssh-password",
  username: "",
  password: "",
  private_key: "",
  passphrase: "",
};

export default function CredentialsPage() {
  const [creds, setCreds] = useState<Credential[]>([]);
  const [open, setOpen] = useState(false);
  const [editingCred, setEditingCred] = useState<Credential | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  const load = useCallback(async () => {
    const data = await apiFetch<Credential[]>("/api/credentials");
    setCreds(data);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openCreateDialog = () => {
    setEditingCred(null);
    setForm({ ...EMPTY_FORM });
    setOpen(true);
  };

  const openEditDialog = (c: Credential) => {
    setEditingCred(c);
    setForm({
      name: c.name,
      type: c.type,
      username: c.username,
      password: "",
      private_key: "",
      passphrase: "",
    });
    setOpen(true);
  };

  const handleDialogClose = (isOpen: boolean) => {
    setOpen(isOpen);
    if (!isOpen) setEditingCred(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingCred) {
        const payload: Record<string, string> = {};
        if (form.name !== editingCred.name) payload.name = form.name;
        if (form.username !== editingCred.username)
          payload.username = form.username;
        if (form.password) payload.password = form.password;
        if (form.private_key) payload.private_key = form.private_key;
        if (form.passphrase) payload.passphrase = form.passphrase;

        await apiFetch(`/api/credentials/${editingCred.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast.success("Credential updated");
      } else {
        await apiFetch("/api/credentials", {
          method: "POST",
          body: JSON.stringify({
            name: form.name,
            type: form.type,
            username: form.username,
            password: form.password || undefined,
            private_key: form.private_key || undefined,
            passphrase: form.passphrase || undefined,
          }),
        });
        toast.success("Credential created");
      }
      setOpen(false);
      setEditingCred(null);
      setForm({ ...EMPTY_FORM });
      load();
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : "Failed to save credential"
      );
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiFetch(`/api/credentials/${id}`, { method: "DELETE" });
      toast.success("Credential deleted");
      load();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  const typeLabel =
    TYPES.find((t) => t.value === form.type)?.label ?? form.type;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Credentials</h1>
          <p className="text-muted-foreground mt-1">
            Manage SSH keys and connection passwords
          </p>
        </div>
        <Button onClick={openCreateDialog}>Add Credential</Button>
      </div>

      {creds.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No credentials yet. Add one to connect to your hosts.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {creds.map((c) => (
            <Card key={c.id}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    {c.name}
                    <Badge variant="secondary" className="text-xs">
                      {TYPES.find((t) => t.value === c.type)?.label ?? c.type}
                    </Badge>
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">{c.username}</p>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openEditDialog(c)}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDelete(c.id)}
                  >
                    Delete
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={handleDialogClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingCred ? "Edit Credential" : "New Credential"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              placeholder="Name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
            {editingCred ? (
              <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
                Type: <span className="font-medium text-foreground">{typeLabel}</span>
                <span className="ml-2 text-xs">(cannot be changed)</span>
              </div>
            ) : (
              <Select
                value={form.type}
                onValueChange={(v) => setForm({ ...form, type: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <Input
              placeholder="Username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              required
            />
            {form.type !== "ssh-key" && (
              <Input
                type="password"
                placeholder={
                  editingCred
                    ? "Password (leave empty to keep unchanged)"
                    : "Password"
                }
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            )}
            {form.type === "ssh-key" && (
              <>
                <textarea
                  className="w-full rounded-md border bg-background p-2 text-sm font-mono min-h-[100px]"
                  placeholder={
                    editingCred
                      ? "Paste new private key (leave empty to keep unchanged)"
                      : "Paste private key"
                  }
                  value={form.private_key}
                  onChange={(e) =>
                    setForm({ ...form, private_key: e.target.value })
                  }
                />
                <Input
                  type="password"
                  placeholder={
                    editingCred
                      ? "Passphrase (leave empty to keep unchanged)"
                      : "Passphrase (optional)"
                  }
                  value={form.passphrase}
                  onChange={(e) =>
                    setForm({ ...form, passphrase: e.target.value })
                  }
                />
              </>
            )}
            <Button type="submit" className="w-full">
              {editingCred ? "Save Changes" : "Create"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
