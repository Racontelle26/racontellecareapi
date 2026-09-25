import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import type { CapsuleActions } from "../components/capsule-row";
import { CapsuleRow } from "../components/capsule-row";
import type { Capsule, Resident } from "../types";
import { Avatar, ConsentBadge, formatDate, formatDuration, Icon } from "../ui/primitives";
import type { ScreenProps } from "../ui/types";

type Props = ScreenProps & {
  resident: Resident;
  capsules: Capsule[];
  isAdmin: boolean;
  carnetEnabled: boolean;
  printing: boolean;
  busyCapsuleId: string | null;
  playingCapsuleId: string | null;
  speakingCapsuleId: string | null;
  capsuleActions: (capsule: Capsule) => CapsuleActions;
  onBack: () => void;
  onGuided: () => void;
  onFree: () => void;
  onPhoto: () => void;
  onEditProfile: () => void;
  onPrintCarnet: () => void;
  onRemoveRequest: () => void;
};

export function ProfileScreen(props: Props) {
  const { styles, colors, insets, resident, capsules, isAdmin } = props;
  const [newestFirst, setNewestFirst] = useState(true);
  const sorted = [...capsules].sort((a, b) => (newestFirst ? b.recorded_at.localeCompare(a.recorded_at) : a.recorded_at.localeCompare(b.recorded_at)));
  const guided = sorted.filter((capsule) => capsule.mode === "question");
  const free = sorted.filter((capsule) => capsule.mode === "free");
  const totalSeconds = capsules.reduce((sum, capsule) => sum + (capsule.duration_sec || 0), 0);
  const consented = resident.consent_status === "obtained";
  const renderCapsule = (capsule: Capsule) => <CapsuleRow key={capsule.id} styles={styles} colors={colors} capsule={capsule} busy={props.busyCapsuleId === capsule.id} playing={props.playingCapsuleId === capsule.id} speaking={props.speakingCapsuleId === `t-${capsule.id}`} actions={props.capsuleActions(capsule)} />;

  return <ScrollView testID="profile-screen" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
    <View style={styles.header}>
      <Pressable testID="profile-back" accessibilityRole="button" accessibilityLabel="Retour à l’accueil" onPress={props.onBack} style={styles.backButton}><Icon name="arrow-back" color={colors.onSurface} /></Pressable>
      <Text style={styles.eyebrow}>Fiche résident</Text>
      <Pressable testID="profile-edit" accessibilityRole="button" accessibilityLabel="Modifier le profil" onPress={props.onEditProfile} style={styles.backButton}><Icon name="create-outline" color={colors.brandPrimary} /></Pressable>
    </View>

    <View style={styles.profileHeader}>
      <Pressable testID="profile-photo-button" accessibilityRole="button" accessibilityLabel="Changer la photo" onPress={props.onPhoto} style={({ pressed }) => pressed && styles.pressed}><Avatar resident={resident} styles={styles} size={88} /></Pressable>
      <Text style={styles.title}>{resident.display_name}{resident.last_initial ? ` ${resident.last_initial}` : ""}</Text>
      {resident.unit ? <Text style={styles.small}>Unité : {resident.unit}</Text> : null}
      <Pressable testID="profile-consent" accessibilityRole="button" accessibilityLabel="Modifier le statut de consentement" onPress={props.onEditProfile}><ConsentBadge status={resident.consent_status} styles={styles} colors={colors} /></Pressable>
      <Text style={styles.small}>Profil créé le {formatDate(resident.created_at)} · {capsules.length} souvenir{capsules.length > 1 ? "s" : ""} · {formatDuration(totalSeconds)} d’écoute</Text>
    </View>

    {consented ? <View style={{ gap: 12 }}>
      <Pressable testID="profile-start-guided" accessibilityRole="button" onPress={props.onGuided} style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}><Icon name="chatbubbles-outline" color={colors.onBrandPrimary} /><Text style={styles.primaryText}>Souvenir guidé</Text></Pressable>
      <Pressable testID="profile-start-free" accessibilityRole="button" onPress={props.onFree} style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}><Icon name="mic-outline" color={colors.brandPrimary} /><Text style={styles.secondaryText}>Enregistrement libre</Text></Pressable>
    </View> : <View testID="profile-consent-required" style={styles.panel}>
      <Text style={styles.heading}>Consentement nécessaire</Text>
      <Text style={styles.body}>Aucun enregistrement n’est possible tant que le consentement n’est pas obtenu. Mettez à jour le statut une fois l’accord recueilli.</Text>
      <Pressable testID="profile-update-consent" accessibilityRole="button" onPress={props.onEditProfile} style={styles.secondaryButton}><Text style={styles.secondaryText}>Mettre à jour le consentement</Text></Pressable>
    </View>}

    <View style={styles.sectionHeader}>
      <Text style={styles.heading}>Bibliothèque</Text>
      <Pressable testID="profile-sort" accessibilityRole="button" onPress={() => setNewestFirst((value) => !value)} style={styles.textButton}>
        <Text style={styles.textButtonLabel}>{newestFirst ? "Plus récents d’abord" : "Plus anciens d’abord"}</Text>
      </Pressable>
    </View>

    <View testID="profile-guided-answers-section" style={{ gap: 14 }}>
      <View style={styles.sectionHeader}><Text style={styles.eyebrow}>Souvenirs guidés</Text><Text testID="profile-guided-answers-count" style={styles.small}>{guided.length}</Text></View>
      {guided.length ? guided.map(renderCapsule) : <View testID="profile-guided-answers-empty" style={styles.empty}><Icon name="chatbubble-ellipses-outline" color={colors.brandPrimary} size={28} /><Text style={styles.body}>Aucune réponse pour le moment.</Text></View>}
    </View>
    {free.length ? <View testID="profile-free-memories-section" style={{ gap: 14 }}>
      <View style={styles.sectionHeader}><Text style={styles.eyebrow}>Souvenirs libres et spontanés</Text><Text testID="profile-free-memories-count" style={styles.small}>{free.length}</Text></View>
      {free.map(renderCapsule)}
    </View> : null}

    {isAdmin && <View style={{ gap: 12 }}>
      <View style={{ height: 1, backgroundColor: colors.divider }} />
      {props.carnetEnabled && <Pressable testID="profile-print-carnet" accessibilityRole="button" disabled={props.printing} onPress={props.onPrintCarnet} style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}>{props.printing ? <ActivityIndicator color={colors.brandPrimary} /> : <Icon name="book-outline" color={colors.brandPrimary} />}<Text style={styles.secondaryText}>Imprimer le carnet (PDF)</Text></Pressable>}
      <Pressable testID="profile-remove" accessibilityRole="button" onPress={props.onRemoveRequest} style={({ pressed }) => [styles.textButton, { alignSelf: "center" }, pressed && styles.pressed]}><Text style={[styles.textButtonLabel, { color: colors.error }]}>Retirer ou supprimer le profil</Text></Pressable>
    </View>}
  </ScrollView>;
}
