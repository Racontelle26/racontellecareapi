import { useCallback, useMemo, useRef, useState } from "react";

import { api, ApiError } from "../api";
import { isLocalId, mergeCapsules, mergeResidents, readLocalState, remapResidentId, writeLocalState } from "../local";
import { BUNDLED_QUESTIONS } from "../question-bank";
import type { AuthUser, BetaSettings, Capsule, ConsentStatus, LocalState, Resident } from "../types";

export const DEFAULT_SETTINGS: BetaSettings = {
  features: { quiz: true, sensitive_themes: false, voice_reading: true, family_share: false, transcription: false, carnet_pdf: false },
  max_residents: 5,
};

export const EMPTY_STATE: LocalState = { residents: [], capsules: [], usage: { total_ms: 0, by_resident_ms: {} }, exports: {}, answered: {}, pending_removals: [], pending_merges: [] };

/**
 * Carnet de l'atelier : état local (offline-first), fusion avec le serveur et
 * file d'attente des opérations faites sans réseau.
 */
export function useCarnetStore(setNotice: (message: string) => void) {
  const [state, setState] = useState<LocalState>(EMPTY_STATE);
  const stateRef = useRef(state);
  const syncing = useRef(false);
  const syncAgain = useRef(false);

  const persist = useCallback(async (next: LocalState) => {
    stateRef.current = next;
    setState(next);
    await writeLocalState(next);
  }, []);

  /** Modifie l'état à partir de la version la plus récente (jamais d'une copie périmée). */
  const update = useCallback((change: (current: LocalState) => LocalState) => persist(change(stateRef.current)), [persist]);

  const patchCapsule = useCallback((id: string, changes: Partial<Capsule>) =>
    update((current) => ({ ...current, capsules: current.capsules.map((item) => (item.id === id ? { ...item, ...changes } : item)) })), [update]);

  const settings = state.settings_cache ?? DEFAULT_SETTINGS;
  const questions = state.questions_cache?.length ? state.questions_cache : BUNDLED_QUESTIONS;

  // Transcription (hors bêta, activable) : souvenirs synchronisés sans texte,
  // 5 par passage, retentés à chaque ouverture.
  const autoTranscribe = useCallback(async () => {
    if (!(stateRef.current.settings_cache ?? DEFAULT_SETTINGS).features.transcription) return;
    const pending = stateRef.current.capsules
      .filter((capsule) => capsule.synced && capsule.audio_uri && !capsule.transcription && !isLocalId(capsule.id))
      .slice(0, 5);
    for (const capsule of pending) {
      try {
        const { transcription } = await api.transcribeCapsule(capsule.id, capsule.audio_uri!);
        await patchCapsule(capsule.id, { transcription });
      } catch (reason) {
        if (reason instanceof ApiError && reason.status === 429) {
          setNotice("Quota quotidien de 30 transcriptions atteint. L’audio reste conservé.");
          return;
        }
      }
    }
  }, [patchCapsule, setNotice]);

  /**
   * File d'attente hors connexion, rejouée dans l'ordre : profils, modifications
   * de profils, retraits, fusions, souvenirs, modifications de souvenirs, puis
   * copies audio. Une panne réseau interrompt le passage : il reprend à la
   * prochaine ouverture, au retour au premier plan ou après une sauvegarde.
   */
  const syncPending = useCallback(async (user: AuthUser | null, onResidentSynced?: (fromId: string, resident: Resident) => void): Promise<boolean> => {
    if (!user) return false;
    if (syncing.current) {
      syncAgain.current = true;
      return true;
    }
    syncing.current = true;
    // Un refus définitif du serveur (400, 403, 404…) ne bloque pas les autres
    // éléments ; une panne réseau, une session expirée ou un quota arrêtent le passage.
    const attempt = async (task: () => Promise<unknown>) => {
      try {
        await task();
        return true;
      } catch (reason) {
        if (reason instanceof ApiError && reason.status >= 400 && reason.status < 500 && ![401, 408, 429].includes(reason.status)) return false;
        throw reason;
      }
    };
    const pass = async () => {
      for (const resident of stateRef.current.residents.filter((item) => isLocalId(item.id))) {
        await attempt(async () => {
          const remote = await api.createResident({ display_name: resident.display_name, last_initial: resident.last_initial, unit: resident.unit, consent_status: resident.consent_status as ConsentStatus });
          const latest = stateRef.current.residents.find((item) => item.id === resident.id) ?? resident;
          const synced: Resident = { ...remote, photo_uri: latest.photo_uri ?? null, pending_sync: false };
          await persist(remapResidentId(stateRef.current, resident.id, synced));
          onResidentSynced?.(resident.id, synced);
        });
      }
      for (const resident of stateRef.current.residents.filter((item) => item.pending_sync && !isLocalId(item.id))) {
        await attempt(async () => {
          await api.updateResident(resident.id, { display_name: resident.display_name, last_initial: resident.last_initial ?? "", unit: resident.unit ?? "", consent_status: resident.consent_status as ConsentStatus });
          await update((current) => ({ ...current, residents: current.residents.map((item) => (item.id === resident.id ? { ...item, pending_sync: false } : item)) }));
        });
      }
      for (const residentId of stateRef.current.pending_removals ?? []) {
        await attempt(() => api.deleteResident(residentId));
        await update((current) => ({ ...current, pending_removals: (current.pending_removals ?? []).filter((id) => id !== residentId) }));
      }
      for (const merge of stateRef.current.pending_merges ?? []) {
        if (isLocalId(merge.keep_id)) continue;
        await attempt(() => api.mergeResidents(merge.keep_id, merge.merge_ids));
        await update((current) => ({ ...current, pending_merges: (current.pending_merges ?? []).filter((item) => item !== merge) }));
      }
      for (const capsule of stateRef.current.capsules.filter((item) => !item.synced && isLocalId(item.id))) {
        if (isLocalId(capsule.resident_id)) continue; // le profil n'est pas encore sur le serveur
        await attempt(async () => {
          const latest = stateRef.current.capsules.find((item) => item.id === capsule.id) ?? capsule;
          const remote = await api.saveCapsule({
            resident_id: latest.resident_id,
            question_id: latest.question_id,
            mode: latest.mode,
            theme: latest.theme,
            title: latest.title,
            duration_sec: latest.duration_sec,
            recorded_at: latest.recorded_at,
          });
          await update((current) => ({
            ...current,
            capsules: current.capsules.map((item) => (item.id === capsule.id ? { ...remote, audio_uri: item.audio_uri, transcription: item.transcription ?? remote.transcription, synced: true, pending_update: false } : item)),
          }));
        });
      }
      for (const capsule of stateRef.current.capsules.filter((item) => item.pending_update && item.synced && !isLocalId(item.id))) {
        if (isLocalId(capsule.resident_id)) continue;
        await attempt(async () => {
          const changes = { ...(capsule.title ? { title: capsule.title } : {}), ...(capsule.theme && capsule.mode === "free" ? { theme: capsule.theme } : {}) };
          if (Object.keys(changes).length) await api.updateCapsule(capsule.id, changes);
          if (capsule.resident_id) await api.assignCapsule(capsule.id, capsule.resident_id);
          await patchCapsule(capsule.id, { pending_update: false });
        });
      }
      // Copie de sauvegarde des audios (5 par passage pour ménager le réseau).
      // Un échec isolé (fichier illisible, coupure) n'empêche pas les suivants.
      const uploads = stateRef.current.capsules.filter((item) => item.synced && item.audio_uri && !item.audio_stored && !isLocalId(item.id)).slice(0, 5);
      for (const capsule of uploads) {
        try {
          await api.uploadCapsuleAudio(capsule.id, capsule.audio_uri!);
          await patchCapsule(capsule.id, { audio_stored: true });
        } catch (reason) {
          api.track("upload_failed");
          if (reason instanceof ApiError && reason.status === 429) {
            setNotice("Quota quotidien d’envois audio atteint. Les souvenirs restent conservés sur l’appareil.");
            break;
          }
        }
      }
    };
    try {
      do {
        syncAgain.current = false;
        await pass();
      } while (syncAgain.current);
      return true;
    } catch {
      return false;
    } finally {
      syncing.current = false;
    }
  }, [patchCapsule, persist, setNotice, update]);

  /** Ouvre le carnet local de l'établissement (ou de l'appareil) courant. */
  const loadLocal = useCallback(async () => {
    const local = await readLocalState();
    stateRef.current = local;
    setState(local);
  }, []);

  /** Vide la mémoire à la déconnexion : aucune donnée d'un établissement ne reste affichée ni réécrite ailleurs. */
  const clear = useCallback(() => {
    stateRef.current = EMPTY_STATE;
    setState(EMPTY_STATE);
  }, []);

  /** Complète le carnet local avec le serveur, puis envoie ce qui attend. */
  const syncWithServer = useCallback(async (user: AuthUser | null, onResidentSynced?: (fromId: string, resident: Resident) => void) => {
    if (!user) return;
    try {
      const [remoteResidents, remoteCapsules, remoteQuestions, remoteSettings] = await Promise.all([api.residents(), api.capsules(), api.questions(), api.settings()]);
      const current = stateRef.current;
      // Les profils retirés ou fusionnés hors connexion restent masqués tant
      // que le serveur n'a pas reçu l'opération.
      const hidden = [...(current.pending_removals ?? []), ...(current.pending_merges ?? []).flatMap((merge) => merge.merge_ids)];
      await persist({
        ...current,
        residents: mergeResidents(current.residents, remoteResidents, hidden),
        capsules: mergeCapsules(current.capsules, remoteCapsules),
        questions_cache: remoteQuestions.length ? remoteQuestions : current.questions_cache,
        settings_cache: remoteSettings,
      });
    } catch {
      setNotice("Mode local actif : les souvenirs restent sur cet appareil et seront envoyés dès que possible.");
      return;
    }
    if (await syncPending(user, onResidentSynced)) void autoTranscribe();
  }, [autoTranscribe, persist, setNotice, syncPending]);

  const pendingUploads = useMemo(
    () => state.capsules.filter((capsule) => !capsule.synced || (capsule.audio_uri && !capsule.audio_stored)).length,
    [state.capsules],
  );

  return { state, stateRef, setState, persist, update, patchCapsule, settings, questions, loadLocal, clear, syncWithServer, syncPending, autoTranscribe, pendingUploads };
}
