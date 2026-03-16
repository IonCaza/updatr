"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";

interface User {
  id: string;
  username: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  setup: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const fetchMe = useCallback(async (accessToken: string) => {
    const res = await fetch(`${API}/api/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (res.ok) {
      const data = await res.json();
      setUser(data);
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem("updatr_token");
    if (stored) {
      setToken(stored);
      fetchMe(stored).catch(() => {
        localStorage.removeItem("updatr_token");
        localStorage.removeItem("updatr_refresh");
      });
    }
    setLoading(false);
  }, [fetchMe]);

  const login = async (username: string, password: string) => {
    const res = await fetch(`${API}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new Error("Invalid credentials");
    const data = await res.json();
    localStorage.setItem("updatr_token", data.access_token);
    localStorage.setItem("updatr_refresh", data.refresh_token);
    setToken(data.access_token);
    await fetchMe(data.access_token);
    router.push("/dashboard");
  };

  const setup = async (username: string, password: string) => {
    const res = await fetch(`${API}/api/auth/setup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Setup failed");
    }
    const data = await res.json();
    localStorage.setItem("updatr_token", data.access_token);
    localStorage.setItem("updatr_refresh", data.refresh_token);
    setToken(data.access_token);
    await fetchMe(data.access_token);
    router.push("/dashboard");
  };

  const logout = () => {
    localStorage.removeItem("updatr_token");
    localStorage.removeItem("updatr_refresh");
    setToken(null);
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, setup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
