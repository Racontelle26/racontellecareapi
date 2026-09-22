import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { AppState, Platform } from "react-native";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, clearToken, getToken, setToken } from "@/src/api/client";
import { authenticateFingerprint, getFingerprintAvailability, getFingerprintEnabled, saveFingerprintEnabled } from "@/src/auth/biometric";

export type User = { id: string; email: string; display_name: string; relationship_label?: string | null };
export type Member = { id: string; circle_id: string; display_name: string; relationship_label?: string | null; initials_color?: string; role?: string; daily_email?: boolean; status: string };
type UnlockResult = { success: boolean; cancelled?: boolean; expired?: boolean };

type AuthState = {
  loading: boolean;
  user: User | null;
  member: Member | null;
  hasCircle: boolean;
  locked: boolean;
  biometricAvailable: boolean;
  biometricEnabled: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (payload: { email: string; password: string; display_name: string; relationship_label?: string }) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<boolean>;
  setBiometricEnabled: (enabled: boolean) => Promise<boolean>;
  unlockWithFingerprint: (pinPrompt?: boolean) => Promise<UnlockResult>;
  usePasswordInstead: () => Promise<void>;
};

const AuthContext = createContext<AuthState | undefined>(undefined);
type MeResponse = { user: User; member: Member | null; has_circle: boolean };

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [member, setMember] = useState<Member | null>(null);
  const [locked, setLocked] = useState(false);
  const [biometricAvailable, setBiometricAvailable] = useState(false);
  const [biometricEnabled, setBiometricEnabledState] = useState(false);

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
      const [token, fingerprintEnabled, availability] = await Promise.all([
        getToken(), getFingerprintEnabled(), getFingerprintAvailability(),
      ]);
      if (!active) return;
      setBiometricAvailable(availability.available);
      setBiometricEnabledState(fingerprintEnabled);
      if (token && fingerprintEnabled && Platform.OS !== "web") {
        setLocked(true);
      } else if (token) {
        await refresh();
      }
      if (active) setLoading(false);
    })();
    return () => { active = false; };
  }, [refresh]);

  useEffect(() => {
    let backgroundAt = 0;
    const subscription = AppState.addEventListener("change", (nextState) => {
      if (nextState === "background" || nextState === "inactive") backgroundAt = Date.now();
      if (nextState === "active" && backgroundAt && Date.now() - backgroundAt >= 30_000 && biometricEnabled && user) {
        setLocked(true);
      }
    });
    return () => subscription.remove();
  }, [biometricEnabled, user]);

  const signIn = useCallback(async (email: string, password: string) => {
    const res = await api.post<{ access_token: string; user: User }>("/auth/login", { email, password });
    await queryClient.cancelQueries();
    queryClient.clear();
    await setToken(res.access_token);
    setLocked(false);
    await refresh();
  }, [queryClient, refresh]);

  const signUp = useCallback(async (payload: { email: string; password: string; display_name: string; relationship_label?: string }) => {
    const res = await api.post<{ access_token: string; user: User }>("/auth/register", payload);
    await queryClient.cancelQueries();
    queryClient.clear();
    await setToken(res.access_token);
    setLocked(false);
    await refresh();
  }, [queryClient, refresh]);

  const signOut = useCallback(async () => {
    await queryClient.cancelQueries();
    queryClient.clear();
    await clearToken();
    setLocked(false);
    setUser(null);
    setMember(null);
  }, [queryClient]);

  const setBiometricEnabled = useCallback(async (enabled: boolean) => {
    if (!enabled) {
      await saveFingerprintEnabled(false);
      setBiometricEnabledState(false);
      return true;
    }
    const availability = await getFingerprintAvailability();
    setBiometricAvailable(availability.available);
    if (!availability.available) return false;
    const result = await authenticateFingerprint(false);
    if (!result.success) return false;
    const saved = await saveFingerprintEnabled(true);
    if (!saved) return false;
    setBiometricEnabledState(true);
    return true;
  }, []);

  const unlockWithFingerprint = useCallback(async (pinPrompt = false): Promise<UnlockResult> => {
    const result = await authenticateFingerprint(pinPrompt);
    if (!result.success) {
      return { success: false, cancelled: result.error === "user_cancel" || result.error === "system_cancel" || result.error === "app_cancel" };
    }
    const valid = await refresh();
    setLocked(false);
    return valid ? { success: true } : { success: false, expired: true };
  }, [refresh]);

  const usePasswordInstead = useCallback(async () => {
    await queryClient.cancelQueries();
    queryClient.clear();
    await clearToken();
    setUser(null);
    setMember(null);
    setLocked(false);
  }, [queryClient]);

  return <AuthContext.Provider value={{ loading, user, member, hasCircle: !!member, locked, biometricAvailable, biometricEnabled, signIn, signUp, signOut, refresh, setBiometricEnabled, unlockWithFingerprint, usePasswordInstead }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}