import { storage } from "@/src/utils/storage";

import type { Capsule, LocalState, Resident } from "./types";

const KEY = "racontelle.local.v1";
const DEFAULT_STATE: LocalState = { residents: [], capsules: [], usage: { total_sec: 0, by_resident: {} }, exports: {} };

export async function readLocalState(): Promise<LocalState> {
  const stored = await storage.getItem<LocalState>(KEY, DEFAULT_STATE);
  // Les états enregistrés avant l'espace professionnel n'ont pas de compteur.
  return {
    ...DEFAULT_STATE,
    ...stored,
    usage: stored?.usage ?? DEFAULT_STATE.usage,
    exports: stored?.exports ?? DEFAULT_STATE.exports,
  };
}

export async function writeLocalState(state: LocalState): Promise<boolean> {
  return storage.setItem(KEY, state);
}

export function mergeResidents(local: Resident[], remote: Resident[]): Resident[] {
  const byId = new Map(local.map((resident) => [resident.id, resident]));
  remote.forEach((resident) => {
    // La photo du profil vit sur l'appareil (offline-first) : la copie
    // serveur ne doit jamais l'effacer.
    byId.set(resident.id, { ...resident, photo_uri: byId.get(resident.id)?.photo_uri ?? null });
  });
  return Array.from(byId.values()).slice(0, 10);
}

export function mergeCapsules(local: Capsule[], remote: Capsule[]): Capsule[] {
  const byId = new Map(local.map((capsule) => [capsule.id, capsule]));
  remote.forEach((capsule) => byId.set(capsule.id, { ...byId.get(capsule.id), ...capsule }));
  return Array.from(byId.values()).sort((a, b) => b.recorded_at.localeCompare(a.recorded_at));
}