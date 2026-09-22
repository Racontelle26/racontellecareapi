import { View, Pressable, ScrollView, ActivityIndicator } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CaretLeft, Trash } from "phosphor-react-native";
import { Body, Display, Label } from "@/src/components/ui";
import { api } from "@/src/api/client";
import { useToast } from "@/src/components/toast";
import { fonts, makeStyles, spacing, useTheme } from "@/src/theme";

type Chapter = { id: string; title: string; content: string; memory_count: number; created_at: string };

export default function ChapterRead() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const toast = useToast();
  const qc = useQueryClient();

  const chapterQ = useQuery({ queryKey: ["chapter", id], queryFn: () => api.get<Chapter>(`/book/chapters/${id}`) });

  const remove = async () => {
    try {
      await api.del(`/book/chapters/${id}`);
      qc.invalidateQueries({ queryKey: ["chapters"] });
      qc.invalidateQueries({ queryKey: ["book-status"] });
      toast.show("Chapitre supprimé", "info");
      router.back();
    } catch (e: any) {
      toast.show(e?.message || "Suppression impossible", "error");
    }
  };

  const c = chapterQ.data;
  const paragraphs = (c?.content || "")
    .split(/\n{2,}/)
    .map((p) => p.replace(/\n/g, " ").trim())
    .filter(Boolean);

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Pressable onPress={() => router.back()} hitSlop={12} testID="chapter-back">
          <CaretLeft color={colors.onSurface} size={26} />
        </Pressable>
        <Pressable onPress={remove} hitSlop={12} testID="chapter-delete">
          <Trash color={colors.error} size={22} />
        </Pressable>
      </View>

      {chapterQ.isLoading ? (
        <ActivityIndicator testID="chapter-loading" color={colors.brandSecondary} style={{ marginTop: spacing.xxl }} />
      ) : chapterQ.isError || !c ? (
        <View style={styles.errorState} testID="chapter-error">
          <Body muted style={styles.errorText}>Ce chapitre ne peut pas être affiché pour le moment.</Body>
          <Pressable testID="chapter-retry" onPress={() => chapterQ.refetch()} style={styles.retryButton}>
            <Label style={styles.retryText}>Réessayer</Label>
          </Pressable>
        </View>
      ) : (
        <ScrollView
          testID="chapter-content"
          contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + spacing.xxl }]}
          showsVerticalScrollIndicator={false}
        >
          <Label style={styles.kicker}>CHAPITRE · {c.memory_count} SOUVENIRS</Label>
          <Display style={styles.title} testID="chapter-title">{c.title}</Display>
          <View style={styles.rule} />
          {paragraphs.map((p, i) => (
            <Body key={i} style={[styles.para, i === 0 && styles.firstPara]}>{p}</Body>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.xl, paddingBottom: spacing.sm },
  content: { paddingHorizontal: spacing.xl, gap: spacing.md },
  kicker: { color: colors.brandSecondary, letterSpacing: 1 },
  title: { fontSize: 34, lineHeight: 40 },
  rule: { width: 48, height: 2, backgroundColor: colors.brand, marginVertical: spacing.sm },
  para: { fontSize: 17, lineHeight: 28, fontFamily: fonts.body, color: colors.onSurface },
  firstPara: { fontFamily: fonts.body },
  errorState: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md, paddingHorizontal: spacing.xl },
  errorText: { textAlign: "center" },
  retryButton: { minHeight: 44, justifyContent: "center", paddingHorizontal: spacing.lg },
  retryText: { color: colors.brandPrimary },
}));
