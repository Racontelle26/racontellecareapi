import { useEffect, useState } from "react";
import { View, Pressable, ScrollView, ActivityIndicator, Platform } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LinearGradient } from "expo-linear-gradient";
import { Image } from "expo-image";
import * as ImagePicker from "expo-image-picker";
import { useAudioPlayer, useAudioPlayerStatus, setAudioModeAsync } from "expo-audio";
import { CaretLeft, Play, Pause, Trash, ImageSquare, X, PencilSimple, Check } from "phosphor-react-native";
import { Body, Button, Label, TextField, Title, Avatar } from "@/src/components/ui";
import { api, audioUrl, API_BASE, getToken, BACKEND_ORIGIN, localFilePart } from "@/src/api/client";
import { useAuth } from "@/src/auth/auth-context";
import { useToast } from "@/src/components/toast";
import { confirmAction } from "@/src/components/confirm";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Capsule = {
  id: string;
  question_id?: string | null;
  title?: string | null;
  narrator_name?: string;
  narrator_color?: string;
  narrator_avatar_url?: string | null;
  narrator_member_id: string;
  recorded_by_user_id: string;
  question_text?: string;
  theme?: string;
  duration_sec: number;
  recorded_at: string;
  transcript?: string | null;
  transcript_status?: string;
  photo_url?: string | null;
  photos?: { id: string; url: string }[];
};
type Member = { id: string; display_name: string; initials_color?: string; avatar_url?: string | null; relationship_label?: string | null; status: string };
const MAX_PHOTOS = 10;

function fmt(sec: number) {
  return `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, "0")}`;
}

