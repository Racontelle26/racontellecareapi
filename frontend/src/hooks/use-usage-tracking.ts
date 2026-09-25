import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import { AppState } from "react-native";

import { writeLocalState } from "../local";
import type { LocalState, UsageState } from "../types";

const usageClockNow = () => globalThis.performance?.now?.() ?? Date.now();

type UsageSession = { startedAt: number; residentId: string | null; active: boolean };

/**
 * Chronométrage réel : chaque milliseconde au premier plan est comptée, sans
 * seuil ni arrondi. Le temps d'un résident correspond à sa fiche et à son
 * atelier. L'horloge monotone ignore les changements d'heure du téléphone.
 */
export function useUsageTracking(stateRef: MutableRefObject<LocalState>, setState: (next: LocalState) => void, residentId: string | null, enabled: boolean) {
  const session = useRef<UsageSession>({ startedAt: usageClockNow(), residentId: null, active: AppState.currentState === "active" });
  // Rempli par reset() à l'ouverture d'un carnet, puis par le chrono.
  const [displayedUsage, setDisplayedUsage] = useState<UsageState>({ total_ms: 0, by_resident_ms: {} });
  // Aucun enregistrement tant qu'aucun carnet n'est ouvert (chargement,
  // écran de connexion) : on n'écrit jamais un carnet dans le mauvais espace.
  const enabledRef = useRef(enabled);
  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  const commit = useCallback((nextResidentId: string | null, active?: boolean) => {
    const previous = session.current;
    const timestamp = usageClockNow();
    const elapsedMs = previous.active ? Math.max(0, timestamp - previous.startedAt) : 0;
    session.current = { startedAt: timestamp, residentId: nextResidentId, active: active ?? AppState.currentState === "active" };
    if (!elapsedMs || !enabledRef.current) return;
    const current = stateRef.current;
    const usage = current.usage ?? { total_ms: 0, by_resident_ms: {} };
    const nextUsage = {
      total_ms: usage.total_ms + elapsedMs,
      by_resident_ms: previous.residentId
        ? { ...usage.by_resident_ms, [previous.residentId]: (usage.by_resident_ms[previous.residentId] ?? 0) + elapsedMs }
        : usage.by_resident_ms,
    };
    const next = { ...current, usage: nextUsage };
    stateRef.current = next;
    setState(next);
    setDisplayedUsage(nextUsage);
    void writeLocalState(next);
  }, [setState, stateRef]);

  /** Nouveau carnet chargé (connexion, déconnexion) : le chrono repart de zéro. */
  const reset = useCallback(() => {
    session.current = { startedAt: usageClockNow(), residentId: null, active: AppState.currentState === "active" };
    setDisplayedUsage(stateRef.current.usage);
  }, [stateRef]);

  const stop = useCallback(() => commit(null, false), [commit]);

  useEffect(() => {
    if (residentId !== session.current.residentId) commit(residentId);
  }, [commit, residentId]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (status) => {
      if (status === "active") session.current = { ...session.current, startedAt: usageClockNow(), active: true };
      else if (session.current.active) commit(session.current.residentId, false);
    });
    return () => subscription.remove();
  }, [commit]);

  // L'affichage avance chaque seconde ; un point de contrôle est enregistré
  // toutes les 10 secondes pour limiter toute perte en cas d'arrêt brutal.
  useEffect(() => {
    const ticker = setInterval(() => {
      const stored = stateRef.current.usage ?? { total_ms: 0, by_resident_ms: {} };
      const current = session.current;
      const elapsedMs = current.active ? Math.max(0, usageClockNow() - current.startedAt) : 0;
      setDisplayedUsage({
        total_ms: stored.total_ms + elapsedMs,
        by_resident_ms: current.residentId
          ? { ...stored.by_resident_ms, [current.residentId]: (stored.by_resident_ms[current.residentId] ?? 0) + elapsedMs }
          : stored.by_resident_ms,
      });
    }, 1000);
    const checkpoint = setInterval(() => {
      if (session.current.active) commit(session.current.residentId, true);
    }, 10000);
    return () => {
      clearInterval(ticker);
      clearInterval(checkpoint);
    };
  }, [commit, stateRef]);

  return { displayedUsage, reset, stop };
}
