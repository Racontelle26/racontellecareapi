import { Ionicons } from "@expo/vector-icons";
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioPlayer,
  useAudioRecorder,
  useAudioRecorderState,
} from "expo-audio";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { readLocalState, mergeResidents, writeLocalState } from "@/src/local";
import { makeStyles, useTheme } from "@/src/theme";
import type { Capsule, LocalState, Question, Resident } from "@/src/types";

type Screen = "home" | "profile" | "workshop" | "archive";
type WorkshopMode = "free" | "question";
type RecorderStatus = "idle" | "recording" | "paused" | "done";

const FALLBACK_QUESTIONS: Question[] = [
  { id: "q1", theme: "Enfance", text: "Quel est votre tout premier souvenir ?", sensitive: false },
  { id: "q2", theme: "Famille", text: "Qui vous faisait le plus rire dans votre famille ?", sensitive: false },
  { id: "q3", theme: "Transmission", text: "Quel conseil aimeriez-vous transmettre aux plus jeunes ?", sensitive: false },
];

const useStyles = makeStyles((colors) => ({
  root: { flex: 1, backgroundColor: colors.surface },
  screen: { paddingHorizontal: 20, gap: 24 },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  backButton: { width: 48, height: 48, borderRadius: 24, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center" },
  brand: { color: colors.brandPrimary, fontSize: 28, fontFamily: Platform.select({ ios: "Georgia", default: "serif" }), fontStyle: "italic" },
  eyebrow: { color: colors.muted, fontSize: 12, letterSpacing: 1.5, textTransform: "uppercase", fontWeight: "700" },
  title: { color: colors.onSurface, fontSize: 30, lineHeight: 36, fontFamily: Platform.select({ ios: "Georgia", default: "serif" }) },
  heading: { color: colors.onSurface, fontSize: 22, lineHeight: 28, fontWeight: "700" },
  body: { color: colors.onSurfaceSecondary, fontSize: 15, lineHeight: 22 },
  small: { color: colors.muted, fontSize: 13, lineHeight: 18 },
  status: { alignSelf: "flex-start", flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: colors.brandTertiary, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 10 },
  statusText: { color: colors.onBrandTertiary, fontSize: 13, fontWeight: "700" },
  hero: { backgroundColor: colors.surfaceSecondary, borderRadius: 24, padding: 20, borderWidth: 1, borderColor: colors.border },
  heroTitle: { color: colors.onSurface, fontSize: 20, lineHeight: 27, fontWeight: "700", marginBottom: 8 },
  actionRow: { flexDirection: "row", gap: 12 },
  actionCard: { flex: 1, minHeight: 126, borderRadius: 20, padding: 16, justifyContent: "space-between", borderWidth: 1, borderColor: colors.border },
  actionPrimary: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  actionSecondary: { backgroundColor: colors.brandTertiary },
  actionTitle: { color: colors.onSurface, fontSize: 16, fontWeight: "700", lineHeight: 21 },
  actionTitleLight: { color: colors.onBrandPrimary },
  actionText: { color: colors.onSurfaceSecondary, fontSize: 12, lineHeight: 17 },
  actionTextLight: { color: colors.onBrandPrimary, opacity: 0.88 },
  sectionHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  textButton: { minHeight: 44, justifyContent: "center", paddingHorizontal: 4 },
  textButtonLabel: { color: colors.brandPrimary, fontSize: 14, fontWeight: "700" },
  profileGrid: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  profileCard: { width: "47%", minHeight: 108, borderRadius: 18, padding: 14, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, justifyContent: "space-between" },
  avatar: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center", backgroundColor: colors.brandSecondary },
  avatarText: { color: colors.onBrandSecondary, fontSize: 18, fontWeight: "700" },
  profileName: { color: colors.onSurface, fontSize: 16, fontWeight: "700", marginTop: 10 },
  consent: { color: colors.success, fontSize: 11, fontWeight: "700", marginTop: 3 },
  empty: { borderRadius: 20, borderWidth: 1, borderColor: colors.border, borderStyle: "dashed", padding: 22, alignItems: "center", gap: 8 },
  primaryButton: { minHeight: 52, borderRadius: 18, backgroundColor: colors.brandPrimary, flexDirection: "row", gap: 10, alignItems: "center", justifyContent: "center", paddingHorizontal: 18 },
  primaryText: { color: colors.onBrandPrimary, fontSize: 16, fontWeight: "700" },
  secondaryButton: { minHeight: 52, borderRadius: 18, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.borderStrong, flexDirection: "row", gap: 10, alignItems: "center", justifyContent: "center", paddingHorizontal: 18 },
  secondaryText: { color: colors.onSurface, fontSize: 16, fontWeight: "700" },
  profileHeader: { alignItems: "center", gap: 10 },
  largeAvatar: { width: 80, height: 80, borderRadius: 40, backgroundColor: colors.brandSecondary, alignItems: "center", justifyContent: "center" },
  largeAvatarText: { color: colors.onBrandSecondary, fontSize: 30, fontWeight: "700" },
  capsule: { borderRadius: 18, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 10 },
  capsuleTop: { flexDirection: "row", justifyContent: "space-between", gap: 10 },
  capsuleTitle: { color: colors.onSurface, fontSize: 15, fontWeight: "700", flex: 1 },
  capsuleDate: { color: colors.muted, fontSize: 12 },
  capsuleMeta: { flexDirection: "row", alignItems: "center", gap: 8 },
  tag: { alignSelf: "flex-start", backgroundColor: colors.brandTertiary, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6 },
  tagText: { color: colors.onBrandTertiary, fontSize: 12, fontWeight: "700" },
  workshopTop: { gap: 10 },
  progressTrack: { height: 8, backgroundColor: colors.surfaceTertiary, borderRadius: 8, overflow: "hidden" },
  progressFill: { height: "100%", backgroundColor: colors.brandPrimary, borderRadius: 8 },
  questionCard: { backgroundColor: colors.surfaceSecondary, borderRadius: 24, padding: 22, borderWidth: 1, borderColor: colors.border, gap: 14 },
  questionText: { color: colors.onSurface, fontSize: 26, lineHeight: 34, fontFamily: Platform.select({ ios: "Georgia", default: "serif" }) },
  recorderPanel: { alignItems: "center", gap: 18, paddingVertical: 12 },
  recordButton: { width: 112, height: 112, borderRadius: 56, backgroundColor: colors.error, alignItems: "center", justifyContent: "center", borderWidth: 10, borderColor: colors.brandTertiary },
  recordButtonActive: { backgroundColor: colors.brandPrimary },
  timer: { color: colors.onSurface, fontSize: 30, fontWeight: "700", letterSpacing: 1 },
  modalBackdrop: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(44,42,41,0.24)" },
  modalCard: { backgroundColor: colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, padding: 24, borderTopWidth: 1, borderColor: colors.border, maxHeight: "88%" },
  input: { minHeight: 54, borderRadius: 16, backgroundColor: colors.surfaceTertiary, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 16, color: colors.onSurface, fontSize: 16 },
  switchRow: { minHeight: 52, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 14 },
  archiveFilter: { flexDirection: "row", gap: 8, paddingBottom: 2 },
  filter: { minHeight: 42, borderRadius: 999, paddingHorizontal: 14, justifyContent: "center", backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  filterActive: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  filterText: { color: colors.onSurfaceSecondary, fontSize: 13, fontWeight: "700" },
  filterTextActive: { color: colors.onBrandPrimary },
  center: { alignItems: "center", justifyContent: "center", gap: 12 },
  pressed: { opacity: 0.78, transform: [{ scale: 0.985 }] },
  notice: { position: "absolute", left: 18, right: 18, minHeight: 52, borderRadius: 16, paddingHorizontal: 14, paddingVertical: 12, backgroundColor: colors.info, flexDirection: "row", alignItems: "center", gap: 10, shadowColor: colors.surfaceInverse, shadowOpacity: 0.15, shadowRadius: 12, elevation: 3 },
  noticeText: { flex: 1, color: colors.onInfo, fontSize: 13, lineHeight: 18, fontWeight: "600" },
}));

function Icon({ name, color, size = 22 }: { name: keyof typeof Ionicons.glyphMap; color: string; size?: number }) {
  return <Ionicons name={name} color={color} size={size} />;
}

function initials(name: string) {
  return name.trim().slice(0, 1).toUpperCase() || "?";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" }).format(new Date(value));
}

function formatDuration(seconds: number) {
  return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;
}

export default function Index() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder) as { isRecording?: boolean; durationMillis?: number };
  const [screen, setScreen] = useState<Screen>("home");
  const [state, setState] = useState<LocalState>({ residents: [], capsules: [] });
  const [questions, setQuestions] = useState<Question[]>(FALLBACK_QUESTIONS);
  const [selectedResident, setSelectedResident] = useState<Resident | null>(null);
  const [workshopMode, setWorkshopMode] = useState<WorkshopMode>("free");
  const [questionIndex, setQuestionIndex] = useState(0);
  const [recorderStatus, setRecorderStatus] = useState<RecorderStatus>("idle");
  const [recordedUri, setRecordedUri] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [consent, setConsent] = useState(true);
  const [archiveResidentId, setArchiveResidentId] = useState<string | null>(null);
  const player = useAudioPlayer(recordedUri);
  const durationSeconds = Math.round((recorderState.durationMillis ?? 0) / 1000);
  const currentQuestion = questions[questionIndex % Math.max(questions.length, 1)] ?? FALLBACK_QUESTIONS[0];

  const refresh = useCallback(async () => {
    const local = await readLocalState();
    setState(local);
    try {
      const [remoteResidents, remoteQuestions] = await Promise.all([api.residents(), api.questions()]);
      const next = { residents: mergeResidents(local.residents, remoteResidents), capsules: local.capsules };
      setState(next);
      await writeLocalState(next);
      if (remoteQuestions.length) setQuestions(remoteQuestions);
    } catch {
      setNotice("Mode local actif : les données restent sur cet appareil.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const persist = async (next: LocalState) => {
    setState(next);
    await writeLocalState(next);
  };

  const beginWorkshop = (resident: Resident | null, mode: WorkshopMode) => {
    if (resident && resident.consent_status !== "obtained") {
      setNotice("Le consentement est nécessaire avant tout enregistrement.");
      return;
    }
    setSelectedResident(resident);
    setWorkshopMode(mode);
    setQuestionIndex(0);
    setRecorderStatus("idle");
    setRecordedUri(null);
    setScreen("workshop");
  };

  const handleRecordPress = async () => {
    try {
      if (recorderStatus === "done") return;
      if (recorderState.isRecording) {
        recorder.pause();
        setRecorderStatus("paused");
        return;
      }
      if (recorderStatus === "paused") {
        recorder.record();
        setRecorderStatus("recording");
        return;
      }
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        setNotice("L’accès au microphone est nécessaire pour enregistrer.");
        return;
      }
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      setRecorderStatus("recording");
    } catch {
      setNotice("Impossible d’accéder au microphone. Vérifiez les autorisations.");
    }
  };

  const stopRecording = async () => {
    await recorder.stop();
    setRecordedUri(recorder.uri ?? null);
    setRecorderStatus("done");
  };

  const resetRecording = () => {
    setRecordedUri(null);
    setRecorderStatus("idle");
  };

  const saveRecording = async () => {
    const capsule: Capsule = {
      id: `local-${Date.now()}`,
      resident_id: selectedResident?.id ?? null,
      question_id: workshopMode === "question" ? currentQuestion.id : null,
      mode: workshopMode,
      theme: workshopMode === "question" ? currentQuestion.theme : null,
      title: workshopMode === "question" ? currentQuestion.text : "Souvenir libre",
      duration_sec: durationSeconds,
      recorded_at: new Date().toISOString(),
      status: selectedResident ? "assigned" : "unclassified",
      synced: false,
      audio_uri: recordedUri,
    };
    const optimistic = { ...state, capsules: [capsule, ...state.capsules] };
    await persist(optimistic);
    try {
      const remote = await api.saveCapsule({
        resident_id: capsule.resident_id,
        question_id: capsule.question_id,
        mode: capsule.mode,
        theme: capsule.theme,
        title: capsule.title,
        duration_sec: capsule.duration_sec,
        recorded_at: capsule.recorded_at,
        audio_uri: capsule.audio_uri,
      });
      const synced: Capsule = { ...remote, audio_uri: recordedUri, synced: true };
      await persist({ ...optimistic, capsules: [synced, ...state.capsules] });
    } catch {
      setNotice("Souvenir conservé sur l’appareil. La copie serveur sera retentée plus tard.");
    }
    resetRecording();
    if (workshopMode === "free") {
      setWorkshopMode("question");
      setQuestionIndex(0);
      setNotice("Souvenir libre sauvegardé. Les 3 questions du jour sont prêtes.");
    } else if (questionIndex < 2) {
      setQuestionIndex((value) => value + 1);
      setNotice("Réponse sauvegardée. Passons à la prochaine question.");
    } else {
      setScreen(selectedResident ? "profile" : "home");
      setNotice("Les 3 questions du jour sont terminées. Merci pour ce moment.");
    }
  };

  const addResident = async () => {
    const displayName = draftName.trim();
    if (!displayName) return;
    if (!consent) {
      setNotice("Le consentement est requis pour enregistrer un souvenir.");
      return;
    }
    if (state.residents.length >= 10) {
      setNotice("Les 10 profils sont déjà créés.");
      return;
    }
    const localResident: Resident = { id: `local-${Date.now()}`, display_name: displayName, consent_status: "obtained", active: true, created_at: new Date().toISOString() };
    const optimistic = { ...state, residents: [...state.residents, localResident] };
    await persist(optimistic);
    try {
      const remote = await api.createResident(displayName);
      await persist({ ...optimistic, residents: optimistic.residents.map((item) => item.id === localResident.id ? remote : item) });
    } catch {
      setNotice("Profil conservé localement. La copie serveur sera retentée plus tard.");
    }
    setDraftName("");
    setConsent(true);
    setShowAdd(false);
  };

  const visibleCapsules = useMemo(() => archiveResidentId ? state.capsules.filter((item) => item.resident_id === archiveResidentId) : state.capsules, [archiveResidentId, state.capsules]);

  if (loading) {
    return <View style={[styles.root, styles.center]}><ActivityIndicator size="large" color={colors.brandPrimary} /><Text style={styles.body}>Ouverture du carnet…</Text></View>;
  }

  return (
    <View style={styles.root}>
      {screen === "home" && <HomeScreen styles={styles} colors={colors} insets={insets} state={state} onAdd={() => setShowAdd(true)} onProfile={(resident: Resident) => { setSelectedResident(resident); setScreen("profile"); }} onFree={() => beginWorkshop(null, "free")} onArchive={() => setScreen("archive")} notice={notice} />}
      {screen === "profile" && selectedResident && <ProfileScreen styles={styles} colors={colors} insets={insets} resident={selectedResident} capsules={state.capsules.filter((item) => item.resident_id === selectedResident.id)} onBack={() => setScreen("home")} onStart={() => beginWorkshop(selectedResident, "free")} onArchive={() => { setArchiveResidentId(selectedResident.id); setScreen("archive"); }} />}
      {screen === "workshop" && <WorkshopScreen styles={styles} colors={colors} insets={insets} resident={selectedResident} mode={workshopMode} questionIndex={questionIndex} question={currentQuestion} recorderStatus={recorderStatus} durationSeconds={durationSeconds} onBack={() => setScreen(selectedResident ? "profile" : "home")} onRecord={handleRecordPress} onStop={stopRecording} onReset={resetRecording} onPlay={() => player.play()} onSave={saveRecording} onSkip={() => { if (questionIndex < 2) setQuestionIndex((value) => value + 1); else { setScreen(selectedResident ? "profile" : "home"); setNotice("Atelier terminé, sans réponse enregistrée pour cette question."); } }} />}
      {screen === "archive" && <ArchiveScreen styles={styles} colors={colors} insets={insets} residents={state.residents} capsules={visibleCapsules} selectedId={archiveResidentId} onSelect={setArchiveResidentId} onBack={() => setScreen("home")} onPlay={(uri: string) => { setRecordedUri(uri); player.play(); }} />}
      {notice && <Pressable accessibilityRole="button" onPress={() => setNotice(null)} style={[styles.notice, { bottom: insets.bottom + 16 }]}><Icon name="information-circle-outline" color={colors.onInfo} size={18} /><Text style={styles.noticeText}>{notice}</Text><Icon name="close" color={colors.onInfo} size={18} /></Pressable>}
      <Modal testID="add-resident-modal" visible={showAdd} transparent animationType="slide" onRequestClose={() => setShowAdd(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false} contentContainerStyle={{ gap: 18, paddingBottom: insets.bottom + 24 }}>
            <View style={styles.sectionHeader}><Text style={styles.heading}>Nouveau profil</Text><Pressable onPress={() => setShowAdd(false)} style={styles.backButton}><Icon name="close" color={colors.onSurface} /></Pressable></View>
            <Text style={styles.body}>Un prénom ou un pseudonyme suffit. Les données restent dans le carnet de l’atelier.</Text>
            <TextInput testID="resident-name-input" value={draftName} onChangeText={setDraftName} autoFocus placeholder="Prénom ou pseudonyme" placeholderTextColor={colors.muted} style={styles.input} maxLength={80} />
            <View style={styles.switchRow}><View style={{ flex: 1, gap: 4 }}><Text style={styles.actionTitle}>Consentement obtenu</Text><Text style={styles.small}>Nécessaire avant tout enregistrement.</Text></View><Switch testID="resident-consent-switch" value={consent} onValueChange={setConsent} trackColor={{ false: colors.borderStrong, true: colors.success }} thumbColor={colors.onBrandPrimary} /></View>
            <Pressable testID="resident-create-button" accessibilityRole="button" onPress={() => void addResident()} style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}><Icon name="person-add-outline" color={colors.onBrandPrimary} /><Text style={styles.primaryText}>Créer le profil</Text></Pressable>
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

function HomeScreen({ styles, colors, insets, state, onAdd, onProfile, onFree, onArchive, notice }: any) {
  return <ScrollView testID="home-screen" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 22, paddingBottom: insets.bottom + 32 }]}>
    <View style={styles.header}><View><Text style={styles.eyebrow}>Carnet de l’atelier</Text><Text style={styles.brand}>Racontelle</Text></View><View style={styles.avatar}><Icon name="leaf-outline" color={colors.brandPrimary} /></View></View>
    <View style={styles.status}><Icon name="cloud-offline-outline" color={colors.onBrandTertiary} size={18} /><Text style={styles.statusText}>Mode local actif</Text></View>
    <View style={styles.hero}><Text style={styles.heroTitle}>Les voix que l’on aime racontent les plus belles histoires.</Text><Text style={styles.body}>Un espace simple pour écouter, préserver et transmettre les souvenirs de l’atelier.</Text></View>
    <View style={styles.actionRow}><Pressable testID="home-free-mode" accessibilityRole="button" onPress={onFree} style={({ pressed }) => [styles.actionCard, styles.actionPrimary, pressed && styles.pressed]}><Icon name="mic-outline" color={colors.onBrandPrimary} size={26} /><View><Text style={[styles.actionTitle, styles.actionTitleLight]}>Mode spontané</Text><Text style={[styles.actionText, styles.actionTextLight]}>Enregistrer sans choisir de personne</Text></View></Pressable><Pressable testID="home-archive" accessibilityRole="button" onPress={onArchive} style={({ pressed }) => [styles.actionCard, styles.actionSecondary, pressed && styles.pressed]}><Icon name="albums-outline" color={colors.onBrandTertiary} size={26} /><View><Text style={styles.actionTitle}>Mes souvenirs</Text><Text style={styles.actionText}>Retrouver le carnet audio</Text></View></Pressable></View>
    <View style={styles.sectionHeader}><Text style={styles.heading}>Vos personnes</Text><Pressable testID="home-add-profile" accessibilityRole="button" onPress={onAdd} style={styles.textButton}><Text style={styles.textButtonLabel}>Ajouter</Text></Pressable></View>
    {state.residents.length ? <View style={styles.profileGrid}>{state.residents.map((resident: Resident) => <Pressable testID={`home-profile-${resident.id}`} key={resident.id} accessibilityRole="button" onPress={() => onProfile(resident)} style={({ pressed }) => [styles.profileCard, pressed && styles.pressed]}><View style={styles.avatar}><Text style={styles.avatarText}>{initials(resident.display_name)}</Text></View><View><Text style={styles.profileName}>{resident.display_name}</Text><Text style={styles.consent}>Consentement obtenu</Text></View></Pressable>)}</View> : <View style={styles.empty}><Icon name="people-outline" color={colors.brand} size={32} /><Text style={styles.heading}>Le carnet commence ici</Text><Text style={[styles.body, { textAlign: "center" }]}>Créez un profil pour associer les prochains souvenirs à la bonne personne.</Text><Pressable testID="home-create-first" accessibilityRole="button" onPress={onAdd} style={styles.secondaryButton}><Text style={styles.secondaryText}>Créer le premier profil</Text></Pressable></View>}
    <Text style={styles.small}>{state.residents.length}/10 profils créés · stockage local sur cet appareil</Text>
  </ScrollView>;
}

function ProfileScreen({ styles, colors, insets, resident, capsules, onBack, onStart, onArchive }: any) {
  return <ScrollView contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
    <View style={styles.header}><Pressable testID="profile-back" accessibilityRole="button" onPress={onBack} style={styles.backButton}><Icon name="arrow-back" color={colors.onSurface} /></Pressable><Text style={styles.eyebrow}>Fiche personne</Text><View style={{ width: 48 }} /></View>
    <View style={styles.profileHeader}><View style={styles.largeAvatar}><Text style={styles.largeAvatarText}>{initials(resident.display_name)}</Text></View><Text style={styles.title}>{resident.display_name}</Text><Text style={styles.small}>Consentement obtenu · profil local</Text></View>
    <Pressable testID="profile-start-workshop" accessibilityRole="button" onPress={onStart} style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}><Icon name="mic" color={colors.onBrandPrimary} /><Text style={styles.primaryText}>Démarrer l’atelier</Text></Pressable>
    <View style={styles.sectionHeader}><Text style={styles.heading}>Souvenirs enregistrés</Text><Text style={styles.small}>{capsules.length}</Text></View>
    {capsules.length ? capsules.slice(0, 5).map((capsule: Capsule) => <CapsuleRow key={capsule.id} styles={styles} colors={colors} capsule={capsule} />) : <View style={styles.empty}><Icon name="heart-outline" color={colors.brand} size={28} /><Text style={styles.body}>Aucun souvenir pour le moment.</Text><Text style={styles.small}>Le premier récit apparaîtra ici.</Text></View>}
    {capsules.length > 5 && <Pressable testID="profile-open-archive" onPress={onArchive} style={styles.secondaryButton}><Text style={styles.secondaryText}>Voir toute l’archive</Text></Pressable>}
  </ScrollView>;
}

