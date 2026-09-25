import { setAudioModeAsync, useAudioPlayer, useAudioPlayerStatus } from "expo-audio";
import { useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Switch, Text, View } from "react-native";

import { api, ApiError } from "../api";
import type { QuizItem } from "../types";
import { Icon } from "../ui/primitives";
import type { ScreenProps } from "../ui/types";

type QuizType = "quote" | "music";
type Filters = { era?: string; theme?: string; difficulty?: string };

type Props = ScreenProps & { onBack: () => void; onNotice: (message: string) => void };

function shuffle<T>(list: T[]): T[] {
  const copy = [...list];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const other = Math.floor(Math.random() * (index + 1));
    [copy[index], copy[other]] = [copy[other], copy[index]];
  }
  return copy;
}

const LETTERS = ["A", "B", "C", "D"];

/**
 * Animation de groupe « Qui a dit ça ? » / « Qui chante ça ? ». Aucune réponse
 * n'est attribuée à un résident : le score, facultatif, concerne la session.
 */
export function QuizScreen({ styles, colors, insets, onBack, onNotice }: Props) {
  const [type, setType] = useState<QuizType | null>(null);
  const [filters, setFilters] = useState<Filters>({});
  const [options, setOptions] = useState<{ eras: string[]; themes: string[]; difficulties: string[] }>({ eras: [], themes: [], difficulties: [] });
  const [items, setItems] = useState<QuizItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [countScore, setCountScore] = useState(false);
  const [score, setScore] = useState(0);
  const scored = useRef(new Set<string>());
  const [audioUri, setAudioUri] = useState<string | null>(null);
  const [audioBusy, setAudioBusy] = useState(false);
  const player = useAudioPlayer(audioUri);
  const status = useAudioPlayerStatus(player);
  const wantPlay = useRef(false);

  useEffect(() => {
    void api.quizFilters().then(setOptions).catch(() => null);
  }, []);

  useEffect(() => {
    if (wantPlay.current && audioUri && status.isLoaded) {
      wantPlay.current = false;
      player.play();
    }
  }, [audioUri, player, status.isLoaded]);

  const item = items[index];
  const choices = useMemo(() => (item ? shuffle(item.choices) : []), [item]);
  const isRevealed = item ? !!revealed[item.id] : false;

  const start = async (nextType: QuizType) => {
    setType(nextType);
    setLoading(true);
    try {
      const list = await api.quizItems({ type: nextType, ...filters });
      setItems(shuffle(list));
      setIndex(0);
      setSelected(null);
      setRevealed({});
      setScore(0);
      scored.current = new Set();
    } catch (reason) {
      setItems([]);
      onNotice(reason instanceof ApiError && reason.status === 403 ? reason.message : "Le quiz demande une connexion au serveur. Réessayez dans un instant.");
    } finally {
      setLoading(false);
    }
  };

  const go = (delta: number) => {
    player.pause();
    setAudioUri(null);
    setSelected(null);
    setIndex((value) => Math.min(Math.max(value + delta, 0), Math.max(items.length - 1, 0)));
  };

  const reveal = () => {
    if (!item || isRevealed) return;
    setRevealed((value) => ({ ...value, [item.id]: true }));
    api.track("quiz_item_played", { item_id: item.id });
    if (countScore && selected === item.correct_answer && !scored.current.has(item.id)) {
      scored.current.add(item.id);
      setScore((value) => value + 1);
    }
  };

  const playExtract = async () => {
    if (!item) return;
    if (status.playing) {
      player.pause();
      return;
    }
    if (audioUri) {
      player.seekTo(0);
      player.play();
      return;
    }
    setAudioBusy(true);
    try {
      const uri = item.has_stored_audio ? await api.quizAudioUri(item.id) : item.audio_url;
      if (!uri) throw new Error("aucun extrait");
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false });
      wantPlay.current = true;
      setAudioUri(uri);
    } catch {
      onNotice("L’extrait musical ne peut pas être lu pour le moment. Vérifiez la connexion.");
    } finally {
      setAudioBusy(false);
    }
  };

  const finish = async () => {
    player.pause();
    const played = Object.keys(revealed).length;
    if (type && played) {
      await api.saveQuizSession({ quiz_type: type, item_count: played, score: countScore ? score : null }).catch(() => null);
    }
    onBack();
  };

  const filterRow = (label: string, key: keyof Filters, values: string[]) => values.length ? <View style={{ gap: 8 }}>
    <Text style={styles.eyebrow}>{label}</Text>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.archiveFilter}>
      {["", ...values].map((value) => {
        const active = (filters[key] ?? "") === value;
        return <Pressable testID={`quiz-filter-${key}-${value || "tous"}`} key={value || "tous"} onPress={() => setFilters((current) => ({ ...current, [key]: value || undefined }))} style={[styles.filter, active && styles.filterActive]}>
          <Text style={[styles.filterText, active && styles.filterTextActive]}>{value || "Tous"}</Text>
        </Pressable>;
      })}
    </ScrollView>
  </View> : null;

  const header = <View style={styles.header}>
    <Pressable testID="quiz-back" accessibilityRole="button" accessibilityLabel="Retour" onPress={() => (type ? void finish() : onBack())} style={styles.backButton}><Icon name="arrow-back" color={colors.onSurface} /></Pressable>
    <Text style={styles.eyebrow}>Animation de groupe</Text>
    <View style={{ width: 48 }} />
  </View>;

  if (!type) {
    return <ScrollView testID="quiz-screen" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
      {header}
      <View><Text style={styles.title}>Qui a dit ça ?</Text><Text style={styles.body}>Un jeu pour lancer la conversation, sans note ni évaluation : les réponses se révèlent ensemble.</Text></View>
      {filterRow("Époque", "era", options.eras)}
      {filterRow("Thème", "theme", options.themes)}
      {filterRow("Difficulté", "difficulty", options.difficulties)}
      <View style={styles.actionGrid}>
        <Pressable testID="quiz-start-quote" accessibilityRole="button" onPress={() => void start("quote")} style={({ pressed }) => [styles.actionCard, styles.actionPrimary, pressed && styles.pressed]}>
          <Icon name="chatbox-ellipses-outline" color={colors.onBrandPrimary} size={30} />
          <View><Text style={[styles.actionTitle, styles.actionTitleLight]}>Citations</Text><Text style={[styles.actionText, styles.actionTextLight]}>« Qui a dit ça ? »</Text></View>
        </Pressable>
        <Pressable testID="quiz-start-music" accessibilityRole="button" onPress={() => void start("music")} style={({ pressed }) => [styles.actionCard, styles.actionSecondary, pressed && styles.pressed]}>
          <Icon name="musical-notes-outline" color={colors.brandPrimary} size={30} />
          <View><Text style={styles.actionTitle}>Musique</Text><Text style={styles.actionText}>« Qui chante ça ? »</Text></View>
        </Pressable>
      </View>
      <View style={styles.switchRow}>
        <View style={{ flex: 1, gap: 4 }}><Text style={styles.actionTitle}>Compter les points du groupe</Text><Text style={styles.small}>Facultatif, pour la session uniquement. Aucun score n’est associé à un résident.</Text></View>
        <Switch testID="quiz-score-switch" value={countScore} onValueChange={setCountScore} trackColor={{ false: colors.borderStrong, true: colors.brandPrimary }} thumbColor={colors.onBrandPrimary} />
      </View>
    </ScrollView>;
  }

  return <ScrollView testID="quiz-play" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
    {header}
    {loading ? <View style={[styles.center, { paddingVertical: 40 }]}><ActivityIndicator size="large" color={colors.brandPrimary} /></View>
      : !item ? <View style={styles.empty}>
        <Icon name={type === "music" ? "musical-notes-outline" : "chatbox-ellipses-outline"} color={colors.brandPrimary} size={32} />
        <Text style={styles.heading}>{type === "music" ? "Aucun extrait autorisé pour le moment" : "Aucune citation pour ces filtres"}</Text>
        <Text style={[styles.body, { textAlign: "center" }]}>{type === "music" ? "Les extraits musicaux sont ajoutés par l’administrateur, avec leur autorisation d’usage." : "Essayez d’autres filtres."}</Text>
        <Pressable testID="quiz-change-mode" accessibilityRole="button" onPress={() => setType(null)} style={styles.secondaryButton}><Text style={styles.secondaryText}>Changer de jeu</Text></Pressable>
      </View>
      : <>
        <View style={styles.sectionHeader}>
          <Text style={styles.small}>{type === "music" ? "Qui chante ça ?" : "Qui a dit ça ?"} · {index + 1} / {items.length}</Text>
          {countScore && <Text testID="quiz-score" style={styles.statValue}>{score} point{score > 1 ? "s" : ""}</Text>}
        </View>
        <View style={styles.questionCard}>
          {type === "music" ? <View style={[styles.center, { gap: 16 }]}>
            <Text style={[styles.body, { textAlign: "center" }]}>{item.prompt_text}</Text>
            <Pressable testID="quiz-play-extract" accessibilityRole="button" accessibilityLabel={status.playing ? "Mettre l’extrait en pause" : "Écouter l’extrait"} onPress={() => void playExtract()} style={({ pressed }) => [styles.recordButton, styles.recordButtonActive, pressed && styles.pressed]}>
              {audioBusy ? <ActivityIndicator color={colors.onBrandPrimary} /> : <Icon name={status.playing ? "pause" : "play"} color={colors.onBrandPrimary} size={46} />}
            </Pressable>
          </View> : <Text testID="quiz-quote" style={styles.quote}>« {item.prompt_text} »</Text>}
        </View>
        <View style={{ gap: 10 }}>
          {choices.map((choice, position) => {
            const correct = isRevealed && choice === item.correct_answer;
            return <Pressable testID={`quiz-choice-${position}`} key={choice} accessibilityRole="button" accessibilityState={{ selected: selected === choice }} disabled={isRevealed} onPress={() => setSelected(choice)} style={[styles.choice, selected === choice && styles.choiceSelected, correct && styles.choiceCorrect]}>
              <View style={styles.choiceLetter}><Text style={styles.choiceLetterText}>{LETTERS[position]}</Text></View>
              <Text style={styles.choiceText}>{choice}</Text>
              {correct && <Icon name="checkmark-circle" color={colors.success} size={26} />}
            </Pressable>;
          })}
        </View>
        {isRevealed ? <View testID="quiz-answer" style={styles.successCard}>
          <Text style={styles.eyebrow}>La réponse</Text>
          <Text style={styles.title}>{item.correct_answer}</Text>
          {item.source_reference ? <Text style={[styles.small, { textAlign: "center" }]}>{item.source_reference}</Text> : null}
        </View> : <Pressable testID="quiz-reveal" accessibilityRole="button" onPress={reveal} style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}><Icon name="eye-outline" color={colors.onBrandPrimary} /><Text style={styles.primaryText}>Révéler la réponse</Text></Pressable>}
        <View style={styles.actionRow}>
          <Pressable testID="quiz-previous" accessibilityRole="button" disabled={index === 0} onPress={() => go(-1)} style={({ pressed }) => [styles.secondaryButton, { flex: 1 }, index === 0 && { opacity: 0.4 }, pressed && styles.pressed]}><Icon name="chevron-back" color={colors.brandPrimary} /><Text style={styles.secondaryText}>Précédent</Text></Pressable>
          {index < items.length - 1
            ? <Pressable testID="quiz-next" accessibilityRole="button" onPress={() => go(1)} style={({ pressed }) => [styles.secondaryButton, { flex: 1 }, pressed && styles.pressed]}><Text style={styles.secondaryText}>Suivant</Text><Icon name="chevron-forward" color={colors.brandPrimary} /></Pressable>
            : <Pressable testID="quiz-finish" accessibilityRole="button" onPress={() => void finish()} style={({ pressed }) => [styles.secondaryButton, { flex: 1 }, pressed && styles.pressed]}><Text style={styles.secondaryText}>Terminer</Text></Pressable>}
        </View>
      </>}
  </ScrollView>;
}
