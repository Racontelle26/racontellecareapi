import { storage } from "@/src/utils/storage";

import type { Capsule, LocalState, Resident } from "./types";

let scope = "guest";
const DEFAULT_STATE: LocalState = { residents: [], capsules: [], usage: { total_ms: 0, by_resident_ms: {} }, exports: {}, answered: {} };

function key() {
  return `racontelle.local.v2.${scope}`;
}

export function setLocalScope(tenantId: string | null) {
  scope = tenantId ?? "guest";
}

export async function readLocalState(): Promise<LocalState> {
  const stored = await storage.getItem<LocalState>(key(), DEFAULT_STATE);
  const legacyUsage = stored?.usage;
  const byResidentMs = legacyUsage?.by_resident_ms ?? Object.fromEntries(
    Object.entries(legacyUsage?.by_resident ?? {}).map(([id, seconds]) => [id, seconds * 1000]),
  );
  // Les états enregistrés avant l'espace professionnel n'ont pas de compteur.
  return {
    ...DEFAULT_STATE,
    ...stored,
    usage: {
      total_ms: legacyUsage?.total_ms ?? (legacyUsage?.total_sec ?? 0) * 1000,
      by_resident_ms: byResidentMs,
    },
    exports: stored?.exports ?? DEFAULT_STATE.exports,
    answered: stored?.answered ?? DEFAULT_STATE.answered,
  };
}

export async function writeLocalState(state: LocalState): Promise<boolean> {
  return storage.setItem(key(), state);
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