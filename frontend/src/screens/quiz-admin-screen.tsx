import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Switch, Text, TextInput, View } from "react-native";

import { api, ApiError } from "../api";
import type { QuizItem } from "../types";
import { Icon } from "../ui/primitives";
import type { ScreenProps } from "../ui/types";

type Props = ScreenProps & { onBack: () => void; onNotice: (message: string) => void };

const RIGHTS_LABELS: Record<QuizItem["rights_status"], string> = {
  public_domain: "Domaine public",
  licensed: "Sous licence",
  provided_by_client: "Fourni par l’établissement",
  blocked: "Bloqué",
};

const CSV_HEADER = "id;type;prompt_text;audio_file;correct_answer;choice_a;choice_b;choice_c;choice_d;era;theme;difficulty;source_reference;rights_status;license_note;active";

/** Administration des contenus du quiz (annexe B, BT-18, BT-19). */
export function QuizAdminScreen({ styles, colors, insets, onBack, onNotice }: Props) {
  const [items, setItems] = useState<QuizItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [content, setContent] = useState("");
  const [importing, setImporting] = useState(false);
  const [report, setReport] = useState<string | null>(null);

  const load = useCallback(() => api.quizAdminItems()
    .then(setItems)
    .catch(() => onNotice("Contenus du quiz indisponibles hors connexion."))
    .finally(() => setLoading(false)), [onNotice]);

  useEffect(() => { void load(); }, [load]);

  const toggle = async (item: QuizItem, active: boolean) => {
    try {
      const updated = await api.updateQuizItem(item.id, { active });
      setItems((list) => list.map((entry) => (entry.id === item.id ? updated : entry)));
    } catch (reason) {
      onNotice(reason instanceof ApiError ? reason.message : "Modification impossible pour le moment.");
    }
  };

  const runImport = async () => {
    const text = content.trim();
    if (!text) return;
    setImporting(true);
    try {
      const result = await api.importQuiz(text.startsWith("[") || text.startsWith("{") ? "json" : "csv", text);
      setReport(`${result.created} ajouté(s), ${result.updated} mis à jour${result.inactive.length ? `, ${result.inactive.length} laissé(s) inactif(s) : ${result.inactive.map((entry) => `${entry.id} (${entry.reason})`).join(" ; ")}` : ""}${result.errors.length ? `, ${result.errors.length} ligne(s) en erreur` : ""}.`);
      setContent("");
      await load();
    } catch (reason) {
      setReport(reason instanceof ApiError ? reason.message : "Import impossible pour le moment.");
    } finally {
      setImporting(false);
    }
  };

  return <ScrollView testID="quiz-admin-screen" keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
    <View style={styles.header}>
      <Pressable testID="quiz-admin-back" accessibilityRole="button" accessibilityLabel="Retour" onPress={onBack} style={styles.backButton}><Icon name="arrow-back" color={colors.onSurface} /></Pressable>
      <Text style={styles.eyebrow}>Contenus du quiz</Text>
      <View style={{ width: 48 }} />
    </View>
    <View><Text style={styles.title}>Qui a dit ça ?</Text><Text style={styles.body}>Un contenu « Bloqué » ne peut jamais être activé. Un extrait musical n’est actif qu’avec son fichier et une autorisation d’usage.</Text></View>

    <View style={styles.panel}>
      <Text style={styles.actionTitle}>Importer des contenus</Text>
      <Text style={styles.small}>Collez un fichier CSV (séparateur « ; ») ou JSON. Première ligne attendue :</Text>
      <Text selectable style={[styles.small, { color: colors.onSurface }]}>{CSV_HEADER}</Text>
      <TextInput testID="quiz-import-input" value={content} onChangeText={setContent} multiline placeholder="Collez ici le contenu du fichier…" placeholderTextColor={colors.muted} style={[styles.input, styles.textArea]} autoCapitalize="none" autoCorrect={false} />
      <Pressable testID="quiz-import-submit" accessibilityRole="button" disabled={importing || !content.trim()} onPress={() => void runImport()} style={({ pressed }) => [styles.primaryButton, (!content.trim() || importing) && { opacity: 0.5 }, pressed && styles.pressed]}>{importing ? <ActivityIndicator color={colors.onBrandPrimary} /> : <Icon name="cloud-upload-outline" color={colors.onBrandPrimary} />}<Text style={styles.primaryText}>Importer</Text></Pressable>
      {report && <Text testID="quiz-import-report" style={styles.small}>{report}</Text>}
      <Text style={styles.small}>Les fichiers audio des extraits musicaux s’ajoutent ensuite par l’API (voir la procédure administrateur) ou via une URL privée dans la colonne audio_file.</Text>
    </View>

    <Text style={styles.heading}>{items.length} élément{items.length > 1 ? "s" : ""}</Text>
    {loading ? <ActivityIndicator color={colors.brandPrimary} /> : items.map((item) => <View testID={`quiz-item-${item.id}`} key={item.id} style={styles.statRow}>
      <View style={{ flex: 1, gap: 3 }}>
        <Text style={styles.body}>{item.type === "music" ? "♪ " : "« "}{item.prompt_text}{item.type === "music" ? "" : " »"}</Text>
        <Text style={styles.small}>{item.correct_answer} · {RIGHTS_LABELS[item.rights_status]}{item.era ? ` · ${item.era}` : ""}</Text>
        {item.activation_problem && <Text style={[styles.small, { color: colors.onAccentRose }]}>{item.activation_problem}</Text>}
      </View>
      <Switch testID={`quiz-item-toggle-${item.id}`} value={item.active} disabled={!item.active && !!item.activation_problem} onValueChange={(value) => void toggle(item, value)} trackColor={{ false: colors.borderStrong, true: colors.brandPrimary }} thumbColor={colors.onBrandPrimary} />
    </View>)}
  </ScrollView>;
}
