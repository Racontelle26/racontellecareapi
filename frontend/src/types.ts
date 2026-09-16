export type Resident = {
  id: string;
  display_name: string;
  consent_status: string;
  active: boolean;
  created_at: string;
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
};

export type LocalState = {
  residents: Resident[];
  capsules: Capsule[];
};