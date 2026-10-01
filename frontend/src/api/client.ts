import { useEffect, useState } from "react";
import Constants from "expo-constants";
import { File } from "expo-file-system";
import { storage } from "@/src/utils/storage";

// Expo's fetch (installed globally from SDK 52) rejects React Native's `{ uri, name, type }` FormData parts
// ("Unsupported FormDataPart implementation"): a local file must be appended as an expo-file-system File.
export function localFilePart(uri: string): Blob {
  return new File(uri) as unknown as Blob;
}

// EXPO_PUBLIC_BACKEND_URL=metro (development only): the API is reached through the Metro server that
// serves the app (see RACONTELLE_API_PROXY in metro.config.js), e.g. over an `expo start --tunnel` URL.
function resolveBackendOrigin(): string {
  const configured = process.env.EXPO_PUBLIC_BACKEND_URL ?? "";
  if (configured !== "metro") return configured;
  const hostUri = Constants.expoConfig?.hostUri ?? "";
  const host = hostUri.split("/")[0];
  const secure = host.endsWith(".exp.direct") || !host.includes(":");
  return `${secure ? "https" : "http"}://${host}`;
}

export const BACKEND_ORIGIN = resolveBackendOrigin();
const BASE = `${BACKEND_ORIGIN}/api`;
export const TOKEN_KEY = "racontelle_token";

export async function getToken(): Promise<string | null> {
  return storage.secureGet<string | null>(TOKEN_KEY, null);
}

export async function setToken(token: string): Promise<void> {
  await storage.secureSet(TOKEN_KEY, token);
}

export async function clearToken(): Promise<void> {
  await storage.secureRemove(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) || "Une erreur est survenue";
    throw new ApiError(typeof msg === "string" ? msg : "Erreur", res.status);
  }
  return data as T;
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  del: <T,>(path: string) => request<T>(path, { method: "DELETE" }),
};

export async function audioUrl(capsuleId: string): Promise<string> {
  const token = await getToken();
  return `${BASE}/capsules/${capsuleId}/audio?token=${token}`;
}

export { BASE as API_BASE };

// Protected media (photos) are read with the session token in the query string.
let cachedMediaToken: string | null = null;

export function useMediaToken(): string | null {
  const [token, setTok] = useState<string | null>(cachedMediaToken);
  useEffect(() => {
    let active = true;
    getToken().then((value) => {
      cachedMediaToken = value;
      if (active) setTok(value);
    });
    return () => {
      active = false;
    };
  }, []);
  return token;
}

export function mediaUrl(path: string | null | undefined, token: string | null): string | null {
  if (!path || !token) return null;
  return `${BACKEND_ORIGIN}${path}${path.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`;
}