function WorkshopScreen({ styles, colors, insets, resident, mode, questionIndex, question, recorderStatus, durationSeconds, onBack, onRecord, onStop, onReset, onPlay, onSave, onSkip }: any) {
  const isQuestion = mode === "question";
  return <ScrollView contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
    <View style={styles.header}><Pressable testID="workshop-back" accessibilityRole="button" onPress={onBack} style={styles.backButton}><Icon name="arrow-back" color={colors.onSurface} /></Pressable><Text style={styles.eyebrow}>L’atelier vocal</Text><View style={{ width: 48 }} /></View>
    <View style={styles.workshopTop}><Text style={styles.title}>{resident ? resident.display_name : "Souvenir spontané"}</Text><Text style={styles.body}>{isQuestion ? "Une question à la fois, au rythme de la personne." : "Laissez la parole venir librement."}</Text>{isQuestion && <><View style={styles.progressTrack}><View style={[styles.progressFill, { width: `${((questionIndex + 1) / 3) * 100}%` }]} /></View><Text style={styles.small}>Question {questionIndex + 1} sur 3 · {question.theme}</Text></>}</View>
    {isQuestion && <View style={styles.questionCard}><Text style={styles.eyebrow}>Question du jour</Text><Text style={styles.questionText}>{question.text}</Text></View>}
    {!isQuestion && <View style={styles.hero}><Text style={styles.heroTitle}>Souvenir libre</Text><Text style={styles.body}>Appuyez sur le bouton quand la personne est prête, puis laissez-la raconter.</Text></View>}
    <View style={styles.recorderPanel}><Text style={styles.timer}>{formatDuration(durationSeconds)}</Text><Pressable testID="workshop-record" accessibilityRole="button" accessibilityLabel={recorderStatus === "recording" ? "Mettre en pause" : "Enregistrer"} onPress={onRecord} style={({ pressed }) => [styles.recordButton, recorderStatus === "recording" && styles.recordButtonActive, pressed && styles.pressed]}>{recorderStatus === "recording" ? <Icon name="pause" color={colors.onError} size={34} /> : <Icon name="mic" color={colors.onError} size={38} />}</Pressable><Text style={styles.small}>{recorderStatus === "recording" ? "Enregistrement en cours" : recorderStatus === "paused" ? "En pause" : recorderStatus === "done" ? "Prêt à réécouter" : "Appuyez pour commencer"}</Text></View>
    {recorderStatus === "recording" || recorderStatus === "paused" ? <View style={styles.actionRow}><Pressable testID="workshop-stop" accessibilityRole="button" onPress={onStop} style={[styles.primaryButton, { flex: 1 }]}><Icon name="stop" color={colors.onBrandPrimary} /><Text style={styles.primaryText}>Terminer</Text></Pressable><Pressable testID="workshop-pause" accessibilityRole="button" onPress={onRecord} style={[styles.secondaryButton, { flex: 1 }]}><Text style={styles.secondaryText}>{recorderStatus === "paused" ? "Reprendre" : "Pause"}</Text></Pressable></View> : recorderStatus === "done" ? <><View style={styles.actionRow}><Pressable testID="workshop-play" accessibilityRole="button" onPress={onPlay} style={[styles.secondaryButton, { flex: 1 }]}><Icon name="play" color={colors.brandPrimary} /><Text style={styles.secondaryText}>Réécouter</Text></Pressable><Pressable testID="workshop-reset" accessibilityRole="button" onPress={onReset} style={[styles.secondaryButton, { flex: 1 }]}><Text style={styles.secondaryText}>Recommencer</Text></Pressable></View><Pressable testID="workshop-save" accessibilityRole="button" onPress={onSave} style={styles.primaryButton}><Icon name="bookmark" color={colors.onBrandPrimary} /><Text style={styles.primaryText}>Sauvegarder le souvenir</Text></Pressable></> : null}
    {isQuestion && <Pressable testID="workshop-skip" accessibilityRole="button" onPress={onSkip} style={styles.textButton}><Text style={styles.textButtonLabel}>Passer cette question</Text></Pressable>}
  </ScrollView>;
}

