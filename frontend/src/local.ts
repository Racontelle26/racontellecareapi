import { storage } from "@/src/utils/storage";

import type { Capsule, LocalState, Resident } from "./types";

const KEY = "racontelle.local.v1";

export async function readLocalState(): Promise<LocalState> {
  return (await storage.getItem<LocalState>(KEY, { residents: [], capsules: [] })) ?? {
    residents: [],
    capsules: [],
  };
}

export async function writeLocalState(state: LocalState): Promise<boolean> {
  return storage.setItem(KEY, state);
}

export function mergeResidents(local: Resident[], remote: Resident[]): Resident[] {
  const byId = new Map(local.map((resident) => [resident.id, resident]));
  remote.forEach((resident) => byId.set(resident.id, resident));
  return Array.from(byId.values()).slice(0, 10);
}

export function mergeCapsules(local: Capsule[], remote: Capsule[]): Capsule[] {
  const byId = new Map(local.map((capsule) => [capsule.id, capsule]));
  remote.forEach((capsule) => byId.set(capsule.id, { ...byId.get(capsule.id), ...capsule }));
  return Array.from(byId.values()).sort((a, b) => b.recorded_at.localeCompare(a.recorded_at));
}