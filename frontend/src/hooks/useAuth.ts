import { useState, useEffect, useCallback } from "react";
import { authApi } from "@/lib/api";
import type { User } from "@/types";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    try {
      const u = await authApi.me();
      setUser(u);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = async (email: string, password: string) => {
    const u = await authApi.login(email, password);
    setUser(u);
    return u;
  };

  const register = async (username: string, email: string, password: string) => {
    const u = await authApi.register(username, email, password);
    return u;
  };

  const logout = async () => {
    await authApi.logout();
    setUser(null);
  };

  return { user, loading, login, register, logout, refetch: fetchUser };
}
