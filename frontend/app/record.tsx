import { useEffect, useState } from "react";
import { View, Pressable, ScrollView, Linking, Platform, ActivityIndicator } from "react-native";
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
import { Body, Button, Label, TextField, Title, Avatar } from "@/src/components/ui";
import { api, API_BASE, getToken } from "@/src/api/client";
import { useAuth } from "@/src/auth/auth-context";
import { useToast } from "@/src/components/toast";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Member = { id: string; display_name: string; initials_color?: string; status: string };
const MAX_PHOTOS = 10;

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
  const player = useAudioPlayer(null);
  const playStatus = useAudioPlayerStatus(player);

  const [permission, setPermission] = useState<"unknown" | "granted" | "denied" | "blocked">("unknown");
  const [uploading, setUploading] = useState(false);
  const [photos, setPhotos] = useState<{ uri: string; mime: string }[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [freeTitle, setFreeTitle] = useState("Souvenir sur le vif");

  const pickFromLibrary = async () => {
    const remaining = MAX_PHOTOS - photos.length;
    if (remaining <= 0) return toast.show("10 photos maximum par souvenir", "error");
    let perm = await ImagePicker.getMediaLibraryPermissionsAsync();
    if (perm.status !== "granted" && perm.canAskAgain) perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (perm.status !== "granted") {
      if (!perm.canAskAgain) toast.show("Autorisez l’accès aux photos dans les réglages", "error");
      else toast.show("Accès aux photos refusé", "error");
      return;
    }
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.7, allowsMultipleSelection: true, selectionLimit: remaining });
    if (!res.canceled && res.assets?.length) {
      setPhotos((prev) => [...prev, ...res.assets.map((a) => ({ uri: a.uri, mime: a.mimeType || "image/jpeg" }))].slice(0, MAX_PHOTOS));
    }
  };

  const takePhoto = async () => {
    if (photos.length >= MAX_PHOTOS) return toast.show("10 photos maximum par souvenir", "error");
    let perm = await ImagePicker.getCameraPermissionsAsync();
    if (perm.status !== "granted" && perm.canAskAgain) perm = await ImagePicker.requestCameraPermissionsAsync();
    if (perm.status !== "granted") {
      if (!perm.canAskAgain) toast.show("Autorisez l’appareil photo dans les réglages", "error");
      else toast.show("Accès à l’appareil photo refusé", "error");
      return;
    }
    const res = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (!res.canceled && res.assets?.[0]) {
      setPhotos((prev) => [...prev, { uri: res.assets[0].uri, mime: res.assets[0].mimeType || "image/jpeg" }]);
    }
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
      player.pause();
      player.replace(null);
      setRecordedUri(null);
      setDurationSec(0);
      setPreviewLoading(false);
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy).catch(() => {});
    } catch {
      toast.show("Impossible de démarrer l’enregistrement", "error");
    }
  };

  const stopRecording = async () => {
    try {
      const durationBeforeStop = Math.max(recState.durationMillis || 0, recorder.currentTime * 1000);
      await recorder.stop();
      const uri = recorder.uri;
      if (!uri) throw new Error("Aucun fichier audio créé");
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy).catch(() => {});
      setDurationSec(Math.max(1, Math.round(durationBeforeStop / 1000)));
      setRecordedUri(uri);
      setPreviewLoading(true);
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false });
      player.replace({ uri });
      setPreviewLoading(false);
    } catch {
      toast.show("Erreur à l’arrêt de l’enregistrement", "error");
    }
  };

  useEffect(() => {
    if (playStatus.isLoaded) setPreviewLoading(false);
  }, [playStatus.isLoaded]);

  const togglePlay = async () => {
    try {
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false });
      if (playStatus.playing) player.pause();
      else {
        if ((playStatus.currentTime || 0) >= (playStatus.duration || 1) - 0.1) await player.seekTo(0);
        player.play();
      }
    } catch {
      toast.show("Impossible de réécouter cet enregistrement", "error");
    }
  };

  const reRecord = () => {
    player.pause();
    player.replace(null);
    setRecordedUri(null);
    setDurationSec(0);
    setPreviewLoading(false);
  };

  const save = async () => {
    if (!recordedUri) {
      toast.show("Enregistrez d’abord votre réponse", "error");
      return;
    }
    const selectedNarratorId = narratorId || member?.id;
    if (!selectedNarratorId) {
      toast.show("Choisissez la personne qui raconte", "error");
      membersQ.refetch();
      return;
    }
    setUploading(true);
    try {
      player.pause();
      const form = new FormData();
      form.append("narrator_member_id", selectedNarratorId);
      form.append("duration_sec", String(Math.max(1, durationSec)));
      if (params.questionId) form.append("question_id", String(params.questionId));
      if (params.dailyId) form.append("daily_question_id", String(params.dailyId));
      if (params.theme) form.append("theme", String(params.theme));
      form.append("title", params.questionText ? String(params.questionText) : (freeTitle.trim() || "Souvenir sur le vif"));
      const name = `memoire-${Date.now()}.${Platform.OS === "web" ? "webm" : "m4a"}`;
      if (Platform.OS === "web") {
        const blob = await (await fetch(recordedUri)).blob();
        form.append("file", blob, name);
      } else {
        form.append("file", { uri: recordedUri, name, type: "audio/mp4" } as any);
      }
      if (photos.length) {
        for (let i = 0; i < photos.length; i++) {
          const p = photos[i];
          const pext = p.mime.includes("png") ? "png" : p.mime.includes("webp") ? "webp" : "jpg";
          const pname = `photo-${Date.now()}-${i}.${pext}`;
          if (Platform.OS === "web") {
            const pblob = await (await fetch(p.uri)).blob();
            form.append("photos", pblob, pname);
          } else {
            form.append("photos", { uri: p.uri, name: pname, type: p.mime } as any);
          }
        }
      }
      const token = await getToken();
      if (!token) throw new Error("Votre session a expiré. Reconnectez-vous.");
      const res = await fetch(`${API_BASE}/capsules`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!res.ok) {
        const raw = await res.text();
        let message = "Échec de l’envoi";
        try {
          const parsed = JSON.parse(raw);
          message = parsed.detail || parsed.message || message;
        } catch {
          if (raw) message = raw;
        }
        throw new Error(message);
      }
      const saved = await res.json();
      qc.invalidateQueries({ queryKey: ["capsules"] });
      qc.invalidateQueries({ queryKey: ["circle"] });
      qc.invalidateQueries({ queryKey: ["daily"] });
      toast.show("Votre réponse est bien enregistrée", "success");
      router.replace(`/capsule/${saved.id}`);
    } catch (e: any) {
      toast.show(e?.message || "Impossible d’enregistrer le souvenir", "error");
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
            <Title style={styles.question} testID="record-question-text">{params.questionText}</Title>
          </View>
        ) : (
          <Title style={styles.question} testID="record-question-text">Racontez ce que vous voulez transmettre</Title>
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

        {!params.questionId ? (
          <TextField
            label="NOM DU SOUVENIR"
            testID="sur-le-vif-title-input"
            value={freeTitle}
            onChangeText={setFreeTitle}
            placeholder="Un dimanche chez Mamie"
            maxLength={120}
          />
        ) : null}

        {/* Photos */}
        <Label style={styles.sectionLabel}>PHOTOS (OPTIONNEL) · {photos.length}/{MAX_PHOTOS}</Label>
        {photos.length > 0 ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.photosRow}>
            {photos.map((p, i) => (
              <View key={`${p.uri}-${i}`} style={styles.photoWrap}>
                <Image source={{ uri: p.uri }} style={styles.photoPreview} contentFit="cover" />
                <Pressable
                  style={styles.photoRemove}
                  testID={`record-photo-remove-${i}`}
                  onPress={() => setPhotos((prev) => prev.filter((_, idx) => idx !== i))}
                >
                  <X color={colors.onBrandPrimary} size={14} weight="bold" />
                </Pressable>
              </View>
            ))}
          </ScrollView>
        ) : null}
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
            <View style={styles.previewArea} testID="record-preview">
              <Label style={styles.previewTitle}>VOTRE ENREGISTREMENT</Label>
              <View style={styles.previewRow}>
              <Pressable testID="record-reset" onPress={reRecord} style={styles.smallBtn}>
                <ArrowClockwise color={colors.onSurface} size={24} />
              </Pressable>
              <Pressable testID="record-play" onPress={togglePlay} style={styles.recBtn} disabled={previewLoading}>
                {previewLoading ? (
                  <ActivityIndicator color={colors.onBrandPrimary} />
                ) : playStatus.playing ? (
                  <Pause color={colors.onBrandPrimary} size={38} weight="fill" />
                ) : (
                  <Play color={colors.onBrandPrimary} size={38} weight="fill" />
                )}
              </Pressable>
              <View style={styles.smallBtn} />
              </View>
              <Body muted style={styles.previewHelp}>Écoutez votre réponse avant de la conserver, ou recommencez.</Body>
            </View>
          )}

          <Body muted style={styles.hint}>
            {recordedUri ? "Réécoutez, puis enregistrez votre réponse" : isRecording ? "Enregistrement en cours…" : "Appuyez pour commencer à raconter"}
          </Body>
        </View>
      </ScrollView>

      {recordedUri ? (
        <View style={styles.saveArea}>
          <Button title="Enregistrer cette réponse" testID="record-save" loading={uploading} onPress={save} icon={<Check color={colors.onBrandPrimary} size={20} weight="bold" />} />
        </View>
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
  photosRow: { gap: spacing.md, paddingVertical: spacing.xs, paddingRight: spacing.md },
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
    ...Platform.select({
      web: { boxShadow: "0 6px 16px rgba(58, 51, 44, 0.20)" },
      default: {
        shadowColor: "#3A332C",
        shadowOpacity: 0.2,
        shadowRadius: 16,
        shadowOffset: { width: 0, height: 6 },
        elevation: 5,
      },
    }),
  },
  recBtnActive: { backgroundColor: colors.error },
  previewArea: { alignItems: "center", gap: spacing.md },
  previewTitle: { color: colors.brandSecondary },
  previewRow: { flexDirection: "row", alignItems: "center", gap: spacing.xl },
  previewHelp: { textAlign: "center", paddingHorizontal: spacing.md },
  smallBtn: { width: 48, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  hint: { textAlign: "center" },
  saveArea: { paddingTop: spacing.sm },
  permBox: { alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg },
  permText: { textAlign: "center" },
}));