export default function CapsuleDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const toast = useToast();
  const qc = useQueryClient();
  const { user, member } = useAuth();

  const capsuleQ = useQuery({ queryKey: ["capsule", id], queryFn: () => api.get<Capsule>(`/capsules/${id}`) });
  const membersQ = useQuery({ queryKey: ["members"], queryFn: () => api.get<Member[]>("/circle/members") });
  const [url, setUrl] = useState<string | null>(null);
  const [token, setTok] = useState<string | null>(null);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [editing, setEditing] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editNarratorId, setEditNarratorId] = useState("");
  const [editingTranscript, setEditingTranscript] = useState(false);
  const [transcriptText, setTranscriptText] = useState("");
  const [savingTranscript, setSavingTranscript] = useState(false);
  useEffect(() => {
    (async () => {
      await setAudioModeAsync({ playsInSilentMode: true }).catch(() => {});
      setUrl(await audioUrl(String(id)));
      setTok(await getToken());
    })();
  }, [id]);

  const photoList = capsuleQ.data?.photos ?? [];
  const photoSrcs = token
    ? photoList.map((p) => ({ id: p.id, uri: `${BACKEND_ORIGIN}${p.url}?token=${token}` }))
    : [];

  const addPhotos = async () => {
    const remaining = MAX_PHOTOS - photoList.length;
    if (remaining <= 0) return toast.show("10 photos maximum par souvenir", "error");
    let perm = await ImagePicker.getMediaLibraryPermissionsAsync();
    if (perm.status !== "granted" && perm.canAskAgain) perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (perm.status !== "granted") {
      toast.show("Accès aux photos refusé", "error");
      return;
    }
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.7, allowsMultipleSelection: true, selectionLimit: remaining });
    if (res.canceled || !res.assets?.length) return;
    setUploadingPhoto(true);
    try {
      const form = new FormData();
      for (let i = 0; i < res.assets.length; i++) {
        const asset = res.assets[i];
        const mime = asset.mimeType || "image/jpeg";
        const ext = mime.includes("png") ? "png" : mime.includes("webp") ? "webp" : "jpg";
        const name = `photo-${i}.${ext}`;
        if (Platform.OS === "web") {
          const blob = await (await fetch(asset.uri)).blob();
          form.append("photos", blob, name);
        } else {
          form.append("photos", localFilePart(asset.uri));
        }
      }
      const tk = await getToken();
      const r = await fetch(`${API_BASE}/capsules/${id}/photos`, { method: "POST", headers: { Authorization: `Bearer ${tk}` }, body: form });
      if (!r.ok) {
        const payload = await r.json().catch(() => null);
        throw new Error(payload?.detail || "Échec de l’envoi des photos");
      }
      await capsuleQ.refetch();
      qc.invalidateQueries({ queryKey: ["capsules"] });
      toast.show("Photo(s) ajoutée(s)", "success");
    } catch (e: any) {
      toast.show(e?.message || "Échec de l’envoi des photos", "error");
    } finally {
      setUploadingPhoto(false);
    }
  };

  const removePhoto = async (photoId: string) => {
    if (!(await confirmAction("Retirer cette photo ?", "La photo sera retirée de ce souvenir.", "Retirer"))) return;
    try {
      await api.del(`/capsules/${id}/photos/${photoId}`);
      await capsuleQ.refetch();
      qc.invalidateQueries({ queryKey: ["capsules"] });
    } catch {
      toast.show("Suppression impossible", "error");
    }
  };

  const player = useAudioPlayer(url || undefined);
  const status = useAudioPlayerStatus(player);
  const progress = status.duration ? (status.currentTime || 0) / status.duration : 0;

  const toggle = () => {
    if (status.playing) player.pause();
    else {
      if ((status.currentTime || 0) >= (status.duration || 1) - 0.1) player.seekTo(0);
      player.play();
    }
  };

  const remove = async () => {
    const ok = await confirmAction(
      "Supprimer ce souvenir ?",
      "L’enregistrement, ses photos et son texte ne seront plus accessibles à la famille. Cette action est définitive.",
    );
    if (!ok) return;
    try {
      await api.del(`/capsules/${id}`);
      qc.invalidateQueries({ queryKey: ["capsules"] });
      qc.invalidateQueries({ queryKey: ["circle"] });
      toast.show("Souvenir supprimé", "info");
      router.back();
    } catch (e: any) {
      toast.show(e?.message || "Suppression impossible", "error");
    }
  };

  const saveEdit = async () => {
    if (!editTitle.trim() || !editNarratorId) return toast.show("Nom et profil familial requis", "error");
    setSavingEdit(true);
    try {
      await api.patch(`/capsules/${id}`, { title: editTitle.trim(), narrator_member_id: editNarratorId });
      await capsuleQ.refetch();
      qc.invalidateQueries({ queryKey: ["capsules"] });
      setEditing(false);
      toast.show("Souvenir mis à jour", "success");
    } catch (e: any) {
      toast.show(e?.message || "Modification impossible", "error");
    } finally {
      setSavingEdit(false);
    }
  };

  const saveTranscript = async () => {
    if (!transcriptText.trim()) return toast.show("Ajoutez le texte du souvenir", "error");
    setSavingTranscript(true);
    try {
      await api.patch(`/capsules/${id}/transcript`, { transcript: transcriptText.trim() });
      await Promise.all([capsuleQ.refetch(), qc.invalidateQueries({ queryKey: ["capsules"] }), qc.invalidateQueries({ queryKey: ["book-status"] })]);
      setEditingTranscript(false);
      toast.show("Texte du souvenir enregistré", "success");
    } catch (e: any) {
      toast.show(e?.message || "Enregistrement impossible", "error");
    } finally {
      setSavingTranscript(false);
    }
  };

  const c = capsuleQ.data;
  const canDelete = !!c && (c.recorded_by_user_id === user?.id || member?.role === "owner");
  const canEditFree = !!c && !c.question_id && (c.recorded_by_user_id === user?.id || member?.role === "owner");
  const activeMembers = membersQ.data?.filter((item) => item.status === "active") ?? [];

  return (
    <View style={styles.container}>
      <View style={styles.hero}>
        {photoSrcs.length > 0 ? (
          <Image source={{ uri: photoSrcs[0].uri }} style={styles.heroBg} contentFit="cover" transition={200} />
        ) : (
          <LinearGradient colors={[colors.brand, colors.brandPrimary]} style={styles.heroBg} />
        )}
        <LinearGradient colors={["transparent", colors.surfaceInverse]} style={styles.scrim} />
        <View style={[styles.heroContent, { paddingTop: insets.top + spacing.md }]}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="capsule-back">
            <CaretLeft color={colors.onBrandPrimary} size={26} />
          </Pressable>
          {c ? (
            <View style={styles.heroText}>
              <Label style={styles.heroTheme}>{c.theme?.toUpperCase()}</Label>
              <Title style={styles.heroQuestion}>{c.question_text}</Title>
            </View>
          ) : null}
        </View>
      </View>

      <ScrollView contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + spacing.xl }]} showsVerticalScrollIndicator={false}>
        {capsuleQ.isLoading || !c ? (
          <ActivityIndicator color={colors.brandSecondary} style={{ marginTop: spacing.xxl }} />
        ) : (
          <>
            <View style={styles.narratorRow}>
              <Avatar name={c.narrator_name || "?"} color={c.narrator_color} photo={c.narrator_avatar_url} size={52} />
              <View>
                <Body style={styles.narratorName}>{c.narrator_name}</Body>
                <Label style={styles.date}>
                  {new Date(c.recorded_at).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })}
                  {" à "}
                  {new Date(c.recorded_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                  {c.theme ? ` · ${c.theme}` : ""}
                </Label>
              </View>
            </View>

            {canEditFree ? editing ? (
              <View style={styles.editCard} testID="sur-le-vif-edit-form">
                <Label style={styles.editLabel}>MODIFIER CE SOUVENIR</Label>
                <TextField label="NOM DU SOUVENIR" testID="sur-le-vif-title-edit" value={editTitle} onChangeText={setEditTitle} maxLength={120} />
                <Label style={styles.pickerLabel}>RATTACHER AU PROFIL DE</Label>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.memberPicker} testID="sur-le-vif-narrator-picker">
                  {activeMembers.map((item) => {
                    const selected = editNarratorId === item.id;
                    return <Pressable key={item.id} testID={`sur-le-vif-narrator-${item.id}`} onPress={() => setEditNarratorId(item.id)} style={[styles.pickerItem, selected && styles.pickerSelected]}>
                      <Avatar name={item.display_name} color={item.initials_color} photo={item.avatar_url} size={38} />
                      <Label style={styles.pickerName} numberOfLines={1}>{item.display_name}</Label>
                    </Pressable>;
                  })}
                </ScrollView>
                <Button title="Enregistrer les modifications" testID="sur-le-vif-save-button" loading={savingEdit} onPress={saveEdit} icon={<Check color={colors.onBrandPrimary} size={18} weight="bold" />} />
                <Pressable testID="sur-le-vif-edit-cancel" onPress={() => setEditing(false)} style={styles.cancelEdit}><Label style={styles.cancelEditText}>Annuler</Label></Pressable>
              </View>
            ) : (
              <Pressable testID="sur-le-vif-rename-button" onPress={() => {
                setEditTitle(c.title || c.question_text || "Souvenir sur le vif");
                setEditNarratorId(c.narrator_member_id);
                setEditing(true);
              }} style={styles.editButton}>
                <PencilSimple color={colors.brandPrimary} size={19} />
                <Label style={styles.editButtonText}>Renommer ou changer de profil</Label>
              </Pressable>
            ) : null}

            {photoSrcs.length > 0 ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.galleryRow}>
                {photoSrcs.map((p) => (
                  <View key={p.id} style={styles.galleryItem}>
                    <Image source={{ uri: p.uri }} style={styles.galleryImg} contentFit="cover" transition={150} />
                    {canDelete ? (
                      <Pressable style={styles.galleryRemove} testID={`capsule-photo-remove-${p.id}`} onPress={() => removePhoto(p.id)}>
                        <X color={colors.onBrandPrimary} size={13} weight="bold" />
                      </Pressable>
                    ) : null}
                  </View>
                ))}
              </ScrollView>
            ) : null}

            <Pressable style={styles.photoAction} testID="capsule-change-photo" onPress={addPhotos} disabled={uploadingPhoto || photoSrcs.length >= MAX_PHOTOS}>
              {uploadingPhoto ? (
                <ActivityIndicator color={colors.brandPrimary} size="small" />
              ) : (
                <ImageSquare color={colors.brandPrimary} size={20} />
              )}
              <Label style={styles.photoActionText}>{photoSrcs.length >= MAX_PHOTOS ? "10 photos maximum" : `${photoSrcs.length > 0 ? "Ajouter des photos" : "Ajouter une photo"} · ${photoSrcs.length}/${MAX_PHOTOS}`}</Label>
            </Pressable>

            <View style={styles.playerCard}>
              <Pressable style={styles.playBtn} testID="capsule-play" onPress={toggle} disabled={!url}>
                {status.playing ? <Pause color={colors.onBrandPrimary} size={30} weight="fill" /> : <Play color={colors.onBrandPrimary} size={30} weight="fill" />}
              </Pressable>
              <View style={styles.trackWrap}>
                <View style={styles.track}>
                  <View style={[styles.trackFill, { width: `${Math.min(1, progress) * 100}%` }]} />
                </View>
                <View style={styles.times}>
                  <Label style={styles.timeText}>{fmt(status.currentTime || 0)}</Label>
                  <Label style={styles.timeText}>{fmt(c.duration_sec)}</Label>
                </View>
              </View>
            </View>

            {c.transcript_status === "done" && c.transcript ? (
              <View style={styles.transcript}>
                <Label style={styles.transcriptLabel}>TRANSCRIPTION</Label>
                {editingTranscript ? (
                  <>
                    <TextField testID="capsule-transcript-input" value={transcriptText} onChangeText={setTranscriptText} multiline numberOfLines={6} textAlignVertical="top" maxLength={50000} style={styles.transcriptField} />
                    <Button title="Enregistrer le texte" testID="capsule-transcript-save" loading={savingTranscript} onPress={saveTranscript} />
                  </>
                ) : (
                  <>
                    <Body style={styles.transcriptText} testID="capsule-transcript-text">{c.transcript}</Body>
                    <Pressable testID="capsule-transcript-edit" onPress={() => { setTranscriptText(c.transcript || ""); setEditingTranscript(true); }} style={styles.transcriptEdit}>
                      <PencilSimple color={colors.brandPrimary} size={18} />
                      <Label style={styles.retryText}>Modifier le texte</Label>
                    </Pressable>
                  </>
                )}
              </View>
            ) : c.transcript_status === "pending" ? (
              <View style={styles.transcriptPending}>
                <ActivityIndicator color={colors.brandSecondary} size="small" />
                <Label style={styles.transcriptHint}>Transcription en cours…</Label>
              </View>
            ) : (
              <View style={styles.transcript} testID="capsule-transcript-manual">
                <Label style={styles.transcriptLabel}>TEXTE DU SOUVENIR</Label>
                <Body muted style={styles.transcriptHint}>Écrivez le souvenir ou utilisez le micro de votre clavier pour l’ajouter au livre.</Body>
                <TextField testID="capsule-transcript-input" value={transcriptText} onChangeText={setTranscriptText} placeholder="Dictez ou écrivez votre souvenir…" multiline numberOfLines={6} textAlignVertical="top" maxLength={50000} style={styles.transcriptField} />
                <Button title="Enregistrer le texte" testID="capsule-transcript-save" loading={savingTranscript} onPress={saveTranscript} />
              </View>
            )}

            {canDelete ? (
              <Pressable style={styles.delete} testID="capsule-delete" onPress={remove}>
                <Trash color={colors.error} size={20} />
                <Label style={styles.deleteText}>Supprimer ce souvenir</Label>
              </Pressable>
            ) : null}
          </>
        )}
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface },
  hero: { height: 260 },
  heroBg: { ...StyleSheetAbsolute() },
  scrim: { ...StyleSheetAbsolute() },
  heroContent: { flex: 1, justifyContent: "space-between", paddingHorizontal: spacing.xl, paddingBottom: spacing.lg },
  heroText: { gap: spacing.xs },
  heroTheme: { color: colors.onBrandPrimary, opacity: 0.85 },
  heroQuestion: { color: colors.onBrandPrimary, fontSize: 26, lineHeight: 32 },
  body: { padding: spacing.xl, gap: spacing.xl },
  narratorRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  narratorName: { fontSize: 17 },
  date: { color: colors.muted },
  editButton: { minHeight: 48, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill },
  editButtonText: { color: colors.brandPrimary },
  editCard: { gap: spacing.md, padding: spacing.lg, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg },
  editLabel: { color: colors.brandSecondary },
  pickerLabel: { color: colors.muted, marginTop: spacing.xs },
  memberPicker: { gap: spacing.sm, paddingVertical: spacing.xs },
  pickerItem: { width: 72, alignItems: "center", gap: spacing.xs, padding: spacing.sm, borderWidth: 1, borderColor: "transparent", borderRadius: radius.md },
  pickerSelected: { borderColor: colors.brandPrimary, backgroundColor: colors.brandTertiary },
  pickerName: { fontSize: 11, color: colors.onSurface, textAlign: "center" },
  cancelEdit: { minHeight: 44, alignItems: "center", justifyContent: "center" },
  cancelEditText: { color: colors.muted },
  photoAction: { flexDirection: "row", alignItems: "center", gap: spacing.sm, alignSelf: "flex-start" },
  photoActionText: { color: colors.brandPrimary },
  galleryRow: { gap: spacing.md, paddingVertical: spacing.xs },
  galleryItem: { position: "relative" },
  galleryImg: { width: 110, height: 110, borderRadius: radius.md },
  galleryRemove: {
    position: "absolute",
    top: -6,
    right: -6,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.brandPrimary,
    alignItems: "center",
    justifyContent: "center",
  },
  playerCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.lg,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  playBtn: { width: 56, height: 56, borderRadius: 28, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center" },
  trackWrap: { flex: 1, gap: spacing.sm },
  track: { height: 6, backgroundColor: colors.surfaceTertiary, borderRadius: radius.pill, overflow: "hidden" },
  trackFill: { height: 6, backgroundColor: colors.brandSecondary, borderRadius: radius.pill },
  times: { flexDirection: "row", justifyContent: "space-between" },
  timeText: { color: colors.muted, fontSize: 11 },
  transcript: { backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.sm },
  transcriptLabel: { color: colors.brandSecondary, letterSpacing: 0.5 },
  transcriptText: { fontSize: 16, lineHeight: 25 },
  transcriptField: { minHeight: 130, paddingTop: spacing.md },
  transcriptEdit: { minHeight: 44, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm },
  transcriptPending: { flexDirection: "row", alignItems: "center", gap: spacing.sm, justifyContent: "center", paddingVertical: spacing.md },
  transcriptHint: { color: colors.muted },
  retry: { alignItems: "center", paddingVertical: spacing.md },
  retryText: { color: colors.brandPrimary },
  delete: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, padding: spacing.md },
  deleteText: { color: colors.error },
}));

function StyleSheetAbsolute() {
  return { position: "absolute" as const, left: 0, right: 0, top: 0, bottom: 0 };
}
