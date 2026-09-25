import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Switch, Text, View } from "react-native";

import { api } from "../api";
import type { Question, ThemeInfo } from "../types";
import { Icon } from "../ui/primitives";
import type { ScreenProps } from "../ui/types";

type Props = ScreenProps & { onBack: () => void; onNotice: (message: string) => void; onChanged: () => void };

/** Administration de la banque de 400 questions (critère BT-06). */
export function QuestionBankScreen({ styles, colors, insets, onBack, onNotice, onChanged }: Props) {
  const [themes, setThemes] = useState<ThemeInfo[]>([]);
  const [theme, setTheme] = useState<string | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.themes().then(setThemes).catch(() => onNotice("Banque de questions indisponible hors connexion.")).finally(() => setLoading(false));
  }, [onNotice]);

  const openTheme = async (name: string) => {
    setTheme(name);
    setLoading(true);
    try {
      setQuestions(await api.adminQuestions(name));
    } catch {
      onNotice("Questions indisponibles hors connexion.");
    } finally {
      setLoading(false);
    }
  };

  const toggle = async (question: Question, active: boolean) => {
    setQuestions((list) => list.map((item) => (item.id === question.id ? { ...item, active } : item)));
    try {
      await api.toggleQuestion(question.id, active);
      onChanged();
    } catch {
      setQuestions((list) => list.map((item) => (item.id === question.id ? { ...item, active: !active } : item)));
      onNotice("Modification impossible pour le moment.");
    }
  };

  return <ScrollView testID="question-bank-screen" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
    <View style={styles.header}>
      <Pressable testID="question-bank-back" accessibilityRole="button" accessibilityLabel="Retour" onPress={() => (theme ? setTheme(null) : onBack())} style={styles.backButton}><Icon name="arrow-back" color={colors.onSurface} /></Pressable>
      <Text style={styles.eyebrow}>Banque de questions</Text>
      <View style={{ width: 48 }} />
    </View>
    <View><Text style={styles.title}>{theme ?? "20 thèmes de vie"}</Text><Text style={styles.body}>{theme ? "Désactivez une question pour ne plus la proposer. Elle reste dans la banque." : "Les thèmes sensibles se gèrent aussi depuis « Fonctions de la bêta »."}</Text></View>
    {loading ? <ActivityIndicator color={colors.brandPrimary} /> : theme
      ? questions.map((question) => <View testID={`question-row-${question.id}`} key={question.id} style={styles.statRow}>
        <View style={{ flex: 1, gap: 3 }}><Text style={styles.body}>{question.number}. {question.text}</Text><Text style={styles.small}>{question.level} · {question.usage}</Text></View>
        <Switch testID={`question-toggle-${question.id}`} value={question.active !== false} onValueChange={(value) => void toggle(question, value)} trackColor={{ false: colors.borderStrong, true: colors.brandPrimary }} thumbColor={colors.onBrandPrimary} />
      </View>)
      : themes.map((item) => <Pressable testID={`question-theme-${item.theme}`} key={item.theme} accessibilityRole="button" onPress={() => void openTheme(item.theme)} style={({ pressed }) => [styles.statRow, pressed && styles.pressed]}>
        <View style={{ flex: 1, gap: 3 }}><Text style={styles.actionTitle}>{item.theme}</Text><Text style={styles.small}>{item.active_count}/{item.total} questions actives{item.sensitive ? ` · sensible${item.enabled ? "" : " (désactivé)"}` : ""}</Text></View>
        <Icon name="chevron-forward" color={colors.muted} size={20} />
      </Pressable>)}
  </ScrollView>;
}
