export type ConsentStatus = "obtained" | "pending" | "withdrawn";

export type Resident = {
  id: string;
  display_name: string;
  /** Initiale ou nom, facultatif. */
  last_initial?: string | null;
  /** Unité de vie, facultative. */
  unit?: string | null;
  consent_status: ConsentStatus | string;
  consent_updated_at?: string | null;
  active: boolean;
  created_at: string;
  photo_uri?: string | null;
  /** Modification faite hors connexion, à envoyer au serveur. */
  pending_sync?: boolean;
};

export type Question = {
  id: string;
  number?: number;
  theme: string;
  text: string;
  level?: string;
  usage?: string;
  tags?: string[];
  sensitive: boolean;
  active?: boolean;
};

export type ThemeInfo = {
  theme: string;
  sensitive: boolean;
  active_count: number;
  total: number;
  enabled: boolean;
};

export type Capsule = {
  id: string;
  resident_id: string | null;
  question_id: string | null;
  mode: "free" | "question";
  theme: string | null;
  title: string | null;
  duration_sec: number;
  /** Heure d'enregistrement d'origine (conservée même si l'envoi est différé). */
  recorded_at: string;
  /** Heure de réception par le serveur. */
  created_at?: string | null;
  created_by_name?: string | null;
  classified_at?: string | null;
  status: "assigned" | "unclassified";
  synced: boolean;
  audio_uri?: string | null;
  transcription?: string | null;
  share_id?: string | null;
  share_expires_at?: string | null;
  /** Une copie de l'audio est conservée côté serveur (condition pour effacer le fichier local). */
  audio_stored?: boolean;
  /** Titre, thème ou rattachement modifié hors connexion, à envoyer au serveur. */
  pending_update?: boolean;
};

export type PendingMerge = { keep_id: string; merge_ids: string[] };

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

export type FeatureFlags = {
  quiz: boolean;
  sensitive_themes: boolean;
  voice_reading: boolean;
  family_share: boolean;
  transcription: boolean;
  carnet_pdf: boolean;
};

export type BetaSettings = { features: FeatureFlags; max_residents: number };

export type QuizItem = {
  id: string;
  type: "quote" | "music";
  prompt_text: string;
  correct_answer: string;
  choices: string[];
  era?: string | null;
  theme?: string | null;
  difficulty?: string | null;
  source_reference?: string | null;
  rights_status: "public_domain" | "licensed" | "provided_by_client" | "blocked";
  license_note?: string | null;
  active: boolean;
  has_stored_audio?: boolean;
  audio_url?: string | null;
  audio_file?: string | null;
  activation_problem?: string | null;
};

export type AuditEntry = {
  id: string;
  user_name?: string | null;
  action: string;
  object_type: string;
  object_id?: string | null;
  details?: Record<string, unknown>;
  created_at: string;
};

export type FeedbackCategory = "bug" | "micro" | "reseau" | "sauvegarde" | "question" | "quiz" | "idee" | "autre";

export type UsageEventType =
  | "session_start"
  | "theme_selected"
  | "question_change"
  | "question_surprise"
  | "recording_abandoned"
  | "mic_denied"
  | "recording_failed"
  | "upload_failed"
  | "save_failed"
  | "quiz_item_played";

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
  /** Ids des questions déjà répondues, par profil ("none" pour le mode spontané). */
  answered: Record<string, string[]>;
  /** Opérations faites hors connexion, rejouées à la prochaine synchronisation. */
  pending_removals?: string[];
  pending_merges?: PendingMerge[];
  /** Dernière banque de questions et derniers réglages reçus du serveur (hors connexion). */
  questions_cache?: Question[];
  settings_cache?: BetaSettings;
};
