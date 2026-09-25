import { ActivityIndicator, Pressable, Text, View } from "react-native";

import type { ThemeColors } from "../theme";
import type { Capsule, Resident } from "../types";
import { formatDateTime, formatDuration, Icon, residentLabel, type IconName } from "../ui/primitives";
import type { Styles } from "../ui/types";

export type CapsuleActions = {
  onPlay?: () => void;
  onListen?: () => void;
  onEdit?: () => void;
  onTranscribe?: () => void;
  onShare?: () => void;
  onRevokeShare?: () => void;
  onDelete?: () => void;
};

function Action({ testID, icon, label, onPress, styles, color }: { testID: string; icon: IconName; label: string; onPress: () => void; styles: Styles; color: string }) {
  return <Pressable testID={testID} accessibilityRole="button" onPress={onPress} style={({ pressed }) => [styles.capsuleAction, pressed && styles.pressed]}>
    <Icon name={icon} color={color} size={16} />
    <Text style={[styles.capsuleActionText, { color }]}>{label}</Text>
  </Pressable>;
}

/** État d'envoi visible (critère BT-14) : « En attente d'envoi » puis « Sauvegardé ». */
export function UploadStatus({ capsule, styles, colors }: { capsule: Capsule; styles: Styles; colors: ThemeColors }) {
  const saved = capsule.synced && (capsule.audio_stored || !capsule.audio_uri);
  return <View testID={`capsule-upload-${saved ? "saved" : "pending"}-${capsule.id}`} style={saved ? styles.uploadSaved : styles.uploadPending}>
    <Icon name={saved ? "cloud-done-outline" : "cloud-upload-outline"} color={saved ? colors.success : colors.onAccentRose} size={14} />
    <Text style={saved ? styles.uploadSavedText : styles.uploadPendingText}>{saved ? "Sauvegardé" : "En attente d’envoi"}</Text>
  </View>;
}

export function CapsuleRow({ styles, colors, capsule, resident, busy, playing, speaking, actions }: {
  styles: Styles;
  colors: ThemeColors;
  capsule: Capsule;
  resident?: Resident;
  busy?: boolean;
  playing?: boolean;
  speaking?: boolean;
  actions: CapsuleActions;
}) {
  const { onPlay, onListen, onEdit, onTranscribe, onShare, onRevokeShare, onDelete } = actions;
  const tag = capsule.mode === "question" ? capsule.theme : capsule.theme ?? (resident ? "Souvenir spontané" : "À classer");
  return <View testID={`capsule-${capsule.id}`} style={styles.capsule}>
    <View style={styles.capsuleTop}>
      <View style={{ flex: 1, gap: 5 }}>
        <Text style={styles.capsuleTitle}>{capsule.title ?? "Souvenir vocal"}</Text>
        <Text testID={`capsule-date-${capsule.id}`} style={styles.capsuleDate}>{formatDateTime(capsule.recorded_at)} · {formatDuration(capsule.duration_sec)}</Text>
        {resident && <Text style={styles.small}>{residentLabel(resident)}</Text>}
      </View>
      {onPlay && <Pressable testID={`capsule-play-${capsule.id}`} accessibilityRole="button" accessibilityLabel={playing ? "Pause" : "Écouter"} onPress={onPlay} style={styles.backButton}>
        <Icon name={playing ? "pause" : "play"} color={colors.brandPrimary} size={22} />
      </Pressable>}
    </View>
    {capsule.transcription ? <Text testID={`capsule-transcription-${capsule.id}`} style={styles.transcription}>« {capsule.transcription} »</Text> : null}
    <View style={styles.capsuleMeta}>
      {tag ? <View style={styles.tag}><Text style={styles.tagText}>{tag}</Text></View> : null}
      <UploadStatus capsule={capsule} styles={styles} colors={colors} />
    </View>
    {capsule.share_expires_at && <Text testID={`capsule-share-expiry-${capsule.id}`} style={styles.small}>Lien familial actif jusqu’au {formatDateTime(capsule.share_expires_at)}</Text>}
    {busy
      ? <ActivityIndicator testID={`capsule-busy-${capsule.id}`} size="small" color={colors.brandPrimary} />
      : <View style={styles.capsuleActions}>
        {onEdit && <Action testID={`capsule-edit-${capsule.id}`} icon={capsule.resident_id ? "swap-horizontal-outline" : "person-add-outline"} label={capsule.resident_id ? "Modifier / réaffecter" : "Classer"} onPress={onEdit} styles={styles} color={colors.brandPrimary} />}
        {onListen && <Action testID={`capsule-listen-${capsule.id}`} icon={speaking ? "stop-circle-outline" : "volume-high-outline"} label={speaking ? "Lecture…" : "Lire le texte"} onPress={onListen} styles={styles} color={colors.brandPrimary} />}
        {onTranscribe && <Action testID={`capsule-transcribe-${capsule.id}`} icon="text-outline" label={capsule.transcription ? "Retranscrire" : "Transcrire"} onPress={onTranscribe} styles={styles} color={colors.brandPrimary} />}
        {onShare && <Action testID={`capsule-share-${capsule.id}`} icon="share-social-outline" label={capsule.share_id ? "Remplacer le lien" : "Partager à la famille"} onPress={onShare} styles={styles} color={colors.brandPrimary} />}
        {onRevokeShare && <Action testID={`capsule-revoke-share-${capsule.id}`} icon="link-outline" label="Révoquer le lien" onPress={onRevokeShare} styles={styles} color={colors.error} />}
        {onDelete && <Action testID={`capsule-delete-${capsule.id}`} icon="trash-outline" label="Supprimer" onPress={onDelete} styles={styles} color={colors.error} />}
      </View>}
  </View>;
}
