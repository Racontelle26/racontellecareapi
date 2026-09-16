import Constants from "expo-constants";

import type { Capsule, Question, Resident } from "./types";

// EXPO_PUBLIC_BACKEND_URL is the protected frontend environment contract for this workspace.
// Do not replace it with EXPO_BACKEND_URL: the preview and native builds inject this public value.
const baseUrl = String(
  Constants.expoConfig?.extra?.backendUrl ?? process.env.EXPO_PUBLIC_BACKEND_URL ?? "",
).replace(/\/$/, "");

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  if (!baseUrl) throw new Error("Serveur temporaire indisponible");
  const response = await fetch(`${baseUrl}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
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
};