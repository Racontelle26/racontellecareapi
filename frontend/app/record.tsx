import { useEffect, useState } from "react";
import { View, Pressable, ScrollView, Linking, Platform } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Haptics from "expo-haptics";
import * as ImagePicker from "expo-image-picker";
import { Image } from "expo-image";
import {
  useAudioRecorder,
  useAudioRecorderState,
  useAudioPlayer,
  useAudioPlayerStatus,
  RecordingPresets,
  AudioModule,
  setAudioModeAsync,
} from "expo-audio";
import { X, Microphone, Stop, Play, Pause, ArrowClockwise, Check, ImageSquare, Camera } from "phosphor-react-native";
import { Body, Button, Label, Title, Avatar } from "@/src/components/ui";
import { api, API_BASE, getToken } from "@/src/api/client";
import { useAuth } from "@/src/auth/auth-context";
import { useToast } from "@/src/components/toast";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Member = { id: string; display_name: string; initials_color?: string; status: string };

function fmt(ms: number) {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export default function RecordScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const toast = useToast();
  const qc = useQueryClient();
  const { member } = useAuth();
  const params = useLocalSearchParams<{ questionId?: string; dailyId?: string; theme?: string; questionText?: string }>();

  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recState = useAudioRecorderState(recorder);
  const [recordedUri, setRecordedUri] = useState<string | null>(null);
  const [durationSec, setDurationSec] = useState(0);
  const player = useAudioPlayer(recordedUri || undefined);
  const playStatus = useAudioPlayerStatus(player);

  const [permission, setPermission] = useState<"unknown" | "granted" | "denied" | "blocked">("unknown");
  const [uploading, setUploading] = useState(false);
  const [photo, setPhoto] = useState<{ uri: string; mime: string } | null>(null);

  const pickFromLibrary = async () => {
    let perm = await ImagePicker.getMediaLibraryPermissionsAsync();
    if (perm.status !== "granted" && perm.canAskAgain) perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (perm.status !== "granted") {
      if (!perm.canAskAgain) toast.show("Autorisez l’accès aux photos dans les réglages", "error");
      else toast.show("Accès aux photos refusé", "error");
      return;
    }
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.7 });
    if (!res.canceled && res.assets?.[0]) setPhoto({ uri: res.assets[0].uri, mime: res.assets[0].mimeType || "image/jpeg" });
  };

  const takePhoto = async () => {
    let perm = await ImagePicker.getCameraPermissionsAsync();
    if (perm.status !== "granted" && perm.canAskAgain) perm = await ImagePicker.requestCameraPermissionsAsync();
    if (perm.status !== "granted") {
      if (!perm.canAskAgain) toast.show("Autorisez l’appareil photo dans les réglages", "error");
      else toast.show("Accès à l’appareil photo refusé", "error");
      return;
    }
    const res = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (!res.canceled && res.assets?.[0]) setPhoto({ uri: res.assets[0].uri, mime: res.assets[0].mimeType || "image/jpeg" });
  };

  const membersQ = useQuery({ queryKey: ["members"], queryFn: () => api.get<Member[]>("/circle/members") });
  const activeMembers = membersQ.data?.filter((m) => m.status === "active") ?? [];
  const [narratorId, setNarratorId] = useState<string | null>(null);
  useEffect(() => {
    if (!narratorId && member) setNarratorId(member.id);
  }, [member, narratorId]);

  useEffect(() => {
    (async () => {
      const res = await AudioModule.getRecordingPermissionsAsync();
      setPermission(res.granted ? "granted" : res.canAskAgain ? "denied" : "blocked");
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true }).catch(() => {});
    })();
  }, []);

  const ensurePermission = async (): Promise<boolean> => {
    const cur = await AudioModule.getRecordingPermissionsAsync();
    if (cur.granted) {
      setPermission("granted");
      return true;
    }
    if (cur.canAskAgain) {
      const res = await AudioModule.requestRecordingPermissionsAsync();
      setPermission(res.granted ? "granted" : res.canAskAgain ? "denied" : "blocked");
      return res.granted;
    }
    setPermission("blocked");
    return false;
  };

  const startRecording = async () => {
    const ok = await ensurePermission();
    if (!ok) {
      toast.show("Micro nécessaire pour enregistrer", "error");
      return;
    }
    try {
      setRecordedUri(null);
      await recorder.prepareToRecordAsync();
      recorder.record();
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy).catch(() => {});
    } catch {
      toast.show("Impossible de démarrer l’enregistrement", "error");
    }
  };

  const stopRecording = async () => {
    try {
      await recorder.stop();
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy).catch(() => {});
      setDurationSec(Math.round((recState.durationMillis || 0) / 1000));
      setRecordedUri(recorder.uri ?? null);
    } catch {
      toast.show("Erreur à l’arrêt de l’enregistrement", "error");
    }
  };

  const togglePlay = () => {
    if (playStatus.playing) player.pause();
    else {
      if ((playStatus.currentTime || 0) >= (playStatus.duration || 1) - 0.1) player.seekTo(0);
      player.play();
    }
  };

  const reRecord = () => {
    setRecordedUri(null);
    setDurationSec(0);
  };

  const save = async () => {
    if (!recordedUri || !narratorId) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("narrator_member_id", narratorId);
      form.append("duration_sec", String(durationSec || Math.round((recState.durationMillis || 0) / 1000)));
      if (params.questionId) form.append("question_id", String(params.questionId));
      if (params.dailyId) form.append("daily_question_id", String(params.dailyId));
      if (params.theme) form.append("theme", String(params.theme));
      if (params.questionText) form.append("title", String(params.questionText));
      const name = `memoire-${Date.now()}.${Platform.OS === "web" ? "webm" : "m4a"}`;
      if (Platform.OS === "web") {
        const blob = await (await fetch(recordedUri)).blob();
        form.append("file", blob, name);
      } else {
        form.append("file", { uri: recordedUri, name, type: "audio/m4a" } as any);
      }
      if (photo) {
        const pext = photo.mime.includes("png") ? "png" : photo.mime.includes("webp") ? "webp" : "jpg";
        const pname = `photo-${Date.now()}.${pext}`;
        if (Platform.OS === "web") {
          const pblob = await (await fetch(photo.uri)).blob();
          form.append("photo", pblob, pname);
        } else {
          form.append("photo", { uri: photo.uri, name: pname, type: photo.mime } as any);
        }
      }
      const token = await getToken();
      const res = await fetch(`${API_BASE}/capsules`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || "Échec de l’envoi");
      }
      qc.invalidateQueries({ queryKey: ["capsules"] });
      qc.invalidateQueries({ queryKey: ["circle"] });
      qc.invalidateQueries({ queryKey: ["daily"] });
      toast.show("Souvenir enregistré 🌱", "success");
      router.back();
    } catch {
      toast.show("Impossible d’enregistrer le souvenir", "error");
    } finally {
      setUploading(false);
    }
  };

  const isRecording = recState.isRecording;
  const elapsed = recordedUri ? durationSec * 1000 : recState.durationMillis || 0;

  return (
    <View style={[styles.container, { paddingTop: insets.top + spacing.md, paddingBottom: insets.bottom + spacing.lg }]}>
      <View style={styles.topBar}>
        <Pressable onPress={() => router.back()} hitSlop={12} testID="record-close">
          <X color={colors.onSurface} size={26} />
        </Pressable>
        <Label style={styles.topTitle}>{params.theme || "Souvenir libre"}</Label>
        <View style={{ width: 26 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {params.questionText ? (
          <View style={styles.questionBox}>
            <Title style={styles.question}>{params.questionText}</Title>
          </View>
        ) : (
          <Title style={styles.question}>Racontez ce que vous voulez transmettre</Title>
        )}

        {/* Narrator */}
        <Label style={styles.sectionLabel}>QUI RACONTE ?</Label>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.narrators}>
          {activeMembers.map((m) => {
            const active = narratorId === m.id;
            return (
              <Pressable
                key={m.id}
                testID={`narrator-${m.id}`}
                onPress={() => setNarratorId(m.id)}
                style={[styles.narratorItem, active && styles.narratorActive]}
              >
                <Avatar name={m.display_name} color={m.initials_color} size={40} />
                <Label style={styles.narratorName} numberOfLines={1}>{m.display_name}</Label>
              </Pressable>
            );
          })}
        </ScrollView>

        {/* Photo */}
        <Label style={styles.sectionLabel}>PHOTO (OPTIONNEL)</Label>
        {photo ? (
          <View style={styles.photoWrap}>
            <Image source={{ uri: photo.uri }} style={styles.photoPreview} contentFit="cover" />
            <Pressable style={styles.photoRemove} testID="record-photo-remove" onPress={() => setPhoto(null)}>
              <X color={colors.onBrandPrimary} size={16} weight="bold" />
            </Pressable>
          </View>
        ) : (
          <View style={styles.photoButtons}>
            <Pressable style={styles.photoBtn} testID="record-photo-library" onPress={pickFromLibrary}>
              <ImageSquare color={colors.brandPrimary} size={22} />
              <Label style={styles.photoBtnText}>Galerie</Label>
            </Pressable>
            <Pressable style={styles.photoBtn} testID="record-photo-camera" onPress={takePhoto}>
              <Camera color={colors.brandPrimary} size={22} />
              <Label style={styles.photoBtnText}>Appareil photo</Label>
            </Pressable>
          </View>
        )}

        {/* Recorder */}
        <View style={styles.recorder}>
          <Title style={styles.timer} testID="record-timer">{fmt(elapsed)}</Title>

          {permission === "blocked" ? (
            <View style={styles.permBox}>
              <Body muted style={styles.permText}>
                L’accès au micro est bloqué. Activez-le dans les réglages pour enregistrer votre voix.
              </Body>
              <Button title="Ouvrir les réglages" variant="secondary" testID="record-open-settings" onPress={() => Linking.openSettings()} />
            </View>
          ) : !recordedUri ? (
            <Pressable
              testID="record-toggle"
              onPress={isRecording ? stopRecording : startRecording}
              style={[styles.recBtn, isRecording && styles.recBtnActive]}
            >
              {isRecording ? <Stop color={colors.onBrandPrimary} size={40} weight="fill" /> : <Microphone color={colors.onBrandPrimary} size={44} weight="fill" />}
            </Pressable>
          ) : (
            <View style={styles.previewRow}>
              <Pressable testID="record-reset" onPress={reRecord} style={styles.smallBtn}>
                <ArrowClockwise color={colors.onSurface} size={24} />
              </Pressable>
              <Pressable testID="record-play" onPress={togglePlay} style={styles.recBtn}>
                {playStatus.playing ? <Pause color={colors.onBrandPrimary} size={38} weight="fill" /> : <Play color={colors.onBrandPrimary} size={38} weight="fill" />}
              </Pressable>
              <View style={styles.smallBtn} />
            </View>
          )}

          <Body muted style={styles.hint}>
            {isRecording ? "Enregistrement en cours…" : recordedUri ? "Réécoutez, puis conservez ce souvenir" : "Appuyez pour commencer à raconter"}
          </Body>
        </View>
      </ScrollView>

      {recordedUri ? (
        <Button title="Conserver ce souvenir" testID="record-save" loading={uploading} onPress={save} icon={<Check color={colors.onBrandPrimary} size={20} weight="bold" />} />
      ) : null}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface, paddingHorizontal: spacing.xl },
  topBar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  topTitle: { color: colors.brandSecondary },
  content: { gap: spacing.lg, paddingBottom: spacing.xl },
  questionBox: {
    backgroundColor: colors.brandTertiary,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  question: { fontSize: 24, lineHeight: 30, color: colors.onBrandTertiary },
  sectionLabel: { color: colors.muted },
  narrators: { gap: spacing.md, paddingVertical: spacing.xs },
  narratorItem: { alignItems: "center", gap: spacing.xs, width: 66, padding: spacing.sm, borderRadius: radius.md, borderWidth: 1, borderColor: "transparent" },
  narratorActive: { borderColor: colors.brand, backgroundColor: colors.surfaceSecondary },
  narratorName: { fontSize: 11, textAlign: "center", color: colors.onSurface },
  photoButtons: { flexDirection: "row", gap: spacing.md },
  photoBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    paddingVertical: 14,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
  },
  photoBtnText: { color: colors.brandPrimary },
  photoWrap: { alignSelf: "flex-start" },
  photoPreview: { width: 120, height: 120, borderRadius: radius.md },
  photoRemove: {
    position: "absolute",
    top: -8,
    right: -8,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.brandPrimary,
    alignItems: "center",
    justifyContent: "center",
  },
  recorder: { alignItems: "center", gap: spacing.lg, marginTop: spacing.lg },
  timer: { fontSize: 52, fontVariant: ["tabular-nums"] },
  recBtn: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: colors.brandPrimary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#3A332C",
    shadowOpacity: 0.2,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 5,
  },
  recBtnActive: { backgroundColor: colors.error },
  previewRow: { flexDirection: "row", alignItems: "center", gap: spacing.xl },
  smallBtn: { width: 48, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  hint: { textAlign: "center" },
  permBox: { alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg },
  permText: { textAlign: "center" },
}));
