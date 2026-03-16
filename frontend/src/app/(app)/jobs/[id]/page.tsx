"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface JobDetail {
  id: string;
  status: string;
  job_type: string;
  host_ids: string[];
  started_at: string | null;
  completed_at: string | null;
  host_results: Record<string, unknown>;
  created_at: string;
}

interface LogEntry {
  type: string;
  event?: string;
  host?: string;
  task?: string;
  status?: string;
  output?: { stdout?: string; stderr?: string; msg?: string };
  timestamp?: string;
}

interface PersistedEvent {
  id: string;
  host: string;
  task: string;
  status: string;
  output: Record<string, string>;
  timestamp: string;
}

const STATUS_COLORS: Record<string, string> = {
  ok: "text-green-400",
  failed: "text-red-400",
  unreachable: "text-yellow-400",
  skipped: "text-zinc-500",
  task_start: "text-blue-400",
  start: "text-zinc-400",
};

function LogLine({ entry }: { entry: LogEntry }) {
  const color = STATUS_COLORS[entry.status || ""] || "text-zinc-300";
  const time = entry.timestamp
    ? new Date(entry.timestamp).toLocaleTimeString()
    : "";
  const host = entry.host || "";
  const task = entry.task || "";
  const detail =
    entry.output?.msg || entry.output?.stdout || entry.output?.stderr || "";

  if (entry.type === "status") {
    return (
      <div className="text-blue-400 font-semibold py-1">
        Job status: {entry.status}
      </div>
    );
  }

  return (
    <div className="py-0.5 font-mono text-xs leading-relaxed">
      <span className="text-zinc-500">{time}</span>{" "}
      <span className={color}>[{entry.status}]</span>{" "}
      {host && <span className="text-cyan-400">{host}</span>}{" "}
      {task && <span className="text-zinc-300">{task}</span>}
      {detail && (
        <div className="pl-16 text-zinc-500 whitespace-pre-wrap break-all">
          {detail}
        </div>
      )}
    </div>
  );
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const loadJob = useCallback(async () => {
    try {
      const j = await apiFetch<JobDetail>(`/api/jobs/${id}`);
      setJob(j);
      return j;
    } catch {
      return null;
    }
  }, [id]);

  const loadPersistedEvents = useCallback(async () => {
    try {
      const events = await apiFetch<PersistedEvent[]>(
        `/api/jobs/${id}/events`
      );
      setLogs(
        events.map((e) => ({
          type: "event",
          host: e.host,
          task: e.task,
          status: e.status,
          output: e.output,
          timestamp: e.timestamp,
        }))
      );
    } catch {
      /* no events yet */
    }
  }, [id]);

  useEffect(() => {
    let es: EventSource | null = null;
    let cancelled = false;

    loadJob().then((j) => {
      if (cancelled || !j) return;
      if (j.status === "running" || j.status === "queued") {
        const token = localStorage.getItem("updatr_token");
        const baseUrl =
          process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        es = new EventSource(
          `${baseUrl}/api/jobs/${id}/stream?token=${token}`
        );
        setConnected(true);

        es.onmessage = (event) => {
          try {
            const data: LogEntry = JSON.parse(event.data);
            if (data.type === "done") {
              es?.close();
              setConnected(false);
              loadJob();
              return;
            }
            setLogs((prev) => [...prev, data]);
          } catch {
            /* ignore parse errors */
          }
        };

        es.onerror = () => {
          es?.close();
          setConnected(false);
          loadPersistedEvents();
          loadJob();
        };
      } else {
        loadPersistedEvents();
      }
    });

    return () => {
      cancelled = true;
      es?.close();
      setConnected(false);
    };
  }, [id, loadJob, loadPersistedEvents]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Button variant="ghost" size="sm" onClick={() => router.push("/jobs")}>
            &larr; Back to Jobs
          </Button>
          <h1 className="text-2xl font-bold mt-2">
            Job Detail
            {job && (
              <Badge
                variant={
                  job.status === "completed"
                    ? "default"
                    : job.status === "failed"
                    ? "destructive"
                    : "secondary"
                }
                className="ml-3 align-middle"
              >
                {job.status}
              </Badge>
            )}
          </h1>
          {job && (
            <p className="text-sm text-muted-foreground mt-1">
              {job.host_ids.length} host(s) {"\u00B7"} Created{" "}
              {new Date(job.created_at).toLocaleString()}
              {job.completed_at &&
                ` \u00B7 Completed ${new Date(job.completed_at).toLocaleString()}`}
            </p>
          )}
        </div>
        {connected && (
          <Badge variant="outline" className="animate-pulse border-green-500 text-green-500">
            Live
          </Badge>
        )}
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Ansible Log</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="bg-zinc-950 rounded-lg p-4 max-h-[600px] overflow-y-auto">
            {logs.length === 0 ? (
              <p className="text-zinc-500 text-sm">
                {connected
                  ? "Waiting for events..."
                  : "No log events recorded for this job."}
              </p>
            ) : (
              logs.map((entry, i) => <LogLine key={i} entry={entry} />)
            )}
            <div ref={logEndRef} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
