import Constants from "expo-constants";
import * as FileSystem from "expo-file-system/legacy";
import { Platform } from "react-native";

import { storage } from "./utils/storage";
import type {
  AuditEntry,
  AuthSession,
  AuthUser,
  BetaSettings,
  Capsule,
  ConsentStatus,
  FeatureFlags,
  FeedbackCategory,
  Question,
  QuizItem,
  Resident,
  ThemeInfo,
  UsageEventType,
} from "./types";

const baseUrl = String(
  Constants.expoConfig?.extra?.backendUrl ?? process.env.EXPO_PUBLIC_BACKEND_URL ?? "",
).replace(/\/$/, "");

export const apiBaseUrl = baseUrl;
export const appVersion = `${Constants.expoConfig?.version ?? "1.0.0"}-beta`;
const SESSION_KEY = "racontelle.auth.session.v1";
const REMEMBERED_USER_KEY = "racontelle.auth.remembered-user.v1";
let sessionCache: AuthSession | null = null;
let refreshPromise: Promise<AuthSession | null> | null = null;
let sessionExpiredHandler: (() => void) | null = null;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Vrai quand l'échec vient du réseau (et non d'un refus du serveur). */
export function isNetworkError(reason: unknown) {
  return !(reason instanceof ApiError) || reason.status >= 500 || reason.status === 408;
}

// Messages compréhensibles pour les champs refusés par le serveur (erreur 422).
const FIELD_ERRORS: Record<string, string> = {
  email: "L’adresse email n’est pas valide. Vérifiez-la (exemple : prenom.nom@ehpad.fr).",
  password: "Le mot de passe doit contenir entre 12 et 128 caractères.",
  new_password: "Le nouveau mot de passe doit contenir entre 12 et 128 caractères.",
  code: "Le code doit être celui reçu par email (8 caractères).",
  full_name: "Indiquez votre nom (2 caractères minimum).",
  establishment_name: "Indiquez le nom de l’établissement (2 caractères minimum).",
  display_name: "Indiquez un prénom ou un pseudonyme.",
};

async function parseError(response: Response) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      const fields = body.detail.map((item: { loc?: unknown[] }) => String(item.loc?.[item.loc.length - 1] ?? ""));
      const known = fields.map((field: string) => FIELD_ERRORS[field]).filter(Boolean);
      if (known.length) return [...new Set(known)].join(" ");
      return "Certaines informations saisies ne sont pas valides. Vérifiez les champs et réessayez.";
    }
    return "Une erreur est survenue. Réessayez dans un instant.";
  } catch {
    return "Le serveur ne répond pas correctement. Réessayez dans un instant.";
  }
}

async function saveSession(session: AuthSession | null) {
  sessionCache = session;
  if (session) {
    await storage.secureSet(SESSION_KEY, session);
    await storage.setItem(REMEMBERED_USER_KEY, session.user);
  }
  else await storage.secureRemove(SESSION_KEY);
}

async function rememberedUser() {
  const session = await storedSession();
  return session?.user ?? storage.getItem<AuthUser | null>(REMEMBERED_USER_KEY, null);
}

async function storedSession() {
  if (sessionCache) return sessionCache;
  sessionCache = await storage.secureGet<AuthSession | null>(SESSION_KEY, null);
  return sessionCache;
}

function platformHeaders() {
  return { "X-Client-Platform": Platform.OS === "web" ? "web" : "native" };
}

