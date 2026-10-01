import { useState } from "react";
import { View, Pressable, FlatList, ScrollView, ActivityIndicator, Platform } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery } from "@tanstack/react-query";
import { Sparkle, Microphone } from "phosphor-react-native";
import { Body, Label, Title } from "@/src/components/ui";
import { api } from "@/src/api/client";
import { useToast } from "@/src/components/toast";
import { usesNativeTabs } from "@/src/navigation";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Theme = { theme: string; question_count: number };
type Question = { id: string; text: string; theme: string };

export default function Questions() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const [selected, setSelected] = useState<string | null>(null);
  const toast = useToast();

  const themesQ = useQuery({ queryKey: ["themes"], queryFn: () => api.get<Theme[]>("/themes") });
  const activeTheme = selected ?? themesQ.data?.[0]?.theme ?? null;
  const questionsQ = useQuery({
    queryKey: ["questions", activeTheme],
    queryFn: () => api.get<Question[]>(`/questions?theme=${encodeURIComponent(activeTheme!)}`),
    enabled: !!activeTheme,
  });

  const goRecord = (q: Question) => {
    api.post("/events", { event_type: "question_viewed", question_id: q.id, source: "guided" }).catch(() => {});
    router.push({ pathname: "/record", params: { questionId: q.id, theme: q.theme, questionText: q.text } });
  };

  const selectTheme = (theme: string) => {
    setSelected(theme);
    api.post("/events", { event_type: "theme_selected", theme }).catch(() => {});
  };

  const surprise = async () => {
    try {
      const q = await api.get<Question>("/questions/surprise");
      goRecord(q);
    } catch {
      toast.show("Impossible de tirer une question pour le moment. Vérifiez votre connexion.", "error");
    }
  };

  return (
    <View style={styles.container}>
      {/* Sticky header + theme chips */}
      <View style={[styles.headerWrap, { paddingTop: insets.top + spacing.lg }]}>
        <Title style={styles.title}>Raconter un souvenir</Title>
        <Body muted style={styles.sub}>Choisissez un thème puis une question qui vous inspire.</Body>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipsRow}
          style={styles.chipsScroll}
        >
          {themesQ.data?.map((t) => {
            const active = t.theme === activeTheme;
            return (
              <Pressable
                key={t.theme}
                testID={`theme-chip-${t.theme}`}
                onPress={() => selectTheme(t.theme)}
                style={[styles.chip, active && styles.chipActive]}
              >
                <Label style={[styles.chipText, active && styles.chipTextActive]} numberOfLines={1}>
                  {t.theme}
                </Label>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {questionsQ.isLoading ? (
        <ActivityIndicator color={colors.brandSecondary} style={{ marginTop: spacing.xl }} />
      ) : (
        <FlatList
          data={questionsQ.data}
          keyExtractor={(q) => q.id}
          contentContainerStyle={[styles.list, { paddingBottom: bottomChrome + 96 }]}
          showsVerticalScrollIndicator={false}
          renderItem={({ item }) => (
            <Pressable style={styles.qCard} testID={`question-${item.id}`} onPress={() => goRecord(item)}>
              <Body style={styles.qText}>{item.text}</Body>
              <View style={styles.qMic}>
                <Microphone color={colors.brandPrimary} size={20} weight="fill" />
              </View>
            </Pressable>
          )}
        />
      )}

      {/* Surprise CTA */}
      <Pressable
        testID="surprise-question-btn"
        onPress={surprise}
        style={[styles.surprise, { bottom: bottomChrome + spacing.lg }]}
      >
        <Sparkle color={colors.onBrandPrimary} size={20} weight="fill" />
        <Label style={styles.surpriseText}>Question surprise</Label>
      </Pressable>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface },
  headerWrap: {
    paddingHorizontal: spacing.xl,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingBottom: spacing.sm,
  },
  title: { fontSize: 26 },
  sub: { marginTop: 2, marginBottom: spacing.md },
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
    maxWidth: 220,
  },
  chipActive: { backgroundColor: colors.brandTertiary, borderColor: colors.brand },
  chipText: { color: colors.onSurfaceTertiary },
  chipTextActive: { color: colors.onBrandTertiary },
  list: { padding: spacing.xl, gap: spacing.md },
  qCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  qText: { flex: 1, fontSize: 16, lineHeight: 23 },
  qMic: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  surprise: {
    position: "absolute",
    alignSelf: "center",
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.brandPrimary,
    paddingHorizontal: spacing.xl,
    paddingVertical: 14,
    borderRadius: radius.pill,
    ...Platform.select({
      web: { boxShadow: "0 4px 12px rgba(47, 62, 82, 0.15)" },
      default: {
        shadowColor: "#2F3E52",
        shadowOpacity: 0.15,
        shadowRadius: 12,
        shadowOffset: { width: 0, height: 4 },
        elevation: 4,
      },
    }),
  },
  surpriseText: { color: colors.onBrandPrimary, fontSize: 15 },
}));
