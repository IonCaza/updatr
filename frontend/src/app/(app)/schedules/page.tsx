"use client";

import { useEffect, useState } from "react";
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
import { toast } from "sonner";

interface Schedule {
  id: string;
  name: string;
  cron_expression: string;
  is_active: boolean;
  reboot_policy: string;
  patch_categories: string[];
  last_run_at: string | null;
  created_at: string;
}

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    cron_expression: "0 2 * * 0",
  });

  const load = async () => {
    const data = await apiFetch<Schedule[]>("/api/schedules");
    setSchedules(data);
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/api/schedules", {
        method: "POST",
        body: JSON.stringify(form),
      });
      toast.success("Schedule created");
      setOpen(false);
      setForm({ name: "", cron_expression: "0 2 * * 0" });
      load();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  const toggleActive = async (id: string, current: boolean) => {
    await apiFetch(`/api/schedules/${id}`, {
      method: "PUT",
      body: JSON.stringify({ is_active: !current }),
    });
    load();
  };

  const handleDelete = async (id: string) => {
    await apiFetch(`/api/schedules/${id}`, { method: "DELETE" });
    toast.success("Schedule deleted");
    load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Schedules</h1>
          <p className="text-muted-foreground mt-1">Manage recurring patch schedules</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>New Schedule</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>New Schedule</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4">
              <Input
                placeholder="Schedule name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
              <Input
                placeholder="Cron expression (e.g. 0 2 * * 0)"
                value={form.cron_expression}
                onChange={(e) => setForm({ ...form, cron_expression: e.target.value })}
                required
              />
              <Button type="submit" className="w-full">
                Create Schedule
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {schedules.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No schedules configured. Create one to automate patching.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {schedules.map((s) => (
            <Card key={s.id}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div className="space-y-1">
                  <CardTitle className="text-base flex items-center gap-2">
                    {s.name}
                    <Badge variant={s.is_active ? "default" : "secondary"}>
                      {s.is_active ? "Active" : "Paused"}
                    </Badge>
                  </CardTitle>
                  <p className="text-sm text-muted-foreground font-mono">
                    {s.cron_expression}
                  </p>
                  {s.last_run_at && (
                    <p className="text-xs text-muted-foreground">
                      Last run: {new Date(s.last_run_at).toLocaleString()}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => toggleActive(s.id, s.is_active)}
                  >
                    {s.is_active ? "Pause" : "Resume"}
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleDelete(s.id)}
                  >
                    Delete
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
