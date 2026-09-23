import Constants from "expo-constants";
import { Platform } from "react-native";

import { storage } from "./utils/storage";
import type { AuthSession, AuthUser, Capsule, Question, Resident } from "./types";

const baseUrl = String(
  Constants.expoConfig?.extra?.backendUrl ?? process.env.EXPO_PUBLIC_BACKEND_URL ?? "",
).replace(/\/$/, "");

export const apiBaseUrl = baseUrl;
const SESSION_KEY = "racontelle.auth.session.v1";
const REMEMBERED_USER_KEY = "racontelle.auth.remembered-user.v1";
let sessionCache: AuthSession | null = null;
let refreshPromise: Promise<AuthSession | null> | null = null;
let sessionExpiredHandler: (() => void) | null = null;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function parseError(response: Response) {
  try {
    const body = await response.json();
    return body.detail ?? "Une erreur est survenue";
  } catch {
    return "Une erreur est survenue";
  }
}

async function saveSession(session: AuthSession | null) {
  sessionCache = session;
  if (session) {
    await storage.secureSet(SESSION_KEY, session);
    await storage.setItem(REMEMBERED_USER_KEY, session.user);
  }
  else await storage.secureRemove(SESSION_KEY);
}

async function rememberedUser() {
  const session = await storedSession();
  return session?.user ?? storage.getItem<AuthUser | null>(REMEMBERED_USER_KEY, null);
}

async function storedSession() {
  if (sessionCache) return sessionCache;
  sessionCache = await storage.secureGet<AuthSession | null>(SESSION_KEY, null);
  return sessionCache;
}

function platformHeaders() {
  return { "X-Client-Platform": Platform.OS === "web" ? "web" : "native" };
}

async function refreshSession(): Promise<AuthSession | null> {
  const existing = await storedSession();
  try {
    const response = await fetch(`${baseUrl}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...platformHeaders() },
      body: JSON.stringify({ refresh_token: existing?.refresh_token ?? null }),
    });
    if (!response.ok) {
      await saveSession(null);
      return null;
    }
    const next = await response.json() as AuthSession;
    await saveSession(next);
    return next;
  } catch {
    return existing;
  }
}

async function authorizedFetch(path: string, options: RequestInit = {}, retry = true) {
  if (!baseUrl) throw new ApiError(503, "Serveur temporaire indisponible");
  const session = await storedSession();
  const headers = new Headers(options.headers);
  headers.set("X-Client-Platform", Platform.OS === "web" ? "web" : "native");
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (session?.access_token) headers.set("Authorization", `Bearer ${session.access_token}`);
  let response = await fetch(`${baseUrl}/api${path}`, {
    ...options,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && retry) {
    refreshPromise ??= refreshSession().finally(() => { refreshPromise = null; });
    const refreshed = await refreshPromise;
    if (refreshed) {
      headers.set("Authorization", `Bearer ${refreshed.access_token}`);
      response = await fetch(`${baseUrl}/api${path}`, {
        ...options,
        headers,
        credentials: "include",
      });
    }
  }
  if (response.status === 401) {
    await saveSession(null);
    sessionExpiredHandler?.();
  }
  return response;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await authorizedFetch(path, options);
  if (!response.ok) throw new ApiError(response.status, await parseError(response));
  return response.json() as Promise<T>;
}

async function uploadAudio<T>(path: string, uri: string): Promise<T> {
  const name = Platform.OS === "web" ? "recording.webm" : "recording.m4a";
  const type = Platform.OS === "web" ? "audio/webm" : "audio/m4a";
  const form = new FormData();
  if (Platform.OS === "web") {
    const blob = await (await fetch(uri)).blob();
    form.append("file", blob, name);
  } else {
    form.append("file", { uri, name, type } as any);
  }
  const response = await authorizedFetch(path, { method: "POST", body: form });
  if (!response.ok) throw new ApiError(response.status, await parseError(response));
  return response.json() as Promise<T>;
}

async function beginAuth(path: string, body: Record<string, string>) {
  const response = await fetch(`${baseUrl}/api/auth/${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...platformHeaders() },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new ApiError(response.status, await parseError(response));
  const session = await response.json() as AuthSession;
  await saveSession(session);
  return session;
}

export const authApi = {
  onSessionExpired: (handler: (() => void) | null) => { sessionExpiredHandler = handler; },
  register: (body: { email: string; password: string; full_name: string; establishment_name: string }) => beginAuth("register", body),
  login: (email: string, password: string) => beginAuth("login", { email, password }),
  rememberedUser,
  logout: async () => {
    const session = await storedSession();
    if (session) {
      await authorizedFetch("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: session.refresh_token ?? null }),
      }, false).catch(() => null);
    }
    await saveSession(null);
    await storage.removeItem(REMEMBERED_USER_KEY);
  },
  current: storedSession,
};

export const api = {
  residents: () => request<Resident[]>("/residents"),
  capsules: () => request<Capsule[]>("/capsules"),
  createResident: (display_name: string) => request<Resident>("/residents", { method: "POST", body: JSON.stringify({ display_name, consent_status: "obtained" }) }),
  questions: () => request<Question[]>("/questions?limit=100"),
  saveCapsule: (capsule: Omit<Capsule, "id" | "status" | "synced">) => request<Capsule>("/capsules", { method: "POST", body: JSON.stringify(capsule) }),
  deleteCapsule: (id: string) => request<{ deleted: boolean }>(`/capsules/${id}`, { method: "DELETE" }),
  uploadCapsuleAudio: (id: string, uri: string) => uploadAudio<{ uploaded: boolean; remaining: number }>(`/capsules/${id}/audio`, uri),
  transcribeCapsule: (id: string, uri: string) => uploadAudio<{ transcription: string }>(`/capsules/${id}/transcribe`, uri),
  shareCapsule: (id: string) => request<{ token: string; share_id: string; path: string; expires_at: string }>(`/capsules/${id}/share`, { method: "POST" }),
  revokeShare: (id: string) => request<{ revoked: boolean }>(`/shares/${id}`, { method: "DELETE" }),
  exportResidentPath: (id: string) => `/residents/${id}/export`,
  carnetResidentPath: (id: string) => `/residents/${id}/carnet`,
  download: (path: string) => authorizedFetch(path),
  authorizationHeaders: async (): Promise<Record<string, string>> => {
    const session = await storedSession();
    return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};
  },
  mergeResidents: (keep_id: string, merge_ids: string[]) => request<{ merged: number }>("/residents/merge", { method: "POST", body: JSON.stringify({ keep_id, merge_ids }) }),
  tts: (text: string) => request<{ path: string }>("/tts", { method: "POST", body: JSON.stringify({ text }) }),
  deleteResident: (id: string) => request<{ deleted: boolean }>(`/residents/${id}`, { method: "DELETE" }),
  updateResident: (id: string, display_name: string) => request<Resident>(`/residents/${id}`, { method: "PATCH", body: JSON.stringify({ display_name }) }),
  updateCapsule: (id: string, title: string) => request<Capsule>(`/capsules/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  assignCapsule: (id: string, resident_id: string) => request<Capsule>(`/capsules/${id}/assign?resident_id=${encodeURIComponent(resident_id)}`, { method: "PATCH" }),
  createMember: (body: { email: string; password: string; full_name: string }) => request<AuthUser>("/auth/members", { method: "POST", body: JSON.stringify(body) }),
};