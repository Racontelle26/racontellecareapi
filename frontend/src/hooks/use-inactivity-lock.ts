import { useCallback, useEffect, useRef } from "react";
import { AppState, Keyboard } from "react-native";

import { storage } from "../utils/storage";

/** La session se ferme après 5 minutes sans aucune activité. */
export const INACTIVITY_LIMIT_MS = 5 * 60 * 1000;
const LAST_ACTIVITY_KEY = "racontelle.last-activity.v1";
const CHECK_EVERY_MS = 15 * 1000;

export async function readLastActivity(): Promise<number | null> {
  return storage.getItem<number | null>(LAST_ACTIVITY_KEY, null);
}

function saveLastActivity(timestamp: number) {
  void storage.setItem(LAST_ACTIVITY_KEY, timestamp);
}

/** Vrai quand la dernière activité enregistrée date de plus de 5 minutes. */
export function isInactiveSince(lastActivity: number | null, nowMs = Date.now()) {
  return lastActivity !== null && nowMs - lastActivity >= INACTIVITY_LIMIT_MS;
}

/**
 * Ferme la session après 5 minutes d'inactivité totale : aucun toucher sur
 * l'écran, application en arrière-plan ou fermée. Tant que l'application est
 * utilisée, la session ne se ferme jamais. Un enregistrement en cours ou non
 * sauvegardé, une écoute ou un clavier ouvert comptent comme de l'activité :
 * un long récit n'est jamais interrompu.
 *
 * Renvoie la fonction à appeler à chaque toucher.
 */
export function useInactivityLock({ enabled, busy, onExpire }: { enabled: boolean; busy: boolean; onExpire: () => void }) {
  const lastActivity = useRef(0);
  const enabledRef = useRef(enabled);
  const busyRef = useRef(busy);
  const onExpireRef = useRef(onExpire);
  const keyboardOpen = useRef(false);

  useEffect(() => {
    busyRef.current = busy;
    onExpireRef.current = onExpire;
  }, [busy, onExpire]);

  // Une session qui s'ouvre repart d'une activité « maintenant ».
  useEffect(() => {
    enabledRef.current = enabled;
    if (!enabled) return;
    lastActivity.current = Date.now();
    saveLastActivity(lastActivity.current);
  }, [enabled]);

  const markActivity = useCallback(() => {
    lastActivity.current = Date.now();
  }, []);

  useEffect(() => {
    const check = () => {
      if (!enabledRef.current) return;
      const nowMs = Date.now();
      if (busyRef.current || keyboardOpen.current) lastActivity.current = nowMs;
      if (nowMs - lastActivity.current >= INACTIVITY_LIMIT_MS) {
        enabledRef.current = false;
        onExpireRef.current();
        return;
      }
      saveLastActivity(lastActivity.current);
    };
    const interval = setInterval(check, CHECK_EVERY_MS);
    const appState = AppState.addEventListener("change", (status) => {
      // Au retour, le temps passé en arrière-plan compte comme de l'inactivité.
      if (status === "active") check();
      else if (enabledRef.current) saveLastActivity(lastActivity.current);
    });
    const shown = Keyboard.addListener("keyboardDidShow", () => {
      keyboardOpen.current = true;
      lastActivity.current = Date.now();
    });
    const hidden = Keyboard.addListener("keyboardDidHide", () => {
      keyboardOpen.current = false;
      lastActivity.current = Date.now();
    });
    return () => {
      clearInterval(interval);
      appState.remove();
      shown.remove();
      hidden.remove();
    };
  }, []);

  return markActivity;
}
