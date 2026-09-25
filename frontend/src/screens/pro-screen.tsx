import * as Sharing from "expo-sharing";
import { useEffect, useState, type ReactNode } from "react";
import { ActivityIndicator, Platform, Pressable, ScrollView, Switch, Text, View } from "react-native";

import { api, type Indicators } from "../api";
import type { AuditEntry, AuthUser, Capsule, FeatureFlags, Resident, UsageState } from "../types";
import { Avatar, formatDateTime, formatTrackedTime, Icon, residentLabel, type IconName } from "../ui/primitives";
import type { ScreenProps } from "../ui/types";

type Props = ScreenProps & {
  residents: Resident[];
  capsules: Capsule[];
  usage: UsageState;
  authUser: AuthUser | null;
  features: FeatureFlags;
  maxResidents: number;
  duplicateGroups: Resident[][];
  onFeatures: (changes: Partial<FeatureFlags>) => Promise<void>;
  onAddMember: () => void;
  onMergeGroup: (group: Resident[]) => void;
  onQuestionBank: () => void;
  onQuizAdmin: () => void;
  onFeedback: () => void;
  onNotice: (message: string) => void;
  onBack: () => void;
};

const FEATURE_ROWS: { key: keyof FeatureFlags; label: string; help: string }[] = [
  { key: "quiz", label: "Quiz « Qui a dit ça ? »", help: "Animation de groupe, citations et musique." },
  { key: "sensitive_themes", label: "Thèmes sensibles", help: "Intimité et deuil : désactivés par défaut, à activer par un professionnel habilité." },
  { key: "voice_reading", label: "Lecture vocale des questions", help: "Une voix lit la question à voix haute." },
  { key: "family_share", label: "Partage famille", help: "Hors bêta : lien privé de 30 jours vers un souvenir classé." },
  { key: "transcription", label: "Transcription automatique", help: "Hors bêta : texte du souvenir généré automatiquement." },
  { key: "carnet_pdf", label: "Carnet PDF", help: "Hors bêta : impression des souvenirs d’un résident." },
];

const ACTION_LABELS: Record<string, string> = {
  "auth.admin_login": "Connexion administrateur",
  "auth.password_reset": "Mot de passe réinitialisé",
  "member.create": "Membre ajouté",
  "member.password_reset": "Mot de passe d’un membre redéfini",
  "resident.create": "Profil créé",
  "resident.consent_change": "Consentement modifié",
  "resident.archive": "Profil retiré",
  "resident.purge": "Profil supprimé (RGPD)",
  "resident.merge": "Profils fusionnés",
  "resident.export": "Souvenirs exportés",
  "resident.carnet": "Carnet PDF imprimé",
  "capsule.classify": "Souvenir classé",
  "capsule.reassign": "Souvenir réaffecté",
  "capsule.update": "Souvenir modifié",
  "capsule.delete": "Souvenir supprimé",
  "share.create": "Lien famille créé",
  "share.revoke": "Lien famille révoqué",
  "settings.update": "Réglages modifiés",
  "question.toggle": "Question activée/désactivée",
  "quiz.import": "Import du quiz",
  "quiz.update": "Élément du quiz modifié",
  "quiz.audio_upload": "Extrait musical ajouté",
  "indicators.export": "Indicateurs consultés",
};

/** « 0 capsule », « 1 capsule », « 3 capsules » (règle française : pluriel à partir de 2). */
function count(value: number | undefined, singular: string, pluralForm = `${singular}s`) {
  const n = value ?? 0;
  return `${n} ${n >= 2 ? pluralForm : singular}`;
}

function Section({ title, children, styles }: { title: string; children: ReactNode; styles: ScreenProps["styles"] }) {
  return <View style={{ gap: 12 }}><Text style={styles.heading}>{title}</Text>{children}</View>;
}

function LinkRow({ testID, icon, label, help, onPress, styles, colors }: { testID: string; icon: IconName; label: string; help: string; onPress: () => void } & Pick<ScreenProps, "styles" | "colors">) {
  return <Pressable testID={testID} accessibilityRole="button" onPress={onPress} style={({ pressed }) => [styles.statRow, pressed && styles.pressed]}>
    <View style={styles.avatar}><Icon name={icon} color={colors.onBrandTertiary} size={20} /></View>
    <View style={{ flex: 1, gap: 2 }}><Text style={styles.actionTitle}>{label}</Text><Text style={styles.small}>{help}</Text></View>
    <Icon name="chevron-forward" color={colors.muted} size={20} />
  </Pressable>;
}