function ArchiveScreen({ styles, colors, insets, residents, capsules, selectedId, onSelect, onBack, onPlay }: any) {
  return <ScrollView contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
    <View style={styles.header}><Pressable testID="archive-back" accessibilityRole="button" onPress={onBack} style={styles.backButton}><Icon name="arrow-back" color={colors.onSurface} /></Pressable><Text style={styles.eyebrow}>Archive locale</Text><View style={{ width: 48 }} /></View>
    <View><Text style={styles.title}>Mes souvenirs</Text><Text style={styles.body}>Les capsules restent disponibles sur cet appareil, même sans réseau.</Text></View>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.archiveFilter}><Pressable testID="archive-filter-all" onPress={() => onSelect(null)} style={[styles.filter, selectedId === null && styles.filterActive]}><Text style={[styles.filterText, selectedId === null && styles.filterTextActive]}>Tous</Text></Pressable>{residents.map((resident: Resident) => <Pressable testID={`archive-filter-${resident.id}`} key={resident.id} onPress={() => onSelect(resident.id)} style={[styles.filter, selectedId === resident.id && styles.filterActive]}><Text style={[styles.filterText, selectedId === resident.id && styles.filterTextActive]}>{resident.display_name}</Text></Pressable>)}</ScrollView>
    {capsules.length ? capsules.map((capsule: Capsule) => <CapsuleRow key={capsule.id} styles={styles} colors={colors} capsule={capsule} resident={residents.find((item: Resident) => item.id === capsule.resident_id)} onPlay={capsule.audio_uri ? () => onPlay(capsule.audio_uri) : undefined} />) : <View style={styles.empty}><Icon name="albums-outline" color={colors.brand} size={30} /><Text style={styles.heading}>Votre archive est vide</Text><Text style={[styles.body, { textAlign: "center" }]}>Les souvenirs sauvegardés pendant l’atelier apparaîtront ici.</Text></View>}
  </ScrollView>;
}

function CapsuleRow({ styles, colors, capsule, resident, onPlay }: { styles: any; colors: any; capsule: Capsule; resident?: Resident; onPlay?: () => void }) {
  return <View style={styles.capsule}><View style={styles.capsuleTop}><View style={{ flex: 1, gap: 5 }}><Text style={styles.capsuleTitle}>{capsule.title ?? "Souvenir vocal"}</Text><Text style={styles.capsuleDate}>{formatDate(capsule.recorded_at)} · {formatDuration(capsule.duration_sec)}</Text></View>{onPlay && <Pressable accessibilityRole="button" onPress={onPlay} style={styles.backButton}><Icon name="play" color={colors.brandPrimary} size={20} /></Pressable>}</View><View style={styles.capsuleMeta}><View style={styles.tag}><Text style={styles.tagText}>{capsule.mode === "question" ? capsule.theme : resident?.display_name ?? "À classer"}</Text></View><Text style={styles.small}>{capsule.synced ? "Copie serveur" : "Conservé sur l’appareil"}</Text></View></View>;
}