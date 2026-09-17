import Constants from "expo-constants";
import { Platform } from "react-native";

import type { Capsule, Question, Resident } from "./types";

// EXPO_PUBLIC_BACKEND_URL is the protected frontend environment contract for this workspace.
// Do not replace it with EXPO_BACKEND_URL: the preview and native builds inject this public value.
const baseUrl = String(
  Constants.expoConfig?.extra?.backendUrl ?? process.env.EXPO_PUBLIC_BACKEND_URL ?? "",
).replace(/\/$/, "");

export const apiBaseUrl = baseUrl;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  if (!baseUrl) throw new Error("Serveur temporaire indisponible");
  const response = await fetch(`${baseUrl}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

// Multipart audio upload. Native FormData takes { uri, name, type }; on web the
// local file:// or blob: URI must be fetched into a real Blob first. Never set
// Content-Type manually: the runtime adds the multipart boundary.
async function uploadAudio<T>(path: string, uri: string): Promise<T> {
  if (!baseUrl) throw new Error("Serveur temporaire indisponible");
  const name = Platform.OS === "web" ? "recording.webm" : "recording.m4a";
  const type = Platform.OS === "web" ? "audio/webm" : "audio/m4a";
  const form = new FormData();
  if (Platform.OS === "web") {
    const blob = await (await fetch(uri)).blob();
    form.append("file", blob, name);
  } else {
    form.append("file", { uri, name, type } as any);
  }
  const response = await fetch(`${baseUrl}/api${path}`, { method: "POST", body: form });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export const api = {
  residents: () => request<Resident[]>("/residents"),
  createResident: (display_name: string) =>
    request<Resident>("/residents", {
      method: "POST",
      body: JSON.stringify({ display_name, consent_status: "obtained" }),
    }),
  questions: () => request<Question[]>("/questions?limit=100"),
  saveCapsule: (capsule: Omit<Capsule, "id" | "status" | "synced">) =>
    request<Capsule>("/capsules", { method: "POST", body: JSON.stringify(capsule) }),
  deleteCapsule: (id: string) => request<{ deleted: boolean }>(`/capsules/${id}`, { method: "DELETE" }),
  uploadCapsuleAudio: (id: string, uri: string) =>
    uploadAudio<{ uploaded: boolean }>(`/capsules/${id}/audio`, uri),
  transcribeCapsule: (id: string, uri: string) =>
    uploadAudio<{ transcription: string }>(`/capsules/${id}/transcribe`, uri),
  shareCapsule: (id: string) =>
    request<{ token: string; path: string }>(`/capsules/${id}/share`, { method: "POST" }),
  exportResidentUrl: (id: string) => `${baseUrl}/api/residents/${id}/export`,
  carnetResidentUrl: (id: string) => `${baseUrl}/api/residents/${id}/carnet`,
  mergeResidents: (keep_id: string, merge_ids: string[]) =>
    request<{ merged: number }>("/residents/merge", {
      method: "POST",
      body: JSON.stringify({ keep_id, merge_ids }),
    }),
  deleteResident: (id: string) =>
    request<{ deleted: boolean }>(`/residents/${id}`, { method: "DELETE" }),
};