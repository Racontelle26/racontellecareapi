import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { Text, View } from "react-native";

import type { Resident } from "../types";

export type IconName = keyof typeof Ionicons.glyphMap;

export function Icon({ name, color, size = 22 }: { name: IconName; color: string; size?: number }) {
  return <Ionicons name={name} color={color} size={size} />;
}

export function initials(name: string) {
  return name.trim().slice(0, 1).toUpperCase() || "?";
}

export function residentLabel(resident: Pick<Resident, "display_name" | "last_initial">) {
  return resident.last_initial ? `${resident.display_name} ${resident.last_initial}` : resident.display_name;
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" }).format(new Date(value));
}

/** Date et heure, comme l'exige la bibliothèque (critère BT-04). */
export function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export function formatDuration(seconds: number) {
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const mm = Math.floor((total % 3600) / 60).toString().padStart(2, "0");
  const ss = (total % 60).toString().padStart(2, "0");
  return hours ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function formatTrackedTime(totalMilliseconds: number) {
  const totalSeconds = Math.max(0, Math.floor(totalMilliseconds / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours} h ${minutes} min ${seconds} s`;
  if (minutes > 0) return `${minutes} min ${seconds} s`;
  return `${seconds} s`;
}

export const CONSENT_LABELS: Record<string, string> = {
  obtained: "Consentement obtenu",
  pending: "Consentement en attente",
  withdrawn: "Consentement retiré",
};

export function Avatar({ resident, size = 44, styles }: { resident: Resident; size?: number; styles: any }) {
  const radius = size / 2;
  return <View style={[size > 60 ? styles.largeAvatar : styles.avatar, { width: size, height: size, borderRadius: radius }]}>
    {resident.photo_uri
      ? <Image source={{ uri: resident.photo_uri }} style={{ width: size, height: size, borderRadius: radius }} contentFit="cover" />
      : <Text style={size > 60 ? styles.largeAvatarText : styles.avatarText}>{initials(resident.display_name)}</Text>}
  </View>;
}

export function ConsentBadge({ status, styles, colors }: { status: string; styles: any; colors: any }) {
  const ok = status === "obtained";
  return <View testID={`consent-badge-${status}`} style={[styles.consentBadge, !ok && { backgroundColor: colors.accentRose }]}>
    <Icon name={ok ? "checkmark-circle" : "alert-circle-outline"} color={ok ? colors.success : colors.onAccentRose} size={15} />
    <Text style={[styles.consentText, !ok && { color: colors.onAccentRose }]}>{CONSENT_LABELS[status] ?? status}</Text>
  </View>;
}
