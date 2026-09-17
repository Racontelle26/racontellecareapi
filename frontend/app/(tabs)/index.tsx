import { ScrollView, View, Pressable, RefreshControl, ActivityIndicator, Image } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, SkipForward, Plus, BookOpenText, Microphone } from "phosphor-react-native";
import { Body, Card, Display, Label, Title, Avatar } from "@/src/components/ui";
import { GrowingTree } from "@/src/components/growing-tree";
import { api } from "@/src/api/client";
import { usesNativeTabs } from "@/src/navigation";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

type TreeLevel = { level: number; max_level: number; count: number; next_at: number | null };
type Member = { id: string; display_name: string; initials_color?: string; relationship_label?: string | null; status: string };
type Summary = {
  circle: { name: string };
  members: Member[];
  member_count: number;
  capsule_count: number;
  total_seconds: number;
  tree_level: TreeLevel;
};
type DailyItem = {
  daily_question_id: string;
  question: { id: string; text: string; theme: string } | null;
  theme: string;
  my_state: string;
  answered_count: number;
};

export default function Home() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;

  const circleQ = useQuery({ queryKey: ["circle"], queryFn: () => api.get<Summary>("/circle") });
  const dailyQ = useQuery({ queryKey: ["daily"], queryFn: () => api.get<{ date: string; items: DailyItem[] }>("/daily-question") });

  const refreshing = circleQ.isRefetching || dailyQ.isRefetching;
  const onRefresh = () => {
    circleQ.refetch();
    dailyQ.refetch();
  };

  const tree = circleQ.data?.tree_level;
  const progressPct = tree && tree.next_at ? Math.min(1, tree.count / tree.next_at) : 1;

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={[styles.content, { paddingTop: insets.top + spacing.lg, paddingBottom: bottomChrome + 96 }]}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.brandPrimary} />}
      >
        <View style={styles.header}>
          <View>
            <Label style={styles.hello}>VOTRE FAMILLE</Label>
            <Title testID="home-circle-name">{circleQ.data?.circle?.name || "…"}</Title>
          </View>
          <Image source={require("../../assets/images/racontelle-logo.png")} style={styles.logo} resizeMode="contain" />
        </View>

        {circleQ.isLoading ? (
          <View style={styles.loading}>
            <ActivityIndicator color={colors.brandSecondary} size="large" />
          </View>
        ) : (
          <View style={styles.treeCard}>
            {tree ? <GrowingTree count={tree.count} level={tree.level} maxLevel={tree.max_level} size={250} /> : null}
            <Display style={styles.treeCount} testID="home-capsule-count">
              {circleQ.data?.capsule_count ?? 0} souvenir{(circleQ.data?.capsule_count ?? 0) > 1 ? "s" : ""}
            </Display>
            <Body muted style={styles.treeSub}>
              {tree?.next_at
                ? `Encore ${tree.next_at - tree.count} pour faire grandir votre arbre`
                : "Votre arbre est florissant 🌳"}
            </Body>
            <View style={styles.progressTrack}>
              <View style={[styles.progressFill, { width: `${progressPct * 100}%` }]} />
            </View>
          </View>
        )}

        {/* Book CTA */}
        <Pressable style={styles.bookCta} testID="home-book-cta" onPress={() => router.push("/book")}>
          <View style={styles.bookIcon}>
            <BookOpenText color={colors.brandPrimary} size={26} weight="duotone" />
          </View>
          <View style={styles.bookText}>
            <Body style={styles.bookTitle}>Votre livre romancé</Body>
            <Label style={styles.bookSub}>Transformez vos souvenirs en un beau chapitre</Label>
          </View>
          <ArrowRight color={colors.brandPrimary} size={20} weight="bold" />
        </Pressable>

        {/* Daily questions */}
        <View style={styles.sectionHead}>
          <Title style={styles.sectionTitle}>Questions du jour</Title>
          <Label style={styles.sectionMeta}>jusqu’à 3</Label>
        </View>

        {dailyQ.isLoading ? (
          <ActivityIndicator color={colors.brandSecondary} style={{ marginVertical: spacing.lg }} />
        ) : (
          <View style={styles.dailyList}>
            {dailyQ.data?.items.map((item) => (
              <Card key={item.daily_question_id} style={styles.dailyCard} testID={`daily-${item.daily_question_id}`}>
                <Label style={styles.theme}>{item.theme.toUpperCase()}</Label>
                <Body style={styles.question}>{item.question?.text}</Body>
                <View style={styles.dailyActions}>
                  {item.my_state === "answered" ? (
                    <Label style={styles.answered}>✓ Répondu</Label>
                  ) : (
                    <Pressable
                      style={styles.answerBtn}
                      testID={`daily-answer-${item.daily_question_id}`}
                      onPress={() =>
                        router.push({
                          pathname: "/record",
                          params: {
                            questionId: item.question?.id,
                            dailyId: item.daily_question_id,
                            theme: item.theme,
                            questionText: item.question?.text,
                          },
                        })
                      }
                    >
                      <Label style={styles.answerText}>Répondre</Label>
                      <ArrowRight color={colors.onBrandPrimary} size={16} weight="bold" />
                    </Pressable>
                  )}
                  {item.my_state !== "answered" ? (
                    <Pressable
                      style={styles.skipBtn}
                      testID={`daily-skip-${item.daily_question_id}`}
                      onPress={async () => {
                        await api.patch("/daily-question/state", { daily_question_id: item.daily_question_id, state: "skipped" });
                        dailyQ.refetch();
                      }}
                    >
                      <SkipForward color={colors.muted} size={18} />
                    </Pressable>
                  ) : null}
                </View>
              </Card>
            ))}
          </View>
        )}

        {/* Members */}
        <View style={styles.sectionHead}>
          <Title style={styles.sectionTitle}>La famille</Title>
          <Pressable onPress={() => router.push("/members")} testID="home-manage-members" hitSlop={8}>
            <Label style={styles.sectionMeta}>Gérer</Label>
          </Pressable>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.membersRow}>
          {circleQ.data?.members.map((m) => (
            <View key={m.id} style={styles.memberItem}>
              <Avatar name={m.display_name} color={m.initials_color} size={58} />
              <Label style={styles.memberName} numberOfLines={1}>{m.display_name}</Label>
              {m.status === "pending" ? <Label style={styles.pending}>en attente</Label> : null}
            </View>
          ))}
          <Pressable style={styles.addMember} testID="home-add-member" onPress={() => router.push("/members")}>
            <View style={styles.addCircle}>
              <Plus color={colors.brandPrimary} size={24} />
            </View>
            <Label style={styles.memberName}>Inviter</Label>
          </Pressable>
        </ScrollView>
      </ScrollView>

      {/* Enregistrement spontané, accès rapide */}
      <Pressable
        style={[styles.fab, { bottom: bottomChrome + spacing.lg }]}
        testID="home-spontaneous-fab"
        onPress={() => router.push("/record")}
      >
        <Microphone color={colors.onBrandPrimary} size={22} weight="fill" />
        <Label style={styles.fabText}>Sur le vif</Label>
      </Pressable>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface },
  fab: {
    position: "absolute",
    right: spacing.xl,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.brandPrimary,
    paddingHorizontal: spacing.xl,
    paddingVertical: 15,
    borderRadius: radius.pill,
    shadowColor: "#3A332C",
    shadowOpacity: 0.2,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 5,
  },
  fabText: { color: colors.onBrandPrimary, fontSize: 15 },
  content: { paddingHorizontal: spacing.xl, gap: spacing.lg },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  hello: { color: colors.muted, marginBottom: 2 },
  logo: { width: 110, height: 38 },
  loading: { height: 300, alignItems: "center", justifyContent: "center" },
  treeCard: {
    alignItems: "center",
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: spacing.xl,
    paddingHorizontal: spacing.lg,
    gap: spacing.xs,
  },
  treeCount: { fontSize: 28, marginTop: spacing.sm },
  treeSub: { textAlign: "center" },
  progressTrack: {
    height: 8,
    width: "70%",
    backgroundColor: colors.surfaceTertiary,
    borderRadius: radius.pill,
    marginTop: spacing.md,
    overflow: "hidden",
  },
  progressFill: { height: 8, backgroundColor: colors.brandSecondary, borderRadius: radius.pill },
  bookCta: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.brandTertiary,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  bookIcon: { width: 46, height: 46, borderRadius: 23, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  bookText: { flex: 1, gap: 2 },
  bookTitle: { fontSize: 16, color: colors.onBrandTertiary },
  bookSub: { color: colors.onBrandTertiary, opacity: 0.8, fontSize: 12 },
  sectionHead: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", marginTop: spacing.sm },
  sectionTitle: { fontSize: 22 },
  sectionMeta: { color: colors.brandPrimary },
  dailyList: { gap: spacing.md },
  dailyCard: { gap: spacing.sm },
  theme: { color: colors.brandSecondary, fontSize: 11 },
  question: { fontSize: 17, lineHeight: 24 },
  dailyActions: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginTop: spacing.xs },
  answerBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.brandPrimary,
    paddingHorizontal: spacing.lg,
    paddingVertical: 10,
    borderRadius: radius.pill,
  },
  answerText: { color: colors.onBrandPrimary },
  skipBtn: { padding: 8 },
  answered: { color: colors.success, fontSize: 14 },
  membersRow: { gap: spacing.lg, paddingVertical: spacing.xs, paddingRight: spacing.lg },
  memberItem: { alignItems: "center", gap: spacing.xs, width: 66 },
  memberName: { color: colors.onSurface, fontSize: 12, textAlign: "center" },
  pending: { color: colors.warning, fontSize: 10 },
  addMember: { alignItems: "center", gap: spacing.xs, width: 66 },
  addCircle: {
    width: 58,
    height: 58,
    borderRadius: 29,
    borderWidth: 1.5,
    borderColor: colors.brandTertiary,
    borderStyle: "dashed",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceSecondary,
  },
}));
