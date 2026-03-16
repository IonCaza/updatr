"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface HostCompliance {
  host_id: string;
  hostname: string;
  display_name: string;
  os_type: string;
  is_compliant: boolean;
  is_reachable: boolean;
  reboot_required: boolean;
  pending_updates: Array<{
    name: string;
    severity?: string;
    kb_number?: string;
    published_date?: string;
  }>;
  scanned_at: string | null;
}

export default function HostCompliancePage() {
  const params = useParams();
  const [data, setData] = useState<HostCompliance | null>(null);

  useEffect(() => {
    if (params.id) {
      apiFetch<HostCompliance>(`/api/compliance/hosts/${params.id}`)
        .then(setData)
        .catch(() => {});
    }
  }, [params.id]);

  if (!data) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        Loading host compliance details...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{data.display_name}</h1>
        <p className="text-muted-foreground">{data.hostname}</p>
      </div>

      <div className="flex gap-2 flex-wrap">
        <Badge variant="secondary">{data.os_type}</Badge>
        <Badge variant={data.is_compliant ? "default" : "destructive"}>
          {data.is_compliant ? "Compliant" : "Non-Compliant"}
        </Badge>
        {!data.is_reachable && <Badge variant="destructive">Unreachable</Badge>}
        {data.reboot_required && <Badge variant="secondary">Reboot Required</Badge>}
      </div>

      {data.scanned_at && (
        <p className="text-sm text-muted-foreground">
          Last scan: {new Date(data.scanned_at).toLocaleString()}
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            Pending Updates ({data.pending_updates.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.pending_updates.length === 0 ? (
            <p className="text-muted-foreground">No pending updates.</p>
          ) : (
            <div className="space-y-2">
              {data.pending_updates.map((u, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-2 rounded border"
                >
                  <div>
                    <p className="font-medium text-sm">{u.name}</p>
                    {u.kb_number && (
                      <p className="text-xs text-muted-foreground">{u.kb_number}</p>
                    )}
                  </div>
                  {u.severity && (
                    <Badge
                      variant={
                        u.severity === "Critical"
                          ? "destructive"
                          : u.severity === "Important"
                          ? "default"
                          : "secondary"
                      }
                    >
                      {u.severity}
                    </Badge>
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
