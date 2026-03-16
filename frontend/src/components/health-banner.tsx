"use client";

import { useEffect, useState, useRef } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const POLL_INTERVAL_MS = 5000;
const POLL_TIMEOUT_MS = 3000;

export function HealthBanner() {
  const [offline, setOffline] = useState(false);
  const [downSince, setDownSince] = useState<Date | null>(null);
  const wasOffline = useRef(false);

  useEffect(() => {
    let mounted = true;

    const check = async () => {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), POLL_TIMEOUT_MS);
        const res = await fetch(`${API_BASE}/health`, {
          signal: controller.signal,
        });
        clearTimeout(timeout);

        if (mounted) {
          if (res.ok) {
            if (wasOffline.current) {
              wasOffline.current = false;
              setDownSince(null);
            }
            setOffline(false);
          } else {
            if (!wasOffline.current) {
              wasOffline.current = true;
              setDownSince(new Date());
            }
            setOffline(true);
          }
        }
      } catch {
        if (mounted) {
          if (!wasOffline.current) {
            wasOffline.current = true;
            setDownSince(new Date());
          }
          setOffline(true);
        }
      }
    };

    check();
    const interval = setInterval(check, POLL_INTERVAL_MS);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  if (!offline) return null;

  const elapsed = downSince
    ? Math.round((Date.now() - downSince.getTime()) / 1000)
    : 0;
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;

  return (
    <div className="sticky top-0 z-50 bg-red-600 text-white px-4 py-2 text-center text-sm font-medium shadow-md">
      Control plane offline
      {downSince && (
        <span className="ml-2 opacity-80">
          ({mins > 0 ? `${mins}m ` : ""}{secs}s)
        </span>
      )}
      <span className="ml-2 opacity-80">
        -- Reconnecting automatically...
      </span>
    </div>
  );
}