async function refreshSession(): Promise<AuthSession | null> {
  const existing = await storedSession();
  try {
    const response = await fetch(`${baseUrl}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...platformHeaders() },
      body: JSON.stringify({ refresh_token: existing?.refresh_token ?? null }),
    });
    if (!response.ok) {
      await saveSession(null);
      return null;
    }
    const next = await response.json() as AuthSession;
    await saveSession(next);
    return next;
  } catch {
    return existing;
  }
}

function sharedRefresh() {
  refreshPromise ??= refreshSession().finally(() => { refreshPromise = null; });
  return refreshPromise;
}

async function authorizedFetch(path: string, options: RequestInit = {}, retry = true) {
  if (!baseUrl) throw new ApiError(503, "Serveur temporaire indisponible");
  const session = await storedSession();
  const headers = new Headers(options.headers);
  headers.set("X-Client-Platform", Platform.OS === "web" ? "web" : "native");
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (session?.access_token) headers.set("Authorization", `Bearer ${session.access_token}`);
  let response = await fetch(`${baseUrl}/api${path}`, {
    ...options,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && retry) {
    const refreshed = await sharedRefresh();
    if (refreshed) {
      headers.set("Authorization", `Bearer ${refreshed.access_token}`);
      response = await fetch(`${baseUrl}/api${path}`, {
        ...options,
        headers,
        credentials: "include",
      });
    }
  }
  if (response.status === 401) {
    await saveSession(null);
    sessionExpiredHandler?.();
  }
  return response;
}

/**
 * Téléchargement natif vers un fichier (export ZIP, carnet PDF, audio).
 * `downloadAsync` ne lève pas d'erreur sur une réponse 401/500 : il enregistre
 * le message d'erreur comme s'il s'agissait du fichier. On vérifie donc le
 * statut, on renouvelle la session une fois si elle a expiré, et on efface
 * tout fichier incomplet.
 */
async function downloadToFile(path: string, target: string): Promise<string> {
  if (!baseUrl) throw new ApiError(503, "Serveur temporaire indisponible");
  const attempt = async () => {
    const session = await storedSession();
    const headers: Record<string, string> = { ...platformHeaders() };
    if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
    return FileSystem.downloadAsync(`${baseUrl}/api${path}`, target, { headers });
  };
  let result = await attempt();
  if (result.status === 401 && await sharedRefresh()) result = await attempt();
  if (result.status !== 200) {
    await FileSystem.deleteAsync(target, { idempotent: true }).catch(() => {});
    if (result.status === 401) {
      await saveSession(null);
      sessionExpiredHandler?.();
    }
    throw new ApiError(result.status, "Téléchargement impossible");
  }
  return result.uri;
}

/** Récupère un fichier protégé et renvoie une adresse lisible par le lecteur ou le partage. */
async function fetchFileUri(path: string, fileName: string): Promise<string> {
  if (Platform.OS === "web") {
    const response = await authorizedFetch(path);
    if (!response.ok) throw new ApiError(response.status, await parseError(response));
    return URL.createObjectURL(await response.blob());
  }
  return downloadToFile(path, `${FileSystem.cacheDirectory}${fileName}`);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await authorizedFetch(path, options);
  if (!response.ok) throw new ApiError(response.status, await parseError(response));
  return response.json() as Promise<T>;
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

async function uploadAudio<T>(path: string, uri: string): Promise<T> {
  const name = Platform.OS === "web" ? "recording.webm" : "recording.m4a";
  const type = Platform.OS === "web" ? "audio/webm" : "audio/m4a";
  const form = new FormData();
  if (Platform.OS === "web") {
    const blob = await (await fetch(uri)).blob();
    form.append("file", blob.type ? blob : new Blob([blob], { type }), name);
  } else {
    form.append("file", { uri, name, type } as any);
  }
  const response = await authorizedFetch(path, { method: "POST", body: form });
  if (!response.ok) throw new ApiError(response.status, await parseError(response));
  return response.json() as Promise<T>;
}

async function publicPost<T>(path: string, body: Record<string, string>): Promise<T> {
  if (!baseUrl) throw new ApiError(503, "Serveur temporaire indisponible");
  const response = await fetch(`${baseUrl}/api/auth/${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...platformHeaders() },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new ApiError(response.status, await parseError(response));
  return response.json() as Promise<T>;
}

async function beginAuth(path: string, body: Record<string, string>) {
  const session = await publicPost<AuthSession>(path, body);
  await saveSession(session);
  return session;
}

export const authApi = {
  onSessionExpired: (handler: (() => void) | null) => { sessionExpiredHandler = handler; },
  register: (body: { email: string; password: string; full_name: string; establishment_name: string }) => beginAuth("register", body),
  login: (email: string, password: string) => beginAuth("login", { email, password }),
  forgotPassword: (email: string) => publicPost<{ ok: boolean; message: string }>("password/forgot", { email }),
  resetPassword: (email: string, code: string, new_password: string) => publicPost<{ ok: boolean; message: string }>("password/reset", { email, code, new_password }),
  rememberedUser,
  logout: async () => {
    const session = await storedSession();
    if (session) {
      await authorizedFetch("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: session.refresh_token ?? null }),
      }, false).catch(() => null);
    }
    await saveSession(null);
    await storage.removeItem(REMEMBERED_USER_KEY);
  },
  current: storedSession,
};

export type NewResident = { display_name: string; last_initial?: string | null; unit?: string | null; consent_status: ConsentStatus };
export type ResidentChanges = Partial<Pick<Resident, "display_name" | "last_initial" | "unit">> & { consent_status?: ConsentStatus };
export type CapsuleChanges = { title?: string; theme?: string; question_id?: string };
export type Indicators = Record<string, any>;

export const api = {
  // Profils et consentement
  residents: () => request<Resident[]>("/residents"),
  createResident: (body: NewResident) => request<Resident>("/residents", json("POST", body)),
  updateResident: (id: string, changes: ResidentChanges) => request<Resident>(`/residents/${id}`, json("PATCH", changes)),
  deleteResident: (id: string) => request<{ deleted: boolean }>(`/residents/${id}`, { method: "DELETE" }),
  purgeResident: (id: string) => request<{ purged: boolean; capsules_erased: number }>(`/residents/${id}/purge`, { method: "DELETE" }),
  mergeResidents: (keep_id: string, merge_ids: string[]) => request<{ merged: number }>("/residents/merge", json("POST", { keep_id, merge_ids })),
  exportResidentPath: (id: string) => `/residents/${id}/export`,
  carnetResidentPath: (id: string) => `/residents/${id}/carnet`,

  // Questions
  questions: () => request<Question[]>("/questions?limit=400"),
  themes: () => request<ThemeInfo[]>("/questions/themes"),
  adminQuestions: (theme?: string) => request<Question[]>(`/questions/admin${theme ? `?theme=${encodeURIComponent(theme)}` : ""}`),
  toggleQuestion: (id: string, active: boolean) => request<{ id: string; active: boolean }>(`/questions/${id}`, json("PATCH", { active })),

  // Souvenirs
  capsules: () => request<Capsule[]>("/capsules"),
  saveCapsule: (capsule: Pick<Capsule, "resident_id" | "question_id" | "mode" | "theme" | "title" | "duration_sec" | "recorded_at">) => request<Capsule>("/capsules", json("POST", capsule)),
  updateCapsule: (id: string, changes: CapsuleChanges) => request<Capsule>(`/capsules/${id}`, json("PATCH", changes)),
  assignCapsule: (id: string, resident_id: string) => request<Capsule>(`/capsules/${id}/assign?resident_id=${encodeURIComponent(resident_id)}`, { method: "PATCH" }),
  deleteCapsule: (id: string) => request<{ deleted: boolean }>(`/capsules/${id}`, { method: "DELETE" }),
  uploadCapsuleAudio: (id: string, uri: string) => uploadAudio<{ uploaded: boolean; remaining: number }>(`/capsules/${id}/audio`, uri),
  capsuleAudioUri: (id: string) => fetchFileUri(`/capsules/${id}/audio`, `capsule-${id.replace(/[^a-z0-9-]/gi, "")}.m4a`),
  transcribeCapsule: (id: string, uri: string) => uploadAudio<{ transcription: string }>(`/capsules/${id}/transcribe`, uri),
  shareCapsule: (id: string) => request<{ token: string; share_id: string; path: string; expires_at: string }>(`/capsules/${id}/share`, { method: "POST" }),
  revokeShare: (id: string) => request<{ revoked: boolean }>(`/shares/${id}`, { method: "DELETE" }),

  // Fichiers protégés
  download: (path: string) => authorizedFetch(path),
  downloadToFile,
  fetchFileUri,
  tts: (text: string) => request<{ path: string }>("/tts", json("POST", { text })),

  // Équipe
  members: () => request<AuthUser[]>("/auth/members"),
  createMember: (body: { email: string; password: string; full_name: string }) => request<AuthUser>("/auth/members", json("POST", body)),
  setMemberPassword: (id: string, new_password: string) => request<{ ok: boolean }>(`/auth/members/${id}/password`, json("POST", { new_password })),

  // Pilotage de la bêta
  settings: () => request<BetaSettings>("/settings"),
  updateSettings: (changes: Partial<FeatureFlags>) => request<BetaSettings>("/settings", json("PATCH", changes)),
  audit: (limit = 50) => request<AuditEntry[]>(`/audit?limit=${limit}`),
  sendFeedback: (body: { category: FeedbackCategory; message?: string; screen?: string }) =>
    request<{ id: string }>("/feedback", json("POST", { ...body, app_version: appVersion, platform: Platform.OS })),
  feedbackList: () => request<{ id: string; category: string; message?: string | null; user_name?: string; app_version: string; created_at: string }[]>("/feedback"),
  indicators: () => request<Indicators>("/indicators"),
  indicatorsCsvPath: "/indicators?format=csv",
  /** Événement d'usage anonyme pour les indicateurs de la bêta (jamais bloquant). */
  track: (type: UsageEventType, data: { theme?: string; question_id?: string; item_id?: string; value?: number } = {}) => {
    void request("/events", json("POST", { type, ...data, app_version: appVersion })).catch(() => null);
  },

  // Quiz « Qui a dit ça ? »
  quizItems: (filters: { type?: "quote" | "music"; era?: string; theme?: string; difficulty?: string } = {}) => {
    const query = Object.entries(filters).filter(([, value]) => value).map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`).join("&");
    return request<QuizItem[]>(`/quiz/items${query ? `?${query}` : ""}`);
  },
  quizFilters: () => request<{ eras: string[]; themes: string[]; difficulties: string[] }>("/quiz/filters"),
  quizAdminItems: () => request<QuizItem[]>("/quiz/admin/items"),
  updateQuizItem: (id: string, changes: { active?: boolean; rights_status?: QuizItem["rights_status"] }) => request<QuizItem>(`/quiz/items/${id}`, json("PATCH", changes)),
  importQuiz: (format: "json" | "csv", content: string) =>
    request<{ created: number; updated: number; inactive: { line: number; id: string; reason: string }[]; errors: { line: number; error: string }[] }>("/quiz/import", json("POST", { format, content })),
  quizAudioUri: (id: string) => fetchFileUri(`/quiz/items/${id}/audio`, `quiz-${id.replace(/[^a-z0-9-]/gi, "")}.mp3`),
  saveQuizSession: (body: { quiz_type: "quote" | "music"; item_count: number; score?: number | null }) => request<{ id: string }>("/quiz/sessions", json("POST", body)),
};
