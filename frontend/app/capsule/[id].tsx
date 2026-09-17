import { useEffect, useState } from "react";
import { View, Pressable, ScrollView, ActivityIndicator } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LinearGradient } from "expo-linear-gradient";
import { useAudioPlayer, useAudioPlayerStatus, setAudioModeAsync } from "expo-audio";
import { CaretLeft, Play, Pause, Trash } from "phosphor-react-native";
import { Body, Label, Title, Avatar } from "@/src/components/ui";
import { api, audioUrl } from "@/src/api/client";
import { useToast } from "@/src/components/toast";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Capsule = {
  id: string;
  narrator_name?: string;
  narrator_color?: string;
  narrator_member_id: string;
  recorded_by_user_id: string;
  question_text?: string;
  theme?: string;
  duration_sec: number;
  recorded_at: string;
  transcript?: string | null;
  transcript_status?: string;
};

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

  const capsuleQ = useQuery({ queryKey: ["capsule", id], queryFn: () => api.get<Capsule>(`/capsules/${id}`) });
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    (async () => {
      await setAudioModeAsync({ playsInSilentMode: true }).catch(() => {});
      setUrl(await audioUrl(String(id)));
    })();
  }, [id]);

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

  const c = capsuleQ.data;
  const canDelete = !!c;

  return (
    <View style={styles.container}>
      <View style={styles.hero}>
        <LinearGradient colors={[colors.brand, colors.brandPrimary]} style={styles.heroBg} />
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
              <Avatar name={c.narrator_name || "?"} color={c.narrator_color} size={52} />
              <View>
                <Body style={styles.narratorName}>{c.narrator_name}</Body>
                <Label style={styles.date}>
                  {new Date(c.recorded_at).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })}
                </Label>
              </View>
            </View>

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
                <Body style={styles.transcriptText}>{c.transcript}</Body>
              </View>
            ) : c.transcript_status === "pending" ? (
              <View style={styles.transcriptPending}>
                <ActivityIndicator color={colors.brandSecondary} size="small" />
                <Label style={styles.transcriptHint}>Transcription en cours…</Label>
              </View>
            ) : c.transcript_status === "failed" ? (
              <Pressable
                style={styles.retry}
                testID="capsule-retranscribe"
                onPress={async () => {
                  try {
                    await api.post(`/capsules/${id}/transcribe`);
                    toast.show("Transcription relancée", "info");
                    setTimeout(() => capsuleQ.refetch(), 4000);
                  } catch {
                    toast.show("Erreur", "error");
                  }
                }}
              >
                <Label style={styles.retryText}>Relancer la transcription</Label>
              </Pressable>
            ) : null}

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
