import { storage } from "@/src/utils/storage";

import type { Capsule, LocalState, Resident } from "./types";

let scope = "guest";
const DEFAULT_STATE: LocalState = { residents: [], capsules: [], usage: { total_ms: 0, by_resident_ms: {} }, exports: {}, answered: {}, pending_removals: [], pending_merges: [] };

function key() {
  return `racontelle.local.v2.${scope}`;
}

export function setLocalScope(tenantId: string | null) {
  scope = tenantId ?? "guest";
}

export function isLocalId(id: string | null | undefined) {
  return !!id && id.startsWith("local-");
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
    pending_removals: stored?.pending_removals ?? [],
    pending_merges: stored?.pending_merges ?? [],
  };
}

export async function writeLocalState(state: LocalState): Promise<boolean> {
  return storage.setItem(key(), state);
}

/**
 * Fusion appareil ↔ serveur. Le serveur fait foi pour les profils déjà
 * synchronisés : un profil retiré ou fusionné depuis un autre appareil
 * disparaît ici aussi. Les profils créés hors connexion (`local-…`) et les
 * modifications en attente (`pending_sync`) sont conservés tels quels.
 */
export function mergeResidents(local: Resident[], remote: Resident[], hiddenIds: string[] = []): Resident[] {
  const localById = new Map(local.map((resident) => [resident.id, resident]));
  const hidden = new Set(hiddenIds);
  const merged: Resident[] = remote
    .filter((resident) => !hidden.has(resident.id))
    .map((resident) => {
      const mine = localById.get(resident.id);
      // La photo du profil vit sur l'appareil (offline-first) : la copie
      // serveur ne doit jamais l'effacer.
      return mine?.pending_sync
        ? { ...resident, display_name: mine.display_name, pending_sync: true, photo_uri: mine.photo_uri ?? null }
        : { ...resident, photo_uri: mine?.photo_uri ?? null };
    });
  local.filter((resident) => isLocalId(resident.id)).forEach((resident) => merged.push(resident));
  return merged;
}

export function mergeCapsules(local: Capsule[], remote: Capsule[]): Capsule[] {
  const byId = new Map(local.map((capsule) => [capsule.id, capsule]));
  remote.forEach((capsule) => {
    const mine = byId.get(capsule.id);
    const next = { ...mine, ...capsule, audio_uri: mine?.audio_uri ?? null };
    // Une modification locale pas encore envoyée l'emporte sur la copie serveur.
    byId.set(capsule.id, mine?.pending_update
      ? { ...next, title: mine.title, resident_id: mine.resident_id, status: mine.status, pending_update: true }
      : next);
  });
  return Array.from(byId.values()).sort((a, b) => b.recorded_at.localeCompare(a.recorded_at));
}

/** Remplace l'identifiant provisoire d'un profil par celui attribué par le serveur. */
export function remapResidentId(state: LocalState, fromId: string, resident: Resident): LocalState {
  const renameKey = <T,>(record: Record<string, T> | undefined) => {
    if (!record || !(fromId in record)) return record ?? {};
    const { [fromId]: value, ...rest } = record;
    return { ...rest, [resident.id]: value };
  };
  return {
    ...state,
    residents: state.residents.map((item) => (item.id === fromId ? resident : item)),
    capsules: state.capsules.map((capsule) => (capsule.resident_id === fromId ? { ...capsule, resident_id: resident.id } : capsule)),
    usage: { ...state.usage, by_resident_ms: renameKey(state.usage.by_resident_ms) },
    exports: renameKey(state.exports),
    answered: renameKey(state.answered),
    pending_merges: (state.pending_merges ?? []).map((merge) => (merge.keep_id === fromId ? { ...merge, keep_id: resident.id } : merge)),
  };
}
