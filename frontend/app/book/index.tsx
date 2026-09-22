import { useState } from "react";
import { View, Pressable, ScrollView, ActivityIndicator, Platform } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Print from "expo-print";
import * as Sharing from "expo-sharing";
import { CaretLeft, BookOpenText, Sparkle, CaretRight, FilePdf } from "phosphor-react-native";
import { Body, Card, Label, Title } from "@/src/components/ui";
import { api, getToken } from "@/src/api/client";
import { useToast } from "@/src/components/toast";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { buildBookHtml, openPrintPreviewWindow, printBookWindow, type PdfPhoto } from "@/src/book/book-pdf";
import { preparePdfForSharing } from "@/src/book/share-pdf";

type BookStatus = { memory_count: number; transcribed: number; pending: number; chapter_count: number; can_generate: boolean };
type Chapter = { id: string; title: string; content?: string; memory_count: number; created_at: string };
type Summary = { circle: { name: string } };
type Capsule = { id: string; photo_url?: string | null; narrator_name?: string; question_text?: string };

async function toDataUrl(url: string): Promise<string> {
  const res = await fetch(url);
  const blob = await res.blob();
  return await new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onloadend = () => resolve(r.result as string);
    r.onerror = reject;
    r.readAsDataURL(blob);
  });
}

export default function BookHome() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const toast = useToast();
  const qc = useQueryClient();
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [pdfSummary, setPdfSummary] = useState<string | null>(null);

  const statusQ = useQuery({ queryKey: ["book-status"], queryFn: () => api.get<BookStatus>("/book/status") });
  const chaptersQ = useQuery({ queryKey: ["chapters"], queryFn: () => api.get<Chapter[]>("/book/chapters") });
  const circleQ = useQuery({ queryKey: ["circle"], queryFn: () => api.get<Summary>("/circle") });

  const generate = async () => {
    if (generating) return;
    setGenerating(true);
    setGenerationError(null);
    try {
      const ch = await api.post<Chapter>("/book/chapters");
      qc.setQueryData<Chapter[]>(["chapters"], (current = []) => [ch, ...current.filter((item) => item.id !== ch.id)]);
      await Promise.all([chaptersQ.refetch(), statusQ.refetch()]);
      toast.show("Votre chapitre est écrit ✨", "success");
      router.push(`/book/${ch.id}`);
    } catch (e: any) {
      const message = e?.message || "Génération impossible";
      setGenerationError(message);
      toast.show(message, "error");
    } finally {
      setGenerating(false);
    }
  };

  const exportPdf = async () => {
    const chapterRefs = chaptersQ.data || [];
    if (chapterRefs.length === 0) {
      toast.show("Créez au moins un chapitre", "error");
      return;
    }
    const webPrintWindow = Platform.OS === "web" ? openPrintPreviewWindow() : null;
    if (Platform.OS === "web" && !webPrintWindow) {
      toast.show("Autorisez la fenêtre d’impression pour créer le PDF", "error");
      return;
    }
    setExporting(true);
    setPdfSummary(null);
    try {
      const familyName = circleQ.data?.circle?.name || "Notre famille";
      const chapters = await Promise.all(chapterRefs.map((chapter) => api.get<Required<Chapter>>(`/book/chapters/${chapter.id}`)));
      if (chapters.some((chapter) => !chapter.content?.trim())) throw new Error("Un chapitre est vide. Ouvrez-le puis réessayez.");
      const gallery: PdfPhoto[] = [];
      try {
        const caps = await api.get<Capsule[]>("/capsules");
        const withPhotos = caps.filter((c) => c.photo_url).slice(0, 30);
        const token = await getToken();
        for (const c of withPhotos) {
          try {
            const dataUrl = await toDataUrl(`${process.env.EXPO_PUBLIC_BACKEND_URL}${c.photo_url}?token=${token}`);
            gallery.push({ src: dataUrl, caption: `${c.narrator_name || ""} — ${c.question_text || ""}` });
          } catch {
            /* skip photo */
          }
        }
      } catch {
        /* gallery optional */
      }
      const date = new Date().toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
      const html = buildBookHtml(familyName, date, chapters, gallery);
      if (Platform.OS === "web") {
        const result = await printBookWindow(webPrintWindow!, html);
        if (result.chapterCount !== chapters.length || result.contentLengths.some((length) => length === 0)) {
          throw new Error("Les histoires n’ont pas toutes été intégrées au PDF");
        }
        setPdfSummary(`PDF prêt : ${result.chapterCount} histoire${result.chapterCount > 1 ? "s" : ""} incluse${result.chapterCount > 1 ? "s" : ""}.`);
      } else {
        const { uri } = await Print.printToFileAsync({ html });
        if (await Sharing.isAvailableAsync()) {
          const shareableUri = await preparePdfForSharing(uri);
          await Sharing.shareAsync(shareableUri, {
            mimeType: "application/pdf",
            dialogTitle: "Partager votre livre de famille",
            ...(Platform.OS === "ios" ? { UTI: "com.adobe.pdf" } : {}),
          });
        } else {
          throw new Error("Le partage de fichiers n’est pas disponible sur cet appareil");
        }
        setPdfSummary(`PDF prêt : ${chapters.length} histoire${chapters.length > 1 ? "s" : ""} incluse${chapters.length > 1 ? "s" : ""}.`);
      }
    } catch (e: any) {
      webPrintWindow?.close();
      toast.show(e?.message || "Création du PDF impossible", "error");
    } finally {
      setExporting(false);
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
            disabled={generating || statusQ.isLoading || !status?.can_generate}
            style={[styles.genBtn, (generating || statusQ.isLoading || !status?.can_generate) && styles.genBtnDisabled]}
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
          {generationError ? (
            <Body style={styles.generationError} testID="book-generation-error">{generationError}</Body>
          ) : null}
          {!status?.can_generate ? (
            <Body muted style={styles.hint}>Enregistrez au moins un souvenir pour commencer.</Body>
          ) : status?.pending ? (
            <Body muted style={styles.hint}>Astuce : attendez la fin des transcriptions pour un texte plus riche.</Body>
          ) : null}
        </Card>

        <View style={styles.sectionRow}>
          <Label style={styles.section}>MES CHAPITRES</Label>
          {(chaptersQ.data?.length ?? 0) > 0 ? (
            <Pressable style={styles.pdfBtn} testID="book-export-pdf" onPress={exportPdf} disabled={exporting}>
              {exporting ? (
                <ActivityIndicator color={colors.brandPrimary} size="small" />
              ) : (
                <FilePdf color={colors.brandPrimary} size={18} weight="fill" />
              )}
              <Label style={styles.pdfText}>Livre PDF</Label>
            </Pressable>
          ) : null}
        </View>
        {pdfSummary ? <Body style={styles.pdfSummary} testID="book-export-summary">{pdfSummary}</Body> : null}
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
  generationError: { color: colors.error, textAlign: "center", fontSize: 13, marginTop: spacing.xs },
  section: { color: colors.brandSecondary, marginTop: spacing.lg, marginBottom: spacing.xs },
  sectionRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  pdfBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.brandTertiary,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    borderRadius: radius.pill,
    marginTop: spacing.lg,
  },
  pdfText: { color: colors.brandPrimary },
  pdfSummary: { color: colors.success, fontSize: 13, textAlign: "right" },
  empty: { marginTop: spacing.sm },
  chapterCard: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  chapterInfo: { flex: 1, gap: 4 },
  chapterTitle: { fontSize: 16 },
  chapterMeta: { color: colors.muted },
}));
