import {
  AudioModule,
  RecordingPresets,
  requestNotificationPermissionsAsync,
  setAudioModeAsync,
  useAudioPlayer,
  useAudioPlayerStatus,
  useAudioRecorder,
  useAudioRecorderState,
} from "expo-audio";
import * as Clipboard from "expo-clipboard";
import * as FileSystem from "expo-file-system/legacy";
import * as ImagePicker from "expo-image-picker";
import * as Sharing from "expo-sharing";
import { useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, AppState, BackHandler, Platform, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, apiBaseUrl, ApiError, authApi } from "@/src/api";
import { AuthScreen } from "@/src/components/auth-screen";
import type { CapsuleActions } from "@/src/components/capsule-row";
import {
  AddMemberModal,
  ConfirmModal,
  EditCapsuleModal,
  FeedbackModal,
  MergeModal,
  PinModal,
  RemoveProfileModal,
  ResidentFormModal,
  type ResidentDraft,
} from "@/src/components/modals";
import { useCarnetStore } from "@/src/hooks/use-carnet-store";
import { isInactiveSince, readLastActivity, useInactivityLock } from "@/src/hooks/use-inactivity-lock";
import { useUsageTracking } from "@/src/hooks/use-usage-tracking";
import { isLocalId, setLocalScope } from "@/src/local";
import { availableQuestions, pickQuestion, THEME_ORDER, themeCards } from "@/src/question-bank";
import { HomeScreen } from "@/src/screens/home-screen";
import { LibraryScreen, type LibraryFilter } from "@/src/screens/library-screen";
import { ProScreen } from "@/src/screens/pro-screen";
import { ProfileScreen } from "@/src/screens/profile-screen";
import { QuestionBankScreen } from "@/src/screens/question-bank-screen";
import { QuizAdminScreen } from "@/src/screens/quiz-admin-screen";
import { QuizScreen } from "@/src/screens/quiz-screen";
import { WorkshopScreen, type RecorderStatus, type WorkshopMode, type WorkshopStep } from "@/src/screens/workshop-screen";
import { readProfessionalPin, writeProfessionalPin } from "@/src/secure-pin";
import { keepScreenOn, releaseScreen } from "@/src/screen-awake";
import { useTheme } from "@/src/theme";
import type { AuthSession, AuthUser, Capsule, FeatureFlags, FeedbackCategory, Question, Resident } from "@/src/types";
import { Icon } from "@/src/ui/primitives";
import { useStyles } from "@/src/ui/styles";

type Screen = "home" | "profile" | "workshop" | "library" | "pro" | "quiz" | "questions" | "quizAdmin";
type Confirm = { title: string; message: string; confirmLabel: string; action: () => void };

const KEEP_AWAKE_TAG = "racontelle-enregistrement";

/**
 * Web : quand le navigateur coupe le micro, il arrête lui-même l'enregistreur
 * et livre l'audio à ce moment-là ; `recorder.stop()` attendrait alors un audio
 * qui ne viendra plus. On garde donc chaque morceau livré pour pouvoir
 * reconstituer le fichier dans ce cas.
 */
function watchWebRecorder(recorder: unknown, onData: (blob: Blob) => void) {
  const media = (recorder as { mediaRecorder?: MediaRecorder | null }).mediaRecorder;
  media?.addEventListener("dataavailable", (event) => {
    if (event.data?.size) onData(event.data);
  });
}

/** Arrête l'enregistreur web et renvoie l'adresse de l'audio, même si le navigateur l'a déjà arrêté. */
async function finishWebRecording(recorder: { stop: () => Promise<void>; uri: string | null }, chunks: Blob[]): Promise<string | null> {
  const media = (recorder as unknown as { mediaRecorder?: MediaRecorder | null }).mediaRecorder;
  if (media && media.state !== "inactive") {
    await recorder.stop();
    return recorder.uri ?? null;
  }
  return chunks.length ? URL.createObjectURL(new Blob(chunks, { type: chunks[0].type })) : null;
}

/** Piste micro de l'enregistreur web (expo-audio n'expose pas le flux) : null sur mobile. */
function webAudioTrack(recorder: unknown): MediaStreamTrack | null {
  if (Platform.OS !== "web") return null;
  const stream = (recorder as { stream?: MediaStream | null }).stream;
  return stream?.getAudioTracks?.()[0] ?? null;
}
const INACTIVITY_MESSAGE = "Session fermée après 5 minutes d’inactivité. Reconnectez-vous : vos souvenirs restent conservés sur l’appareil.";
const PIN_MAX_ATTEMPTS = 5;
const PIN_LOCK_SECONDS = 60;

function spontaneousTitle(date: Date) {
  const label = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
  return `Souvenir spontané — ${label}`;
}

/** Une capsule peut perdre son fichier local sans risque seulement si le serveur en a la copie. */
function safelyStored(capsule: Capsule) {
  return capsule.synced && !isLocalId(capsule.id) && (!capsule.audio_uri || !!capsule.audio_stored);
}