export function ProScreen(props: Props) {
  const { styles, colors, insets, residents, capsules, usage, authUser, features } = props;
  const isAdmin = authUser?.role === "admin";
  const [indicators, setIndicators] = useState<Indicators | null>(null);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [feedbackCount, setFeedbackCount] = useState<number | null>(null);
  const [loadingAdmin, setLoadingAdmin] = useState(isAdmin);
  const [savingFlag, setSavingFlag] = useState<keyof FeatureFlags | null>(null);
  const { onNotice } = props;

  // Indicateurs, journal et retours : chargés à l'ouverture de l'espace professionnel.
  useEffect(() => {
    if (!isAdmin) return;
    let active = true;
    Promise.all([api.indicators(), api.audit(30), api.feedbackList()])
      .then(([nextIndicators, nextAudit, feedback]) => {
        if (!active) return;
        setIndicators(nextIndicators);
        setAuditLog(nextAudit);
        setFeedbackCount(feedback.length);
      })
      .catch(() => onNotice("Indicateurs indisponibles hors connexion."))
      .finally(() => active && setLoadingAdmin(false));
    return () => { active = false; };
  }, [isAdmin, onNotice]);

  const exportIndicators = async () => {
    try {
      const uri = await api.fetchFileUri(api.indicatorsCsvPath, "racontelle-indicateurs-beta.csv");
      if (Platform.OS === "web") (globalThis as any).window?.open?.(uri, "_blank");
      else if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(uri, { mimeType: "text/csv", dialogTitle: "Indicateurs de la bêta" });
    } catch {
      onNotice("Export impossible pour le moment. Vérifiez la connexion.");
    }
  };

  const toggle = async (key: keyof FeatureFlags, value: boolean) => {
    setSavingFlag(key);
    try {
      await props.onFeatures({ [key]: value });
    } finally {
      setSavingFlag(null);
    }
  };

  // Les souvenirs « À classer » ne comptent pas dans les statistiques d'un résident.
  const recordedTotal = capsules.reduce((sum, capsule) => sum + (capsule.duration_sec || 0), 0);
  const rows = residents
    .map((resident) => ({ resident, usageMs: usage.by_resident_ms[resident.id] ?? 0, capsules: capsules.filter((capsule) => capsule.resident_id === resident.id) }))
    .sort((a, b) => b.usageMs - a.usageMs);

  return <ScrollView testID="stats-screen" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
    <View style={styles.header}>
      <Pressable testID="stats-back" accessibilityRole="button" accessibilityLabel="Retour" onPress={props.onBack} style={styles.backButton}><Icon name="arrow-back" color={colors.onSurface} /></Pressable>
      <Text style={styles.eyebrow}>Espace professionnel</Text>
      <View style={{ width: 48 }} />
    </View>
    <View>
      <Text style={styles.title}>Suivi de l’atelier</Text>
      <Text testID="stats-establishment" style={styles.body}>{authUser ? `${authUser.establishment_name} · ${isAdmin ? "Administrateur" : "Membre"}` : "Mode local"}</Text>
    </View>

    <View testID="stats-global" style={styles.statHero}>
      <Text style={styles.statHeroLabel}>Temps total d’utilisation</Text>
      <Text testID="stats-global-time" style={styles.statHeroValue}>{formatTrackedTime(usage.total_ms)}</Text>
      <Text style={[styles.small, { color: colors.onBrandPrimary, opacity: 0.85 }]}>{capsules.length} souvenir{capsules.length > 1 ? "s" : ""} · {formatTrackedTime(recordedTotal * 1000)} d’audio · {capsules.filter((capsule) => !capsule.resident_id).length} à classer</Text>
    </View>

    <Section title={`Par résident (${residents.length}/${props.maxResidents})`} styles={styles}>
      {rows.length ? rows.map(({ resident, usageMs, capsules: own }) => <View testID={`stats-row-${resident.id}`} key={resident.id} style={styles.statRow}>
        <Avatar resident={resident} styles={styles} />
        <View style={{ flex: 1, gap: 2 }}><Text style={styles.actionTitle}>{residentLabel(resident)}</Text><Text style={styles.small}>{own.length} souvenir{own.length > 1 ? "s" : ""} · {formatTrackedTime(own.reduce((sum, capsule) => sum + (capsule.duration_sec || 0), 0) * 1000)} d’audio</Text></View>
        <View style={{ alignItems: "flex-end", gap: 2 }}><Text style={styles.small}>Temps passé</Text><Text testID={`stats-time-${resident.id}`} style={styles.statValue}>{formatTrackedTime(usageMs)}</Text></View>
      </View>) : <View style={styles.empty}><Text style={styles.body}>Créez un profil pour suivre le temps d’atelier par personne.</Text></View>}
    </Section>

    <LinkRow testID="stats-feedback" icon="chatbubble-ellipses-outline" label="Signaler une difficulté" help="Envoyer un retour à l’équipe Racontelle (avec la version de l’application)." onPress={props.onFeedback} styles={styles} colors={colors} />

    {isAdmin && <>
      <Section title="Équipe" styles={styles}>
        <Pressable testID="stats-add-member" accessibilityRole="button" onPress={props.onAddMember} style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}><Icon name="person-add-outline" color={colors.brandPrimary} /><Text style={styles.secondaryText}>Ajouter un membre à l’équipe</Text></Pressable>
      </Section>

      <Section title="Fonctions de la bêta" styles={styles}>
        <View style={styles.panel}>
          {FEATURE_ROWS.map((row) => <View key={row.key} style={styles.switchRow}>
            <View style={{ flex: 1, gap: 3 }}><Text style={styles.actionTitle}>{row.label}</Text><Text style={styles.small}>{row.help}</Text></View>
            {savingFlag === row.key ? <ActivityIndicator color={colors.brandPrimary} /> : <Switch testID={`feature-${row.key}`} value={features[row.key]} onValueChange={(value) => void toggle(row.key, value)} trackColor={{ false: colors.borderStrong, true: colors.brandPrimary }} thumbColor={colors.onBrandPrimary} />}
          </View>)}
        </View>
      </Section>

      <Section title="Contenus" styles={styles}>
        <LinkRow testID="stats-question-bank" icon="list-outline" label="Banque de questions" help="400 questions : activer ou désactiver par thème." onPress={props.onQuestionBank} styles={styles} colors={colors} />
        <LinkRow testID="stats-quiz-admin" icon="musical-notes-outline" label="Contenus du quiz" help="Importer un fichier CSV/JSON, activer ou désactiver les éléments." onPress={props.onQuizAdmin} styles={styles} colors={colors} />
      </Section>

      <Section title="Indicateurs de la bêta" styles={styles}>
        {loadingAdmin && !indicators ? <ActivityIndicator color={colors.brandPrimary} /> : indicators ? <View testID="stats-indicators" style={styles.panel}>
          <Text style={styles.body}>{count(indicators.usage?.sessions, "session")} · {count(indicators.usage?.capsules, "capsule")} · durée moyenne {Math.round(indicators.usage?.average_duration_sec ?? 0)} s</Text>
          <Text style={styles.body}>Parcours guidé : {count(indicators.guided?.capsules, "capsule")} · {count(indicators.guided?.question_changes, "changement")} de question · {count(indicators.guided?.abandoned_before_save, "abandon")}</Text>
          <Text style={styles.body}>Mode spontané : {count(indicators.spontaneous?.capsules, "capsule")} · {indicators.spontaneous?.still_to_classify ?? 0} à classer{indicators.spontaneous?.average_hours_before_classification != null ? ` · classées en ${indicators.spontaneous.average_hours_before_classification} h en moyenne` : ""}</Text>
          <Text style={styles.body}>Technique : {count(indicators.technical?.mic_denied, "refus micro", "refus micro")} · {count(indicators.technical?.upload_failed, "échec d’envoi", "échecs d’envoi")} · {count(indicators.technical?.audio_not_yet_on_server, "audio en attente", "audios en attente")}</Text>
          <Text style={styles.body}>Quiz : {count(indicators.quiz?.sessions, "session")} ({indicators.quiz?.quote_sessions ?? 0} citations, {indicators.quiz?.music_sessions ?? 0} musique)</Text>
          <Text style={styles.body}>Retours des testeurs : {feedbackCount ?? 0}</Text>
          <Pressable testID="stats-export-indicators" accessibilityRole="button" onPress={() => void exportIndicators()} style={styles.secondaryButton}><Icon name="download-outline" color={colors.brandPrimary} /><Text style={styles.secondaryText}>Exporter (CSV)</Text></Pressable>
        </View> : <Text style={styles.small}>Disponible une fois connecté au serveur.</Text>}
      </Section>

      <Section title="Journal des actions sensibles" styles={styles}>
        {auditLog.length ? <View testID="stats-audit" style={styles.panel}>
          {auditLog.slice(0, 15).map((entry) => <View key={entry.id} style={{ gap: 2 }}>
            <Text style={styles.actionTitle}>{ACTION_LABELS[entry.action] ?? entry.action}</Text>
            <Text style={styles.small}>{formatDateTime(entry.created_at)}{entry.user_name ? ` · ${entry.user_name}` : ""}</Text>
          </View>)}
        </View> : <Text style={styles.small}>{loadingAdmin ? "Chargement…" : "Aucune action enregistrée pour le moment."}</Text>}
      </Section>

      {props.duplicateGroups.length ? <Section title="Profils en double" styles={styles}>
        {props.duplicateGroups.map((group) => <Pressable testID={`merge-group-${group[0].display_name.trim().toLowerCase()}`} key={group[0].id} accessibilityRole="button" onPress={() => props.onMergeGroup(group)} style={({ pressed }) => [styles.statRow, pressed && styles.pressed]}>
          <View style={styles.avatar}><Icon name="copy-outline" color={colors.onBrandTertiary} size={20} /></View>
          <View style={{ flex: 1, gap: 2 }}><Text style={styles.actionTitle}>{group[0].display_name}</Text><Text style={styles.small}>{group.length} fiches portent ce prénom</Text></View>
          <Text style={styles.capsuleActionText}>Fusionner</Text>
        </Pressable>)}
      </Section> : null}
    </>}
    <Text style={styles.small}>Les durées restent conservées sur cet appareil, même hors connexion.</Text>
  </ScrollView>;
}
