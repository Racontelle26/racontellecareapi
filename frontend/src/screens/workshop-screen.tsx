import { Pressable, ScrollView, Text, View } from "react-native";

import { Waveform } from "../components/waveform";
import type { Question, Resident, ThemeInfo } from "../types";
import { Avatar, formatDuration, Icon, residentLabel } from "../ui/primitives";
import type { ScreenProps } from "../ui/types";

export type WorkshopMode = "free" | "question";
export type WorkshopStep = "resident" | "theme" | "record" | "saved";
export type RecorderStatus = "idle" | "recording" | "paused" | "done";

type Props = ScreenProps & {
  step: WorkshopStep;
  mode: WorkshopMode;
  resident: Resident | null;
  residents: Resident[];
  themes: ThemeInfo[];
  theme: string | null;
  question: Question | null;
  recorderStatus: RecorderStatus;
  durationSeconds: number;
  voiceEnabled: boolean;
  speakingQuestion: boolean;
  onBack: () => void;
  onPickResident: (resident: Resident) => void;
  onPickTheme: (theme: string) => void;
  onSurprise: () => void;
  onAnotherQuestion: () => void;
  onChangeTheme: () => void;
  onListenQuestion: () => void;
  onModeChange: (mode: WorkshopMode) => void;
  onRecord: () => void;
  onStop: () => void;
  onReset: () => void;
  onPlay: () => void;
  onSave: () => void;
  onNext: () => void;
  onFinish: () => void;
};