export default function Index() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const resetParams = useLocalSearchParams<{ reset_email?: string | string[]; reset_code?: string | string[] }>();
  const resetEmail = Array.isArray(resetParams.reset_email) ? resetParams.reset_email[0] : resetParams.reset_email;
  const resetCode = Array.isArray(resetParams.reset_code) ? resetParams.reset_code[0] : resetParams.reset_code;
  const resetFromLink = !!resetEmail && !!resetCode;
  const base = { styles, colors, insets };

  const [notice, setNotice] = useState<string | null>(null);
  const store = useCarnetStore(setNotice);
  const { state, stateRef, update, patchCapsule, settings, questions } = store;
  const features = settings.features;

  const [screen, setScreen] = useState<Screen>("home");
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [guestMode, setGuestMode] = useState(false);
  const [authMessage, setAuthMessage] = useState<string | null>(null);
  const [rememberedEmail, setRememberedEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [professionalPin, setProfessionalPin] = useState<string | null>(null);
  const [selectedResidentId, setSelectedResidentId] = useState<string | null>(null);
  const [libraryFilter, setLibraryFilter] = useState<LibraryFilter>("all");
  const [busyCapsuleId, setBusyCapsuleId] = useState<string | null>(null);
  const [printing, setPrinting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const isAdmin = authUser?.role === "admin";
  const selectedResident = state.residents.find((resident) => resident.id === selectedResidentId) ?? null;

  // --- Chronométrage ---------------------------------------------------------
  const usageResidentId = screen === "profile" || screen === "workshop" ? selectedResidentId : null;
  const usage = useUsageTracking(stateRef, store.setState, usageResidentId, !loading && (!!authUser || guestMode));

  useEffect(() => {
    if (!notice) return;
    const timeout = setTimeout(() => setNotice(null), 7000);
    return () => clearTimeout(timeout);
  }, [notice]);

  // --- Session ---------------------------------------------------------------
  const onResidentSynced = useCallback((fromId: string, resident: Resident) => {
    setSelectedResidentId((current) => (current === fromId ? resident.id : current));
    setLibraryFilter((current) => (current === fromId ? resident.id : current));
  }, []);

  const openCarnet = useCallback(async (user: AuthUser | null) => {
    setLocalScope(user?.tenant_id ?? null);
    setProfessionalPin(await readProfessionalPin(user?.tenant_id ?? null));
    setLoading(true);
    // Le carnet local s'ouvre immédiatement, sans attendre le réseau ; le
    // serveur le complète ensuite.
    await store.loadLocal();
    usage.reset();
    setLoading(false);
    if (user) api.track("session_start");
    await store.syncWithServer(user, onResidentSynced);
  }, [onResidentSynced, store, usage]);

  useEffect(() => {
    let active = true;
    void authApi.rememberedUser().then(async (remembered) => {
      if (!active) return;
      let user = remembered;
      if (resetFromLink) {
        await authApi.logout();
        user = null;
      }
      // Application rouverte après plus de 5 minutes sans activité : la
      // session est fermée, il faut se reconnecter.
      if (user && isInactiveSince(await readLastActivity())) {
        await authApi.logout();
        setAuthMessage(INACTIVITY_MESSAGE);
        setRememberedEmail(user.email);
        user = null;
      }
      setAuthUser(user);
      if (user) setRememberedEmail(user.email);
      setAuthChecking(false);
      if (user) await openCarnet(user);
      else setLoading(false);
    });
    authApi.onSessionExpired(() => {
      setAuthMessage("Votre session a expiré par sécurité. Connectez-vous à nouveau : vos souvenirs restent sur l’appareil.");
      setAuthUser(null);
      setGuestMode(false);
    });
    return () => {
      active = false;
      authApi.onSessionExpired(null);
    };
    // Lecture unique au lancement.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Retour au premier plan : on renvoie ce qui attend (réseau revenu).
  const { syncPending } = store;
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (status) => {
      if (status === "active" && authUser) void syncPending(authUser, onResidentSynced);
    });
    return () => subscription.remove();
  }, [authUser, onResidentSynced, syncPending]);

  const activateSession = async (session: AuthSession) => {
    setAuthUser(session.user);
    setRememberedEmail(session.user.email);
    setGuestMode(false);
    setAuthMessage(null);
    setScreen("home");
    await openCarnet(session.user);
  };

  const continueLocally = async () => {
    setAuthUser(null);
    setGuestMode(true);
    setAuthMessage(null);
    setScreen("home");
    await openCarnet(null);
  };

  const logout = async () => {
    usage.stop();
    await authApi.logout();
    setAuthUser(null);
    setGuestMode(false);
    store.clear();
    setSelectedResidentId(null);
    setScreen("home");
    setLocalScope(null);
    setAuthMessage("Vous êtes déconnecté. Les enregistrements restent conservés sur l’appareil.");
  };

  // --- Lecture audio (souvenirs, réécoute, lecture vocale) ------------------
  const [playSource, setPlaySource] = useState<string | null>(null);
  const [playingKey, setPlayingKey] = useState<string | null>(null);
  const player = useAudioPlayer(playSource);
  const playerStatus = useAudioPlayerStatus(player);
  const wantPlay = useRef(false);

  useEffect(() => {
    if (wantPlay.current && playSource) {
      wantPlay.current = false;
      player.play();
    }
  }, [playSource, player]);

  const playUri = async (uri: string, key: string) => {
    // Sortie haut-parleur : après un enregistrement, la session iOS reste en
    // mode play-and-record et la réécoute partirait dans l'écouteur.
    await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false });
    setPlayingKey(key);
    if (playSource === uri) {
      player.seekTo(0);
      player.play();
      return;
    }
    wantPlay.current = true;
    setPlaySource(uri);
  };

  const playingCapsuleId = playerStatus.playing && playingKey?.startsWith("c-") ? playingKey.slice(2) : null;
  const speakingKey = playerStatus.playing && playingKey && !playingKey.startsWith("c-") ? playingKey : null;

  const togglePlay = async (capsule: Capsule) => {
    if (playingCapsuleId === capsule.id) {
      player.pause();
      return;
    }
    let uri = capsule.audio_uri ?? null;
    if (!uri && capsule.audio_stored && authUser) {
      setBusyCapsuleId(capsule.id);
      try {
        uri = await api.capsuleAudioUri(capsule.id);
      } catch {
        setNotice("Lecture impossible : la copie serveur n’est pas accessible pour le moment.");
      } finally {
        setBusyCapsuleId(null);
      }
    }
    if (uri) await playUri(uri, `c-${capsule.id}`);
  };

  const speakText = async (key: string, text: string) => {
    if (!authUser) {
      setNotice("Connectez-vous à l’établissement pour utiliser la lecture vocale.");
      return;
    }
    if (speakingKey === key) {
      player.pause();
      return;
    }
    try {
      const { path } = await api.tts(text);
      const uri = await api.fetchFileUri(path.replace(/^\/api/, ""), `tts-${key.replace(/[^a-z0-9-]/gi, "")}.mp3`);
      await playUri(uri, key);
    } catch (reason) {
      setNotice(reason instanceof ApiError && reason.status === 429 ? "Quota quotidien de lectures vocales atteint." : "La lecture vocale est indisponible pour le moment.");
    }
  };

  // --- Atelier : parcours guidé et mode spontané ----------------------------
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder) as { isRecording?: boolean };
  const [workshopStep, setWorkshopStep] = useState<WorkshopStep>("record");
  const [workshopMode, setWorkshopMode] = useState<WorkshopMode>("free");
  const [workshopTheme, setWorkshopTheme] = useState<string | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [recorderStatus, setRecorderStatus] = useState<RecorderStatus>("idle");
  const [recordedUri, setRecordedUri] = useState<string | null>(null);
  // Chronométrage basé sur l'horloge (pause/reprise incluses), sans limite de durée.
  const [elapsedSec, setElapsedSec] = useState(0);
  const elapsedBaseMs = useRef(0);
  const recordStartMs = useRef<number | null>(null);
  const finalDurationSec = useRef(0);

  const available = useMemo(() => availableQuestions(questions, features), [questions, features]);
  const themes = useMemo(() => themeCards(questions, features), [questions, features]);
  const answeredFor = (residentId: string | null) => state.answered?.[residentId ?? "none"] ?? [];

  useEffect(() => {
    if (recorderStatus !== "recording") return;
    const interval = setInterval(() => {
      const start = recordStartMs.current;
      setElapsedSec(Math.floor((elapsedBaseMs.current + (start ? Date.now() - start : 0)) / 1000));
    }, 250);
    return () => clearInterval(interval);
  }, [recorderStatus]);

  // Écran allumé pendant tout l'enregistrement : sans cela, la mise en veille
  // d'Android (30 s à 2 min) couperait un long récit (BT-09).
  // Écran allumé pendant tout l'enregistrement : indispensable sur le web, où
  // un écran verrouillé coupe le micro du navigateur.
  useEffect(() => {
    if (recorderStatus !== "recording" && recorderStatus !== "paused") return;
    void keepScreenOn(KEEP_AWAKE_TAG).then((ok) => {
      if (!ok && Platform.OS === "web" && recorderStatus === "recording") {
        setNotice("Ce navigateur ne peut pas garder l’écran allumé : désactivez la mise en veille automatique du téléphone pendant l’atelier, sinon le micro peut être coupé.");
      }
    });
    return () => releaseScreen(KEEP_AWAKE_TAG);
  }, [recorderStatus]);

  // Écran verrouillé ou application quittée : le récit CONTINUE d'être
  // enregistré jusqu'à ce que l'animatrice l'arrête. Sur l'application,
  // Android garde le micro grâce au service d'enregistrement en arrière-plan
  // (notification « enregistrement en cours », config `enableBackgroundRecording`).
  // Sur le web, cela dépend du navigateur : au retour sur la page, on vérifie
  // que le micro n'a pas été coupé et on le dit clairement si c'est le cas.
  const recorderStatusRef = useRef<RecorderStatus>("idle");
  const hiddenAtMs = useRef<number | null>(null);
  const backgroundRecording = useRef(false);
  const webMicMuted = useRef(false);
  const webChunks = useRef<Blob[]>([]);
  useEffect(() => {
    recorderStatusRef.current = recorderStatus;
  }, [recorderStatus]);
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (status) => {
      if (recorderStatusRef.current !== "recording") {
        hiddenAtMs.current = null;
        return;
      }
      if (status !== "active") {
        if (Platform.OS !== "web" && !backgroundRecording.current) {
          // Notifications refusées : Android suspend le micro, on le dit.
          elapsedBaseMs.current += Date.now() - (recordStartMs.current ?? Date.now());
          recordStartMs.current = null;
          try {
            recorder.pause();
          } catch {
            // L'enregistreur a déjà été suspendu par le système.
          }
          setRecorderStatus("paused");
          setNotice("Enregistrement mis en pause : l’écran s’est verrouillé. Touchez le bouton pour reprendre. Autorisez les notifications de Racontelle Care pour que l’enregistrement continue écran verrouillé.");
          return;
        }
        hiddenAtMs.current ??= Date.now();
        return;
      }
      const hiddenAt = hiddenAtMs.current;
      hiddenAtMs.current = null;
      if (Platform.OS !== "web" || hiddenAt === null) return;
      void keepScreenOn(KEEP_AWAKE_TAG);
      const track = webAudioTrack(recorder);
      if (!track || track.readyState === "ended") {
        // Micro rendu par le navigateur pendant le verrouillage (piste arrêtée
        // ou retirée du flux) : rien n'a été capté après. On garde le début,
        // avec sa vraie durée.
        elapsedBaseMs.current += hiddenAt - (recordStartMs.current ?? hiddenAt);
        recordStartMs.current = null;
        finalDurationSec.current = Math.max(1, Math.round(elapsedBaseMs.current / 1000));
        setElapsedSec(finalDurationSec.current);
        recorderStatusRef.current = "done";
        setRecorderStatus("done");
        void finishWebRecording(recorder, webChunks.current).then(
          (uri) => (uri ? setRecordedUri(uri) : api.track("recording_failed")),
          () => api.track("recording_failed"),
        );
        setNotice("Le navigateur a coupé le micro pendant que l’écran était verrouillé : l’enregistrement s’est arrêté à ce moment. Sauvegardez ce début, puis enregistrez la suite. Pour les longs récits, préférez l’application installée.");
        return;
      }
      if (webMicMuted.current || track?.muted) {
        webMicMuted.current = false;
        setNotice("Le navigateur a pu couper le micro pendant que l’écran était verrouillé : l’enregistrement continue, mais une partie du récit peut manquer. Vérifiez à la réécoute.");
      }
    });
    return () => subscription.remove();
  }, [recorder]);

  const resetRecording = () => {
    setRecordedUri(null);
    setElapsedSec(0);
    elapsedBaseMs.current = 0;
    recordStartMs.current = null;
    finalDurationSec.current = 0;
    setRecorderStatus("idle");
  };

  const openWorkshop = (resident: Resident | null, mode: WorkshopMode) => {
    if (resident && resident.consent_status !== "obtained") {
      setNotice("Le consentement doit être obtenu avant tout enregistrement.");
      return;
    }
    resetRecording();
    setSelectedResidentId(resident?.id ?? null);
    setWorkshopMode(mode);
    setWorkshopTheme(null);
    setQuestion(null);
    setWorkshopStep(mode === "question" ? (resident ? "theme" : "resident") : "record");
    setScreen("workshop");
  };

  const chooseQuestion = (theme: string | null, surprise: boolean) => {
    const next = pickQuestion(available, answeredFor(selectedResidentId), theme, question?.id ?? null);
    if (!next) {
      setNotice("Aucune question disponible pour ce thème.");
      return;
    }
    setQuestion(next);
    setWorkshopTheme(surprise ? next.theme : theme);
    setWorkshopMode("question");
    setWorkshopStep("record");
  };

  const leaveWorkshop = (to: Screen) => {
    if (recorderStatus !== "idle") {
      api.track("recording_abandoned", { question_id: question?.id });
      if (recorderState.isRecording || recorderStatus === "paused") void recorder.stop().catch(() => null);
    }
    resetRecording();
    setScreen(to);
  };

  const handleRecordPress = async () => {
    try {
      if (recorderStatus === "recording") {
        elapsedBaseMs.current += Date.now() - (recordStartMs.current ?? Date.now());
        recordStartMs.current = null;
        recorder.pause();
        setRecorderStatus("paused");
        return;
      }
      if (recorderStatus === "paused") {
        recordStartMs.current = Date.now();
        recorder.record();
        setRecorderStatus("recording");
        return;
      }
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        api.track("mic_denied");
        setNotice("Le micro n’est pas autorisé. Ouvrez les réglages du téléphone et autorisez le micro pour Racontelle Care.");
        return;
      }
      // Android 13+ exige l'autorisation des notifications pour enregistrer
      // écran verrouillé (notification « enregistrement en cours »).
      let background = Platform.OS === "ios";
      if (Platform.OS === "android") {
        const notifications = await requestNotificationPermissionsAsync().catch(() => null);
        background = !!notifications?.granted;
        if (!background) setNotice("Autorisez les notifications de Racontelle Care : sans elles, l’enregistrement se met en pause quand l’écran se verrouille.");
      }
      backgroundRecording.current = background;
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true, allowsBackgroundRecording: background });
      await recorder.prepareToRecordAsync();
      elapsedBaseMs.current = 0;
      finalDurationSec.current = 0;
      recordStartMs.current = Date.now();
      setElapsedSec(0);
      recorder.record();
      webMicMuted.current = false;
      webChunks.current = [];
      const track = webAudioTrack(recorder);
      if (track) track.onmute = () => { webMicMuted.current = true; };
      if (Platform.OS === "web") watchWebRecorder(recorder, (blob) => webChunks.current.push(blob));
      setRecorderStatus("recording");
    } catch {
      api.track("recording_failed");
      setNotice("L’enregistrement n’a pas pu démarrer. Vérifiez que le micro n’est pas utilisé par une autre application, puis réessayez.");
    }
  };

  const stopRecording = async () => {
    if (recordStartMs.current) {
      elapsedBaseMs.current += Date.now() - recordStartMs.current;
      recordStartMs.current = null;
    }
    finalDurationSec.current = Math.max(1, Math.round(elapsedBaseMs.current / 1000));
    setElapsedSec(finalDurationSec.current);
    try {
      if (Platform.OS === "web") setRecordedUri(await finishWebRecording(recorder, webChunks.current));
      else {
        await recorder.stop();
        setRecordedUri(recorder.uri ?? null);
      }
      setRecorderStatus("done");
    } catch {
      api.track("recording_failed");
      setNotice("L’enregistrement n’a pas pu être finalisé. Réessayez.");
      resetRecording();
    }
  };

  const saveRecording = async () => {
    const now = new Date();
    const resident = selectedResident;
    const guided = workshopMode === "question" && !!question && !!resident;
    const capsule: Capsule = {
      id: `local-${now.getTime()}`,
      resident_id: resident?.id ?? null,
      question_id: guided ? question!.id : null,
      mode: guided ? "question" : "free",
      theme: guided ? question!.theme : null,
      title: guided ? question!.text : resident ? `Récit libre — ${spontaneousTitle(now).replace("Souvenir spontané — ", "")}` : spontaneousTitle(now),
      duration_sec: finalDurationSec.current || elapsedSec,
      recorded_at: now.toISOString(),
      status: resident ? "assigned" : "unclassified",
      synced: false,
      audio_uri: recordedUri,
    };
    // Conservation précieuse : l'enregistrement quitte le cache (nettoyable
    // par le système) pour le stockage document permanent de l'appareil.
    if (recordedUri && Platform.OS !== "web") {
      try {
        const dir = `${FileSystem.documentDirectory}recordings/`;
        await FileSystem.makeDirectoryAsync(dir, { intermediates: true }).catch(() => {});
        const target = `${dir}${capsule.id}.m4a`;
        await FileSystem.copyAsync({ from: recordedUri, to: target });
        capsule.audio_uri = target;
      } catch {
        api.track("save_failed");
      }
    }
    await update((current) => ({
      ...current,
      capsules: [capsule, ...current.capsules],
      answered: guided
        ? { ...current.answered, [resident!.id]: [...new Set([...(current.answered?.[resident!.id] ?? []), question!.id])] }
        : current.answered,
    }));
    resetRecording();
    setWorkshopStep("saved");
    if (authUser) {
      void store.syncPending(authUser, onResidentSynced).then((ok) => {
        if (ok) void store.autoTranscribe();
        else setNotice("Réseau faible : la capsule est gardée sur l’appareil et sera envoyée automatiquement.");
      });
    }
  };

  const nextInWorkshop = () => {
    resetRecording();
    if (workshopMode === "question") chooseQuestion(workshopTheme, false);
    else setWorkshopStep("record");
  };

  // --- Profils -----------------------------------------------------------------
  const [residentForm, setResidentForm] = useState<{ open: boolean; residentId: string | null }>({ open: false, residentId: null });
  // Le sélecteur de photos du système ne demande aucune autorisation (Android
  // 13+ et iOS). La photo choisie arrive dans un cache que le système peut
  // vider : elle est recopiée dans le stockage permanent de l'appareil.
  const pickPhoto = async (): Promise<string | null> => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], allowsEditing: true, aspect: [1, 1], quality: 0.7 });
      const picked = result.canceled ? null : result.assets[0]?.uri ?? null;
      if (!picked || Platform.OS === "web") return picked;
      const dir = `${FileSystem.documentDirectory}photos/`;
      await FileSystem.makeDirectoryAsync(dir, { intermediates: true }).catch(() => {});
      const target = `${dir}portrait-${Date.now()}.jpg`;
      await FileSystem.copyAsync({ from: picked, to: target });
      return target;
    } catch {
      setNotice("La galerie photo n’est pas accessible pour le moment. Réessayez.");
      return null;
    }
  };

  const changeProfilePhoto = async () => {
    if (!selectedResident) return;
    const uri = await pickPhoto();
    if (!uri) return;
    await update((current) => ({ ...current, residents: current.residents.map((item) => (item.id === selectedResident.id ? { ...item, photo_uri: uri } : item)) }));
    setNotice("Photo enregistrée sur cet appareil.");
  };

  const submitResident = async (draft: ResidentDraft) => {
    const displayName = draft.display_name.trim();
    if (!displayName) {
      setNotice("Indiquez un prénom ou un pseudonyme.");
      return;
    }
    const editing = state.residents.find((resident) => resident.id === residentForm.residentId);
    if (!editing && state.residents.length >= settings.max_residents) {
      setNotice(`La bêta accepte ${settings.max_residents} profils au maximum.`);
      return;
    }
    const fields = { display_name: displayName, last_initial: draft.last_initial.trim() || null, unit: draft.unit.trim() || null, consent_status: draft.consent_status, photo_uri: draft.photo_uri };
    if (editing) {
      await update((current) => ({ ...current, residents: current.residents.map((item) => (item.id === editing.id ? { ...item, ...fields, pending_sync: !isLocalId(item.id) } : item)) }));
      setNotice(editing.consent_status !== draft.consent_status ? "Statut de consentement mis à jour et daté." : "Profil mis à jour.");
    } else {
      const resident: Resident = { id: `local-${Date.now()}`, ...fields, active: true, created_at: new Date().toISOString() };
      await update((current) => ({ ...current, residents: [...current.residents, resident] }));
      setNotice(authUser ? "Profil créé." : "Profil créé sur cet appareil uniquement.");
    }
    setResidentForm({ open: false, residentId: null });
    if (authUser) void store.syncPending(authUser, onResidentSynced);
  };

  // Doublons : profils portant le même prénom (insensible à la casse).
  const duplicateGroups = useMemo(() => {
    const groups = new Map<string, Resident[]>();
    state.residents.forEach((resident) => {
      const key = resident.display_name.trim().toLowerCase();
      groups.set(key, [...(groups.get(key) ?? []), resident]);
    });
    return Array.from(groups.values()).filter((group) => group.length > 1);
  }, [state.residents]);
  const [mergeGroup, setMergeGroup] = useState<Resident[]>([]);

  const confirmMerge = async (keepId: string) => {
    const keep = mergeGroup.find((resident) => resident.id === keepId);
    if (!keep || !isAdmin) return;
    const duplicateIds = mergeGroup.filter((resident) => resident.id !== keepId).map((resident) => resident.id);
    const photo = keep.photo_uri ?? mergeGroup.find((resident) => resident.photo_uri)?.photo_uri ?? null;
    const serverIds = duplicateIds.filter((id) => !isLocalId(id));
    await update((current) => ({
      ...current,
      residents: current.residents.filter((resident) => !duplicateIds.includes(resident.id)).map((resident) => (resident.id === keepId ? { ...resident, photo_uri: photo } : resident)),
      capsules: current.capsules.map((capsule) => (capsule.resident_id && duplicateIds.includes(capsule.resident_id) ? { ...capsule, resident_id: keepId } : capsule)),
      pending_merges: serverIds.length ? [...(current.pending_merges ?? []), { keep_id: keepId, merge_ids: serverIds }] : current.pending_merges,
    }));
    setMergeGroup([]);
    setNotice(`Profils fusionnés dans la fiche de ${keep.display_name}.`);
    if (authUser) void store.syncPending(authUser, onResidentSynced);
  };

  // --- Retrait, export et suppression RGPD --------------------------------------
  const [showRemove, setShowRemove] = useState(false);
  const removalUnsafe = selectedResident ? state.capsules.filter((capsule) => capsule.resident_id === selectedResident.id && !safelyStored(capsule)).length : 0;

  const shareFile = async (path: string, fileName: string, mimeType: string, dialogTitle: string) => {
    const uri = await api.fetchFileUri(path, fileName);
    if (Platform.OS === "web") (globalThis as any).window?.open?.(uri, "_blank");
    else if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(uri, { mimeType, dialogTitle });
  };

  const exportResident = async (resident: Resident) => {
    if (!isAdmin) return setNotice("L’export est réservé à l’administrateur de l’établissement.");
    if (isLocalId(resident.id)) return setNotice("Connectez l’appareil pour envoyer ce profil au serveur avant l’export.");
    setExporting(true);
    try {
      // Le fichier est vérifié (statut 200) avant d'être considéré comme exporté.
      await shareFile(api.exportResidentPath(resident.id), `racontelle-${resident.id}.zip`, "application/zip", `Souvenirs de ${resident.display_name}`);
      await update((current) => ({ ...current, exports: { ...current.exports, [resident.id]: new Date().toISOString() } }));
      setNotice("Export prêt : souvenirs et informations regroupés en un fichier.");
    } catch {
      setNotice("Export impossible pour le moment. Vérifiez la connexion et réessayez.");
    } finally {
      setExporting(false);
    }
  };

  const deleteLocalFiles = async (capsules: Capsule[]) => {
    if (Platform.OS === "web") return;
    for (const capsule of capsules) {
      if (capsule.audio_uri?.startsWith("file")) await FileSystem.deleteAsync(capsule.audio_uri, { idempotent: true }).catch(() => {});
    }
  };

  const removeResident = async (resident: Resident) => {
    if (!isAdmin) return setNotice("Le retrait d’un profil est réservé à l’administrateur.");
    if (!stateRef.current.exports?.[resident.id]) return setNotice("Extrayez d’abord les souvenirs avant de retirer le profil.");
    const own = stateRef.current.capsules.filter((capsule) => capsule.resident_id === resident.id);
    // Jamais d'effacement d'un audio qui n'a pas de copie sur le serveur.
    if (own.some((capsule) => !safelyStored(capsule))) return setNotice("Certains souvenirs ne sont pas encore sauvegardés sur le serveur. Attendez « Sauvegardé » avant de retirer le profil.");
    await deleteLocalFiles(own);
    await update((current) => ({
      ...current,
      residents: current.residents.filter((item) => item.id !== resident.id),
      capsules: current.capsules.filter((item) => item.resident_id !== resident.id),
      pending_removals: [...(current.pending_removals ?? []), resident.id],
    }));
    setShowRemove(false);
    setSelectedResidentId(null);
    setScreen("home");
    setNotice(`${resident.display_name} a été retiré(e) du carnet. Les souvenirs restent conservés sur le serveur.`);
    if (authUser) void store.syncPending(authUser, onResidentSynced);
  };

  const purgeResident = async (resident: Resident) => {
    if (!isAdmin && authUser) return setNotice("La suppression est réservée à l’administrateur.");
    if (!isLocalId(resident.id)) {
      try {
        await api.purgeResident(resident.id);
      } catch {
        setNotice("Suppression impossible hors connexion : rien n’a été effacé. Réessayez une fois connecté.");
        return;
      }
    }
    const own = stateRef.current.capsules.filter((capsule) => capsule.resident_id === resident.id);
    await deleteLocalFiles(own);
    await update((current) => ({
      ...current,
      residents: current.residents.filter((item) => item.id !== resident.id),
      capsules: current.capsules.filter((item) => item.resident_id !== resident.id),
    }));
    setShowRemove(false);
    setSelectedResidentId(null);
    setScreen("home");
    setNotice("Les données du profil ont été supprimées définitivement. L’opération est journalisée.");
  };

  const printCarnet = async (resident: Resident) => {
    if (isLocalId(resident.id)) return setNotice("Connectez l’appareil pour envoyer ce profil au serveur.");
    setPrinting(true);
    try {
      await shareFile(api.carnetResidentPath(resident.id), `racontelle-carnet-${resident.id}.pdf`, "application/pdf", `Carnet de ${resident.display_name}`);
    } catch {
      setNotice("Impression impossible pour le moment. Vérifiez la connexion et réessayez.");
    } finally {
      setPrinting(false);
    }
  };

  // --- Souvenirs : classement, suppression, partage, transcription -------------
  const [editingCapsule, setEditingCapsule] = useState<Capsule | null>(null);
  const [confirm, setConfirm] = useState<Confirm | null>(null);

  // Retour depuis l'atelier : jamais de perte silencieuse d'un enregistrement.
  const workshopBack = () => {
    if (workshopStep === "record" && workshopMode === "question" && recorderStatus === "idle") return setWorkshopStep("theme");
    const target: Screen = selectedResident ? "profile" : "home";
    if (recorderStatus === "idle") return leaveWorkshop(target);
    setConfirm({
      title: "Quitter sans sauvegarder ?",
      message: recorderStatus === "done"
        ? "Cet enregistrement n’a pas encore été sauvegardé. Si vous quittez maintenant, il sera perdu."
        : "Un enregistrement est en cours. Si vous quittez maintenant, il sera perdu.",
      confirmLabel: "Quitter sans sauvegarder",
      action: () => {
        setConfirm(null);
        leaveWorkshop(target);
      },
    });
  };

  // Bouton « retour » d'Android : revient à l'écran précédent au lieu de
  // fermer l'application (les fenêtres se ferment d'elles-mêmes).
  const hardwareBack = useRef<() => boolean>(() => false);
  useEffect(() => {
    hardwareBack.current = () => {
      if (screen === "home") return false;
      if (screen === "workshop") workshopBack();
      else if (screen === "questions" || screen === "quizAdmin") setScreen("pro");
      else setScreen("home");
      return true;
    };
  });
  useEffect(() => {
    const subscription = BackHandler.addEventListener("hardwareBackPress", () => hardwareBack.current());
    return () => subscription.remove();
  }, []);

  const saveCapsuleEdit = async (changes: { title: string; resident_id: string | null; theme: string | null }) => {
    const capsule = editingCapsule;
    if (!capsule) return;
    const title = changes.title || capsule.title;
    await patchCapsule(capsule.id, {
      title,
      resident_id: changes.resident_id,
      theme: capsule.mode === "question" ? capsule.theme : changes.theme,
      status: changes.resident_id ? "assigned" : "unclassified",
      classified_at: changes.resident_id && !capsule.resident_id ? new Date().toISOString() : capsule.classified_at,
      pending_update: capsule.synced && !isLocalId(capsule.id),
    });
    setEditingCapsule(null);
    setNotice(changes.resident_id && !capsule.resident_id ? "Souvenir classé : il rejoint la bibliothèque du résident avec sa date d’origine." : "Souvenir mis à jour.");
    if (authUser) void store.syncPending(authUser, onResidentSynced);
  };

  const deleteCapsule = async (capsule: Capsule) => {
    setConfirm(null);
    if (capsule.synced && !isLocalId(capsule.id)) {
      try {
        await api.deleteCapsule(capsule.id);
      } catch (reason) {
        setNotice(reason instanceof ApiError && reason.status === 403 ? "La suppression est réservée à l’administrateur." : "Suppression impossible hors connexion : rien n’a été effacé.");
        return;
      }
    }
    await deleteLocalFiles([capsule]);
    await update((current) => ({ ...current, capsules: current.capsules.filter((item) => item.id !== capsule.id) }));
    setNotice("Souvenir supprimé. L’audio n’est plus accessible.");
  };

  const transcribeCapsule = async (capsule: Capsule) => {
    if (!capsule.audio_uri || !capsule.synced) return setNotice("La transcription demande que le souvenir soit envoyé au serveur.");
    setBusyCapsuleId(capsule.id);
    try {
      const { transcription } = await api.transcribeCapsule(capsule.id, capsule.audio_uri);
      await patchCapsule(capsule.id, { transcription });
      setNotice("Transcription prête à relire.");
    } catch (reason) {
      setNotice(reason instanceof ApiError && reason.status === 429 ? "Quota quotidien de transcriptions atteint." : "Transcription momentanément indisponible.");
    } finally {
      setBusyCapsuleId(null);
    }
  };

  const shareCapsule = async (capsule: Capsule) => {
    if (!capsule.resident_id) return setNotice("Classez d’abord ce souvenir : un souvenir « À classer » ne peut pas être partagé.");
    if (!capsule.synced) return setNotice("Le partage demande que le souvenir soit envoyé au serveur.");
    setBusyCapsuleId(capsule.id);
    try {
      if (!capsule.audio_stored && capsule.audio_uri) {
        await api.uploadCapsuleAudio(capsule.id, capsule.audio_uri);
        await patchCapsule(capsule.id, { audio_stored: true });
      }
      const share = await api.shareCapsule(capsule.id);
      await Clipboard.setStringAsync(`${apiBaseUrl}${share.path}`);
      await patchCapsule(capsule.id, { share_id: share.share_id, share_expires_at: share.expires_at });
      setNotice("Lien copié : il reste valable 30 jours et peut être révoqué.");
    } catch (reason) {
      setNotice(reason instanceof ApiError ? reason.message : "Partage impossible pour le moment.");
    } finally {
      setBusyCapsuleId(null);
    }
  };

  const revokeShare = async (capsule: Capsule) => {
    if (!capsule.share_id) return;
    setBusyCapsuleId(capsule.id);
    try {
      await api.revokeShare(capsule.share_id);
      await patchCapsule(capsule.id, { share_id: null, share_expires_at: null });
      setNotice("Le lien familial est révoqué.");
    } catch {
      setNotice("Impossible de révoquer ce lien pour le moment.");
    } finally {
      setBusyCapsuleId(null);
    }
  };

  const capsuleActions = (capsule: Capsule): CapsuleActions => ({
    onPlay: capsule.audio_uri || capsule.audio_stored ? () => void togglePlay(capsule) : undefined,
    onEdit: () => setEditingCapsule(capsule),
    onListen: features.voice_reading && capsule.transcription ? () => void speakText(`t-${capsule.id}`, capsule.transcription!) : undefined,
    onTranscribe: features.transcription && authUser ? () => void transcribeCapsule(capsule) : undefined,
    onShare: features.family_share && authUser && capsule.resident_id ? () => void shareCapsule(capsule) : undefined,
    onRevokeShare: isAdmin && capsule.share_id ? () => void revokeShare(capsule) : undefined,
    onDelete: isAdmin || !authUser ? () => setConfirm({
      title: "Supprimer ce souvenir ?",
      message: "L’enregistrement sera effacé de cet appareil et du serveur. Cette action est définitive et sera journalisée.",
      confirmLabel: "Supprimer définitivement",
      action: () => void deleteCapsule(capsule),
    }) : undefined,
  });

  // --- Espace professionnel --------------------------------------------------------
  const [pinPrompt, setPinPrompt] = useState<{ mode: "create" | "unlock"; onSuccess: () => void } | null>(null);
  const [pinError, setPinError] = useState(false);
  const pinFailures = useRef(0);
  const [pinLockedUntil, setPinLockedUntil] = useState(0);
  const [pinLockSeconds, setPinLockSeconds] = useState(0);

  useEffect(() => {
    if (!pinLockedUntil) return;
    const tick = () => {
      const remaining = Math.max(0, Math.ceil((pinLockedUntil - Date.now()) / 1000));
      setPinLockSeconds(remaining);
      if (!remaining) setPinLockedUntil(0);
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [pinLockedUntil]);

  const requirePin = (onSuccess: () => void) => {
    setPinError(false);
    setPinPrompt({ mode: professionalPin ? "unlock" : "create", onSuccess });
  };

  const submitPin = async (value: string) => {
    if (!pinPrompt || pinLockSeconds) return;
    if (pinPrompt.mode === "create") {
      await writeProfessionalPin(authUser?.tenant_id ?? null, value);
      setProfessionalPin(value);
      setNotice("Code professionnel créé.");
    } else if (value !== professionalPin) {
      pinFailures.current += 1;
      setPinError(true);
      if (pinFailures.current >= PIN_MAX_ATTEMPTS) {
        pinFailures.current = 0;
        setPinLockedUntil(Date.now() + PIN_LOCK_SECONDS * 1000);
      }
      return;
    }
    pinFailures.current = 0;
    const action = pinPrompt.onSuccess;
    setPinPrompt(null);
    action();
  };

  const [showAddMember, setShowAddMember] = useState(false);
  const [memberBusy, setMemberBusy] = useState(false);
  const addTeamMember = async (body: { full_name: string; email: string; password: string }) => {
    if (!body.full_name || !body.email || body.password.length < 12) return setNotice("Complétez les champs avec un mot de passe d’au moins 12 caractères.");
    setMemberBusy(true);
    try {
      await api.createMember(body);
      setShowAddMember(false);
      setNotice("Le membre peut maintenant se connecter à cet établissement.");
    } catch (reason) {
      setNotice(reason instanceof ApiError && reason.status === 409 ? "Cette adresse email est déjà utilisée." : "Impossible d’ajouter ce membre pour le moment.");
    } finally {
      setMemberBusy(false);
    }
  };

  const updateFeatures = async (changes: Partial<FeatureFlags>) => {
    try {
      const next = await api.updateSettings(changes);
      await update((current) => ({ ...current, settings_cache: next }));
      if ("sensitive_themes" in changes) {
        const nextQuestions = await api.questions().catch(() => null);
        if (nextQuestions) await update((current) => ({ ...current, questions_cache: nextQuestions }));
      }
    } catch {
      setNotice("Réglage impossible hors connexion.");
    }
  };

  const reloadQuestions = useCallback(() => {
    void api.questions().then((next) => update((current) => ({ ...current, questions_cache: next }))).catch(() => null);
  }, [update]);

  // --- Retours des testeurs ------------------------------------------------------
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const sendFeedback = async (category: FeedbackCategory, message: string) => {
    if (!authUser) return setNotice("Connectez-vous pour envoyer un retour à l’équipe Racontelle.");
    setFeedbackBusy(true);
    try {
      await api.sendFeedback({ category, message: message || undefined, screen });
      setShowFeedback(false);
      setNotice("Merci ! Votre retour a bien été transmis.");
    } catch {
      setNotice("Envoi impossible pour le moment. Réessayez une fois la connexion revenue.");
    } finally {
      setFeedbackBusy(false);
    }
  };

  // --- Fermeture après 5 minutes d'inactivité ----------------------------------------
  // Pendant un enregistrement (même en pause ou avant sauvegarde) ou une écoute,
  // la session reste ouverte : un long récit se fait sans toucher l'écran.
  const markActivity = useInactivityLock({
    enabled: !!authUser && !loading,
    busy: recorderStatus !== "idle" || playerStatus.playing,
    onExpire: () => {
      void logout().then(() => setAuthMessage(INACTIVITY_MESSAGE));
    },
  });

  // --- Affichage -----------------------------------------------------------------
  if (authChecking) {
    return <View testID="auth-session-loading" style={[styles.root, styles.center]}><ActivityIndicator size="large" color={colors.brandPrimary} /><Text style={styles.body}>Ouverture de la session sécurisée…</Text></View>;
  }
  if (!authUser && !guestMode) {
    return <AuthScreen onAuthenticated={(session) => void activateSession(session)} onContinueLocal={() => void continueLocally()} initialMessage={authMessage} initialEmail={rememberedEmail} initialResetEmail={resetEmail} initialResetCode={resetCode} />;
  }
  if (loading) {
    return <View style={[styles.root, styles.center]}><ActivityIndicator size="large" color={colors.brandPrimary} /><Text style={styles.body}>Ouverture du carnet…</Text></View>;
  }

  const openLibrary = (filter: LibraryFilter) => {
    setLibraryFilter(filter);
    setScreen("library");
  };

  return <View style={styles.root} onTouchStart={markActivity}>
    {screen === "home" && <HomeScreen {...base}
      residents={state.residents}
      maxResidents={settings.max_residents}
      unclassifiedCount={state.capsules.filter((capsule) => !capsule.resident_id).length}
      pendingUploads={store.pendingUploads}
      authUser={authUser}
      quizEnabled={features.quiz && !!authUser}
      onAuthAction={() => (authUser ? void logout() : setGuestMode(false))}
      onAdd={() => setResidentForm({ open: true, residentId: null })}
      onProfile={(resident) => { setSelectedResidentId(resident.id); setScreen("profile"); }}
      onGuided={() => openWorkshop(null, "question")}
      onSpontaneous={() => openWorkshop(null, "free")}
      onQuiz={() => setScreen("quiz")}
      onToClassify={() => openLibrary("unclassified")}
      onLibrary={() => openLibrary("all")}
      onPro={() => requirePin(() => setScreen("pro"))}
      onFeedback={() => setShowFeedback(true)} />}

    {screen === "profile" && selectedResident && <ProfileScreen {...base}
      resident={selectedResident}
      capsules={state.capsules.filter((capsule) => capsule.resident_id === selectedResident.id)}
      isAdmin={isAdmin || guestMode}
      carnetEnabled={features.carnet_pdf}
      printing={printing}
      busyCapsuleId={busyCapsuleId}
      playingCapsuleId={playingCapsuleId}
      speakingCapsuleId={speakingKey}
      capsuleActions={capsuleActions}
      onBack={() => setScreen("home")}
      onGuided={() => openWorkshop(selectedResident, "question")}
      onFree={() => openWorkshop(selectedResident, "free")}
      onPhoto={() => void changeProfilePhoto()}
      onEditProfile={() => setResidentForm({ open: true, residentId: selectedResident.id })}
      onPrintCarnet={() => void printCarnet(selectedResident)}
      onRemoveRequest={() => requirePin(() => setShowRemove(true))} />}

    {screen === "workshop" && <WorkshopScreen {...base}
      step={workshopStep}
      mode={workshopMode}
      resident={selectedResident}
      residents={state.residents}
      themes={themes}
      theme={workshopTheme}
      question={question}
      recorderStatus={recorderStatus}
      durationSeconds={elapsedSec}
      voiceEnabled={features.voice_reading && !!authUser}
      speakingQuestion={!!question && speakingKey === `q-${question.id}`}
      onBack={workshopBack}
      onPickResident={(resident) => {
        if (resident.consent_status !== "obtained") return setNotice("Le consentement doit être obtenu avant tout enregistrement.");
        setSelectedResidentId(resident.id);
        setWorkshopStep("theme");
      }}
      onPickTheme={(theme) => { api.track("theme_selected", { theme }); chooseQuestion(theme, false); }}
      onSurprise={() => { api.track("question_surprise"); chooseQuestion(null, true); }}
      onAnotherQuestion={() => { api.track("question_change", { question_id: question?.id }); chooseQuestion(workshopTheme, false); }}
      onChangeTheme={() => setWorkshopStep("theme")}
      onListenQuestion={() => question && void speakText(`q-${question.id}`, question.text)}
      onModeChange={(mode) => {
        resetRecording();
        setWorkshopMode(mode);
        if (mode === "question" && !question) setWorkshopStep("theme");
        else setWorkshopStep("record");
      }}
      onRecord={() => void handleRecordPress()}
      onStop={() => void stopRecording()}
      onReset={resetRecording}
      onPlay={() => recordedUri && void playUri(recordedUri, "review")}
      onSave={() => void saveRecording()}
      onNext={nextInWorkshop}
      onFinish={() => leaveWorkshop(selectedResident ? "profile" : "home")} />}

    {screen === "library" && <LibraryScreen {...base}
      residents={state.residents}
      capsules={state.capsules}
      filter={libraryFilter}
      busyCapsuleId={busyCapsuleId}
      playingCapsuleId={playingCapsuleId}
      speakingCapsuleId={speakingKey}
      capsuleActions={capsuleActions}
      onFilter={setLibraryFilter}
      onBack={() => setScreen("home")} />}

    {screen === "pro" && <ProScreen {...base}
      residents={state.residents}
      capsules={state.capsules}
      usage={usage.displayedUsage}
      authUser={authUser}
      features={features}
      maxResidents={settings.max_residents}
      duplicateGroups={isAdmin ? duplicateGroups : []}
      onFeatures={updateFeatures}
      onAddMember={() => setShowAddMember(true)}
      onMergeGroup={setMergeGroup}
      onQuestionBank={() => setScreen("questions")}
      onQuizAdmin={() => setScreen("quizAdmin")}
      onFeedback={() => setShowFeedback(true)}
      onNotice={setNotice}
      onBack={() => setScreen("home")} />}

    {screen === "quiz" && <QuizScreen {...base} onNotice={setNotice} onBack={() => setScreen("home")} />}
    {screen === "questions" && <QuestionBankScreen {...base} onNotice={setNotice} onChanged={reloadQuestions} onBack={() => setScreen("pro")} />}
    {screen === "quizAdmin" && <QuizAdminScreen {...base} onNotice={setNotice} onBack={() => setScreen("pro")} />}

    {notice && <Pressable testID="notice" accessibilityRole="alert" onPress={() => setNotice(null)} style={[styles.notice, { bottom: insets.bottom + 16 }]}>
      <Icon name="information-circle-outline" color={colors.onInfo} size={20} /><Text style={styles.noticeText}>{notice}</Text><Icon name="close" color={colors.onInfo} size={18} />
    </Pressable>}

    <ResidentFormModal {...base}
      visible={residentForm.open}
      resident={state.residents.find((resident) => resident.id === residentForm.residentId) ?? null}
      onPickPhoto={pickPhoto}
      onClose={() => setResidentForm({ open: false, residentId: null })}
      onSubmit={(draft) => void submitResident(draft)} />
    <RemoveProfileModal {...base}
      visible={showRemove}
      resident={selectedResident}
      exportedAt={selectedResident ? state.exports?.[selectedResident.id] ?? null : null}
      exporting={exporting}
      unsafeCount={removalUnsafe}
      onExport={() => selectedResident && void exportResident(selectedResident)}
      onRemove={() => selectedResident && void removeResident(selectedResident)}
      onPurge={() => selectedResident && void purgeResident(selectedResident)}
      onClose={() => setShowRemove(false)} />
    <MergeModal {...base} visible={mergeGroup.length > 0} group={mergeGroup} capsules={state.capsules} onConfirm={(keepId) => void confirmMerge(keepId)} onClose={() => setMergeGroup([])} />
    <AddMemberModal {...base} visible={showAddMember && isAdmin} establishment={authUser?.establishment_name ?? ""} busy={memberBusy} onSubmit={(body) => void addTeamMember(body)} onClose={() => setShowAddMember(false)} />
    <EditCapsuleModal {...base} visible={!!editingCapsule} capsule={editingCapsule} residents={state.residents} themes={THEME_ORDER} onSubmit={(changes) => void saveCapsuleEdit(changes)} onClose={() => setEditingCapsule(null)} />
    <ConfirmModal {...base} visible={!!confirm} title={confirm?.title ?? ""} message={confirm?.message ?? ""} confirmLabel={confirm?.confirmLabel ?? "Confirmer"} onConfirm={() => confirm?.action()} onClose={() => setConfirm(null)} />
    <FeedbackModal {...base} visible={showFeedback} busy={feedbackBusy} onSubmit={(category, message) => void sendFeedback(category, message)} onClose={() => setShowFeedback(false)} />
    <PinModal {...base} visible={!!pinPrompt} mode={pinPrompt?.mode ?? "unlock"} error={pinError} lockedSeconds={pinLockSeconds} onSubmit={(pin) => void submitPin(pin)} onClose={() => setPinPrompt(null)} />
  </View>;
}
