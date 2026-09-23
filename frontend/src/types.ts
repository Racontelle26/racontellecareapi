export type Resident = {
  id: string;
  display_name: string;
  consent_status: string;
  active: boolean;
  created_at: string;
  photo_uri?: string | null;
};

export type Question = {
  id: string;
  theme: string;
  text: string;
  sensitive: boolean;
};

export type Capsule = {
  id: string;
  resident_id: string | null;
  question_id: string | null;
  mode: "free" | "question";
  theme: string | null;
  title: string | null;
  duration_sec: number;
  recorded_at: string;
  status: "assigned" | "unclassified";
  synced: boolean;
  audio_uri?: string | null;
  transcription?: string | null;
  share_id?: string | null;
  share_expires_at?: string | null;
};

export type AuthUser = {
  id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  role: "admin" | "member";
  establishment_name: string;
};

export type AuthSession = {
  access_token: string;
  refresh_token?: string | null;
  token_type: "bearer";
  user: AuthUser;
};

export type UsageState = {
  /** Durée active réelle, conservée à la milliseconde pour éviter tout arrondi. */
  total_ms: number;
  by_resident_ms: Record<string, number>;
  /** Anciens champs lus uniquement pendant la migration locale. */
  total_sec?: number;
  by_resident?: Record<string, number>;
};

export type LocalState = {
  residents: Resident[];
  capsules: Capsule[];
  usage: UsageState;
  /** Date ISO du dernier export réalisé par profil (retrait sécurisé). */
  exports: Record<string, string>;
  /** Ids des questions déjà répondues, par profil ("none" pour le mode spontané).
   * Les questions non traitées sont reproposées lors des ateliers suivants. */
  answered: Record<string, string[]>;
};