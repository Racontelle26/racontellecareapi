import { useState } from "react";
import { View, Pressable, FlatList, ScrollView, ActivityIndicator } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery } from "@tanstack/react-query";
import { Play, BookOpen } from "phosphor-react-native";
import { Body, Label, Title, Avatar } from "@/src/components/ui";
import { api } from "@/src/api/client";
import { usesNativeTabs } from "@/src/navigation";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Member = { id: string; display_name: string; initials_color?: string };
type Summary = { members: Member[] };
type Capsule = {
  id: string;
  narrator_name?: string;
  narrator_color?: string;
  question_text?: string;
  theme?: string;
  duration_sec: number;
  recorded_at: string;
};

function fmtDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}
function fmtDur(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

export default function Album() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const [narrator, setNarrator] = useState<string | null>(null);

  const circleQ = useQuery({ queryKey: ["circle"], queryFn: () => api.get<Summary>("/circle") });
  const capsulesQ = useQuery({
    queryKey: ["capsules", narrator],
    queryFn: () => api.get<Capsule[]>(`/capsules${narrator ? `?narrator=${narrator}` : ""}`),
  });

  const members = circleQ.data?.members?.filter((m) => m) ?? [];

  return (
    <View style={styles.container}>
      <View style={[styles.headerWrap, { paddingTop: insets.top + spacing.lg }]}>
        <Title style={styles.title}>Album des souvenirs</Title>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipsScroll} contentContainerStyle={styles.chipsRow}>
          <Pressable
            testID="album-filter-all"
            onPress={() => setNarrator(null)}
            style={[styles.chip, !narrator && styles.chipActive]}
          >
            <Label style={[styles.chipText, !narrator && styles.chipTextActive]}>Tous</Label>
          </Pressable>
          {members.map((m) => {
            const active = narrator === m.id;
            return (
              <Pressable
                key={m.id}
                testID={`album-filter-${m.id}`}
                onPress={() => setNarrator(m.id)}
                style={[styles.chip, active && styles.chipActive]}
              >
                <Label style={[styles.chipText, active && styles.chipTextActive]} numberOfLines={1}>
                  {m.display_name}
                </Label>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {capsulesQ.isLoading ? (
        <ActivityIndicator color={colors.brandSecondary} style={{ marginTop: spacing.xl }} />
      ) : (capsulesQ.data?.length ?? 0) === 0 ? (
        <View style={styles.empty}>
          <View style={styles.emptyIcon}>
            <BookOpen color={colors.brand} size={48} weight="thin" />
          </View>
          <Title style={styles.emptyTitle}>Vos souvenirs s’écriront ici</Title>
          <Body muted style={styles.emptyText}>
            Enregistrez votre première voix depuis l’onglet « Raconter ».
          </Body>
        </View>
      ) : (
        <FlatList
          data={capsulesQ.data}
          keyExtractor={(c) => c.id}
          contentContainerStyle={[styles.list, { paddingBottom: bottomChrome + spacing.xxl }]}
          showsVerticalScrollIndicator={false}
          renderItem={({ item }) => (
            <Pressable style={styles.card} testID={`capsule-${item.id}`} onPress={() => router.push(`/capsule/${item.id}`)}>
              <Avatar name={item.narrator_name || "?"} color={item.narrator_color} size={46} />
              <View style={styles.cardBody}>
                <Body style={styles.cardQuestion} numberOfLines={2}>{item.question_text}</Body>
                <Label style={styles.cardMeta}>
                  {item.narrator_name} · {fmtDate(item.recorded_at)} · {fmtDur(item.duration_sec)}
                </Label>
              </View>
              <View style={styles.playBtn}>
                <Play color={colors.onBrandPrimary} size={18} weight="fill" />
              </View>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface },
  headerWrap: {
    paddingHorizontal: spacing.xl,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingBottom: spacing.sm,
  },
  title: { fontSize: 26, marginBottom: spacing.md },
  chipsScroll: { marginHorizontal: -spacing.xl },
  chipsRow: { gap: spacing.sm, paddingHorizontal: spacing.xl, height: 44, alignItems: "center" },
  chip: {
    height: 36,
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    flexShrink: 0,
    maxWidth: 200,
  },
  chipActive: { backgroundColor: colors.brandTertiary, borderColor: colors.brand },
  chipText: { color: colors.onSurfaceTertiary },
  chipTextActive: { color: colors.onBrandTertiary },
  list: { padding: spacing.xl, gap: spacing.md },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  cardBody: { flex: 1, gap: 4 },
  cardQuestion: { fontSize: 15, lineHeight: 21 },
  cardMeta: { color: colors.muted, fontSize: 12 },
  playBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.brandPrimary,
    alignItems: "center",
    justifyContent: "center",
  },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xxl, gap: spacing.md },
  emptyIcon: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyTitle: { fontSize: 22, textAlign: "center" },
  emptyText: { textAlign: "center" },
}));
