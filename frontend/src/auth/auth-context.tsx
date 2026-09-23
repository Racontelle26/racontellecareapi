import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, clearToken, getToken, setToken } from "@/src/api/client";

export type User = { id: string; email: string; display_name: string; relationship_label?: string | null };
export type Member = { id: string; circle_id: string; display_name: string; relationship_label?: string | null; initials_color?: string; role?: string; daily_email?: boolean; status: string };
type AuthState = {
  loading: boolean;
  user: User | null;
  member: Member | null;
  hasCircle: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (payload: { email: string; password: string; display_name: string; relationship_label?: string }) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<boolean>;
};

const AuthContext = createContext<AuthState | undefined>(undefined);
type MeResponse = { user: User; member: Member | null; has_circle: boolean };

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [member, setMember] = useState<Member | null>(null);

  const refresh = useCallback(async () => {
    try {
      const me = await api.get<MeResponse>("/auth/me");
      setUser(me.user);
      setMember(me.member);
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) await clearToken();
      setUser(null);
      setMember(null);
      return false;
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      const token = await getToken();
      if (!active) return;
      if (token) await refresh();
      if (active) setLoading(false);
    })();
    return () => { active = false; };
  }, [refresh]);

  const signIn = useCallback(async (email: string, password: string) => {
    const res = await api.post<{ access_token: string; user: User }>("/auth/login", { email, password });
    await queryClient.cancelQueries();
    queryClient.clear();
    await setToken(res.access_token);
    await refresh();
  }, [queryClient, refresh]);

  const signUp = useCallback(async (payload: { email: string; password: string; display_name: string; relationship_label?: string }) => {
    const res = await api.post<{ access_token: string; user: User }>("/auth/register", payload);
    await queryClient.cancelQueries();
    queryClient.clear();
    await setToken(res.access_token);
    await refresh();
  }, [queryClient, refresh]);

  const signOut = useCallback(async () => {
    await queryClient.cancelQueries();
    queryClient.clear();
    await clearToken();
    setUser(null);
    setMember(null);
  }, [queryClient]);

  return <AuthContext.Provider value={{ loading, user, member, hasCircle: !!member, signIn, signUp, signOut, refresh }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}