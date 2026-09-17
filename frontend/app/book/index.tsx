import { useState } from "react";
import { View, Pressable, ScrollView, ActivityIndicator } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CaretLeft, BookOpenText, Sparkle, CaretRight } from "phosphor-react-native";
import { Body, Card, Label, Title } from "@/src/components/ui";
import { api } from "@/src/api/client";
import { useToast } from "@/src/components/toast";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

type BookStatus = { memory_count: number; transcribed: number; pending: number; chapter_count: number; can_generate: boolean };
type Chapter = { id: string; title: string; memory_count: number; created_at: string };

export default function BookHome() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const toast = useToast();
  const qc = useQueryClient();
  const [generating, setGenerating] = useState(false);

  const statusQ = useQuery({ queryKey: ["book-status"], queryFn: () => api.get<BookStatus>("/book/status") });
  const chaptersQ = useQuery({ queryKey: ["chapters"], queryFn: () => api.get<Chapter[]>("/book/chapters") });

  const generate = async () => {
    setGenerating(true);
    try {
      const ch = await api.post<Chapter>("/book/chapters");
      qc.invalidateQueries({ queryKey: ["chapters"] });
      qc.invalidateQueries({ queryKey: ["book-status"] });
      toast.show("Votre chapitre est écrit ✨", "success");
      router.push(`/book/${ch.id}`);
    } catch (e: any) {
      toast.show(e?.message || "Génération impossible", "error");
    } finally {
      setGenerating(false);
    }
  };

  const status = statusQ.data;

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Pressable onPress={() => router.back()} hitSlop={12} testID="book-back">
          <CaretLeft color={colors.onSurface} size={26} />
        </Pressable>
        <Title style={styles.headerTitle}>Livre romancé</Title>
        <View style={{ width: 26 }} />
      </View>

      <ScrollView
        contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + spacing.xxl }]}
        showsVerticalScrollIndicator={false}
      >
        <Card style={styles.hero}>
          <View style={styles.heroIcon}>
            <BookOpenText color={colors.brandPrimary} size={34} weight="duotone" />
          </View>
          <Title style={styles.heroTitle}>Transformez vos souvenirs en roman</Title>
          <Body muted style={styles.heroText}>
            L’intelligence artificielle tisse les souvenirs de votre famille en un chapitre romancé,
            où chaque proche devient un personnage.
          </Body>
          {status ? (
            <Body style={styles.statusLine}>
              {status.memory_count} souvenir{status.memory_count > 1 ? "s" : ""} · {status.transcribed} transcrit{status.transcribed > 1 ? "s" : ""}
              {status.pending > 0 ? ` · ${status.pending} en cours` : ""}
            </Body>
          ) : null}

          <Pressable
            testID="book-generate"
            onPress={generate}
            disabled={generating || !status?.can_generate}
            style={[styles.genBtn, (generating || !status?.can_generate) && styles.genBtnDisabled]}
          >
            {generating ? (
              <>
                <ActivityIndicator color={colors.onBrandPrimary} />
                <Label style={styles.genText}>L’auteur écrit votre chapitre…</Label>
              </>
            ) : (
              <>
                <Sparkle color={colors.onBrandPrimary} size={20} weight="fill" />
                <Label style={styles.genText}>Générer un chapitre</Label>
              </>
            )}
          </Pressable>
          {!status?.can_generate ? (
            <Body muted style={styles.hint}>Enregistrez au moins un souvenir pour commencer.</Body>
          ) : status?.pending ? (
            <Body muted style={styles.hint}>Astuce : attendez la fin des transcriptions pour un texte plus riche.</Body>
          ) : null}
        </Card>

        <Label style={styles.section}>MES CHAPITRES</Label>
        {chaptersQ.isLoading ? (
          <ActivityIndicator color={colors.brandSecondary} style={{ marginTop: spacing.md }} />
        ) : (chaptersQ.data?.length ?? 0) === 0 ? (
          <Body muted style={styles.empty}>Aucun chapitre pour l’instant. Créez le premier ci-dessus.</Body>
        ) : (
          chaptersQ.data?.map((ch) => (
            <Pressable key={ch.id} testID={`chapter-${ch.id}`} onPress={() => router.push(`/book/${ch.id}`)}>
              <Card style={styles.chapterCard}>
                <View style={styles.chapterInfo}>
                  <Body style={styles.chapterTitle} numberOfLines={2}>{ch.title}</Body>
                  <Label style={styles.chapterMeta}>
                    {ch.memory_count} souvenirs · {new Date(ch.created_at).toLocaleDateString("fr-FR", { day: "numeric", month: "long" })}
                  </Label>
                </View>
                <CaretRight color={colors.muted} size={20} />
              </Card>
            </Pressable>
          ))
        )}
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.xl, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerTitle: { fontSize: 22 },
  content: { padding: spacing.xl, gap: spacing.md },
  hero: { alignItems: "center", gap: spacing.sm, paddingVertical: spacing.xl },
  heroIcon: { width: 68, height: 68, borderRadius: 34, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  heroTitle: { fontSize: 24, textAlign: "center", marginTop: spacing.xs },
  heroText: { textAlign: "center" },
  statusLine: { color: colors.brandSecondary, fontSize: 13, marginTop: spacing.xs },
  genBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    backgroundColor: colors.brandPrimary,
    paddingHorizontal: spacing.xl,
    paddingVertical: 15,
    borderRadius: radius.pill,
    marginTop: spacing.md,
    alignSelf: "stretch",
  },
  genBtnDisabled: { opacity: 0.5 },
  genText: { color: colors.onBrandPrimary, fontSize: 15 },
  hint: { textAlign: "center", fontSize: 12, marginTop: spacing.xs },
  section: { color: colors.brandSecondary, marginTop: spacing.lg, marginBottom: spacing.xs },
  empty: { marginTop: spacing.sm },
  chapterCard: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  chapterInfo: { flex: 1, gap: 4 },
  chapterTitle: { fontSize: 16 },
  chapterMeta: { color: colors.muted },
}));