export function WorkshopScreen(props: Props) {
  const { styles, colors, insets, step, mode, resident, recorderStatus } = props;
  const isQuestion = mode === "question";
  const idle = recorderStatus === "idle";
  const title = resident ? residentLabel(resident) : "Mode spontané";

  const header = <View style={styles.header}>
    <Pressable testID="workshop-back" accessibilityRole="button" accessibilityLabel="Retour" onPress={props.onBack} style={styles.backButton}><Icon name="arrow-back" color={colors.onSurface} /></Pressable>
    <Text style={styles.eyebrow}>{isQuestion ? "Souvenir guidé" : resident ? "Enregistrement libre" : "Mode spontané"}</Text>
    <View style={{ width: 48 }} />
  </View>;

  if (step === "resident") {
    return <ScrollView testID="workshop-resident-step" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
      {header}
      <View><Text style={styles.title}>Qui raconte ?</Text><Text style={styles.body}>Choisissez la personne. Le souvenir sera automatiquement rattaché à son profil et daté.</Text></View>
      <View style={styles.profileGrid}>
        {props.residents.map((item) => {
          const allowed = item.consent_status === "obtained";
          return <Pressable testID={`workshop-resident-${item.id}`} key={item.id} accessibilityRole="button" accessibilityState={{ disabled: !allowed }} onPress={() => props.onPickResident(item)} style={({ pressed }) => [styles.profileCard, !allowed && styles.themeCardDisabled, pressed && styles.pressed]}>
            <Avatar resident={item} styles={styles} size={52} />
            <View><Text style={styles.profileName}>{residentLabel(item)}</Text>{!allowed && <Text style={styles.small}>Consentement à recueillir</Text>}</View>
          </Pressable>;
        })}
      </View>
      {!props.residents.length && <View style={styles.empty}><Text style={styles.body}>Créez d’abord un profil depuis l’accueil.</Text></View>}
    </ScrollView>;
  }

  if (step === "theme") {
    return <ScrollView testID="workshop-theme-step" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
      {header}
      <View><Text style={styles.title}>{title}</Text><Text style={styles.body}>Choisissez un thème de vie, ou laissez-vous surprendre.</Text></View>
      <Pressable testID="workshop-surprise" accessibilityRole="button" onPress={props.onSurprise} style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}><Icon name="sparkles-outline" color={colors.onBrandPrimary} /><Text style={styles.primaryText}>Question surprise</Text></Pressable>
      <View style={styles.themeGrid}>
        {props.themes.map((theme) => <Pressable testID={`workshop-theme-${theme.theme}`} key={theme.theme} accessibilityRole="button" accessibilityState={{ disabled: !theme.enabled }} disabled={!theme.enabled} onPress={() => props.onPickTheme(theme.theme)} style={({ pressed }) => [styles.themeCard, !theme.enabled && styles.themeCardDisabled, pressed && styles.pressed]}>
          <Text style={styles.themeTitle}>{theme.theme}</Text>
          {theme.sensitive ? <Text style={[styles.small, { color: colors.onAccentRose }]}>{theme.enabled ? "Thème sensible · à aborder avec tact" : "Thème sensible · désactivé"}</Text> : <Text style={styles.small}>{theme.active_count} questions</Text>}
        </Pressable>)}
      </View>
      <Pressable testID="workshop-mode-free" accessibilityRole="button" onPress={() => props.onModeChange("free")} style={styles.textButton}><Text style={[styles.textButtonLabel, { textAlign: "center" }]}>Enregistrer sans question (récit libre)</Text></Pressable>
    </ScrollView>;
  }

  if (step === "saved") {
    return <ScrollView testID="workshop-saved-step" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
      {header}
      <View testID="workshop-saved" style={styles.successCard}>
        <Icon name="checkmark-circle" color={colors.success} size={56} />
        <Text style={styles.title}>Capsule sauvegardée</Text>
        <Text style={[styles.body, { textAlign: "center" }]}>{resident ? `Le souvenir est rangé dans la bibliothèque de ${residentLabel(resident)}.` : "Le souvenir est rangé dans « À classer »."} Il reste sur l’appareil jusqu’à la confirmation d’envoi.</Text>
      </View>
      <Pressable testID="workshop-next" accessibilityRole="button" onPress={props.onNext} style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}>
        <Icon name={isQuestion ? "chatbubbles-outline" : "mic-outline"} color={colors.onBrandPrimary} />
        <Text style={styles.primaryText}>{isQuestion ? "Une nouvelle question" : "Un nouvel enregistrement"}</Text>
      </Pressable>
      <Pressable testID="workshop-finish" accessibilityRole="button" onPress={props.onFinish} style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}>
        <Text style={styles.secondaryText}>{resident ? "Revenir au profil" : "Revenir à l’accueil"}</Text>
      </Pressable>
    </ScrollView>;
  }

  const micLabel = recorderStatus === "recording" ? "Micro actif · enregistrement en cours" : recorderStatus === "paused" ? "En pause" : recorderStatus === "done" ? "Enregistrement terminé · prêt à réécouter" : "Micro prêt";
  return <ScrollView testID="workshop-record-step" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
    {header}
    <View style={styles.workshopTop}><Text style={styles.title}>{title}</Text></View>
    {resident && idle && <View style={styles.modeSwitch}>
      <Pressable testID="workshop-mode-question" accessibilityRole="button" onPress={() => props.onModeChange("question")} style={({ pressed }) => [styles.modeOption, isQuestion && styles.modeOptionActive, pressed && styles.pressed]}><Icon name="chatbubble-ellipses-outline" color={isQuestion ? colors.onBrandPrimary : colors.onSurfaceSecondary} size={20} /><Text style={[styles.modeOptionText, isQuestion && styles.modeOptionTextActive]}>Question guidée</Text></Pressable>
      <Pressable testID="workshop-mode-free-switch" accessibilityRole="button" onPress={() => props.onModeChange("free")} style={({ pressed }) => [styles.modeOption, !isQuestion && styles.modeOptionActive, pressed && styles.pressed]}><Icon name="mic-outline" color={!isQuestion ? colors.onBrandPrimary : colors.onSurfaceSecondary} size={20} /><Text style={[styles.modeOptionText, !isQuestion && styles.modeOptionTextActive]}>Récit libre</Text></Pressable>
    </View>}
    {isQuestion && props.question ? <View testID="workshop-question-card" style={styles.questionCard}>
      <View style={styles.sectionHeader}>
        <Text style={styles.eyebrow}>{props.question.theme}</Text>
        {idle && <Pressable testID="workshop-change-theme" accessibilityRole="button" onPress={props.onChangeTheme} style={styles.textButton}><Text style={styles.textButtonLabel}>Changer de thème</Text></Pressable>}
      </View>
      <Text testID="workshop-question-text" style={styles.questionText}>{props.question.text}</Text>
      {props.question.sensitive && <Text style={[styles.small, { color: colors.onAccentRose }]}>Question sensible : à poser avec tact, la personne peut ne pas répondre.</Text>}
      <View style={styles.capsuleActions}>
        {idle && <Pressable testID="workshop-another-question" accessibilityRole="button" onPress={props.onAnotherQuestion} style={({ pressed }) => [styles.capsuleAction, pressed && styles.pressed]}><Icon name="refresh-outline" color={colors.brandPrimary} size={20} /><Text style={styles.capsuleActionText}>Une autre question</Text></Pressable>}
        {idle && <Pressable testID="workshop-surprise-inline" accessibilityRole="button" onPress={props.onSurprise} style={({ pressed }) => [styles.capsuleAction, pressed && styles.pressed]}><Icon name="sparkles-outline" color={colors.brandPrimary} size={20} /><Text style={styles.capsuleActionText}>Question surprise</Text></Pressable>}
        {props.voiceEnabled && <Pressable testID="workshop-listen-question" accessibilityRole="button" onPress={props.onListenQuestion} style={({ pressed }) => [styles.capsuleAction, pressed && styles.pressed]}><Icon name={props.speakingQuestion ? "stop-circle-outline" : "volume-high-outline"} color={colors.brandPrimary} size={20} /><Text style={styles.capsuleActionText}>{props.speakingQuestion ? "Lecture en cours…" : "Écouter la question"}</Text></Pressable>}
      </View>
    </View> : <View style={styles.hero}>
      <Text style={styles.heroTitle}>{resident ? "Récit libre" : "Souvenir spontané"}</Text>
      <Text style={styles.body}>{resident ? "Laissez la parole venir librement." : "Enregistrez tout de suite : vous choisirez la personne plus tard, depuis « À classer »."}</Text>
    </View>}

    <View style={styles.recorderPanel}>
      <View testID="workshop-mic-state" style={styles.micState}><Icon name={recorderStatus === "recording" ? "mic" : "mic-outline"} color={recorderStatus === "recording" ? colors.error : colors.onSurface} size={16} /><Text style={styles.micStateText}>{micLabel}</Text></View>
      <Text testID="workshop-timer" style={styles.timer}>{formatDuration(props.durationSeconds)}</Text>
      <Waveform active={recorderStatus === "recording"} />
      {recorderStatus !== "done" && <Pressable testID="workshop-record" accessibilityRole="button" accessibilityLabel={recorderStatus === "recording" ? "Mettre en pause" : recorderStatus === "paused" ? "Reprendre" : "Enregistrer"} onPress={props.onRecord} style={({ pressed }) => [styles.recordButton, recorderStatus === "recording" && styles.recordButtonActive, pressed && styles.pressed]}>
        <Icon name={recorderStatus === "recording" ? "pause" : "mic"} color={colors.onError} size={42} />
      </Pressable>}
      <Text style={styles.small}>{recorderStatus === "idle" ? "Appuyez sur le bouton pour enregistrer" : recorderStatus === "recording" ? "Appuyez pour mettre en pause · aucune limite de durée" : recorderStatus === "paused" ? "Appuyez pour reprendre" : ""}</Text>
    </View>

    {recorderStatus === "recording" || recorderStatus === "paused" ? <Pressable testID="workshop-stop" accessibilityRole="button" onPress={props.onStop} style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}><Icon name="stop" color={colors.onBrandPrimary} /><Text style={styles.primaryText}>Arrêter</Text></Pressable> : null}
    {recorderStatus === "done" ? <View style={{ gap: 12 }}>
      <View style={styles.actionRow}>
        <Pressable testID="workshop-play" accessibilityRole="button" onPress={props.onPlay} style={({ pressed }) => [styles.secondaryButton, { flex: 1 }, pressed && styles.pressed]}><Icon name="play" color={colors.brandPrimary} /><Text style={styles.secondaryText}>Réécouter</Text></Pressable>
        <Pressable testID="workshop-reset" accessibilityRole="button" onPress={props.onReset} style={({ pressed }) => [styles.secondaryButton, { flex: 1 }, pressed && styles.pressed]}><Icon name="refresh" color={colors.brandPrimary} /><Text style={styles.secondaryText}>Recommencer</Text></Pressable>
      </View>
      <Pressable testID="workshop-save" accessibilityRole="button" onPress={props.onSave} style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}><Icon name="bookmark" color={colors.onBrandPrimary} /><Text style={styles.primaryText}>Sauvegarder</Text></Pressable>
    </View> : null}
  </ScrollView>;
}
