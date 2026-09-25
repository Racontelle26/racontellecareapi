import { Image } from "expo-image";
import { Pressable, ScrollView, Text, View } from "react-native";

import { EstablishmentBanner } from "../components/establishment-banner";
import type { AuthUser, Resident } from "../types";
import { Avatar, ConsentBadge, Icon, residentLabel, type IconName } from "../ui/primitives";
import type { ScreenProps } from "../ui/types";

type Props = ScreenProps & {
  residents: Resident[];
  maxResidents: number;
  unclassifiedCount: number;
  pendingUploads: number;
  authUser: AuthUser | null;
  quizEnabled: boolean;
  onAuthAction: () => void;
  onAdd: () => void;
  onProfile: (resident: Resident) => void;
  onGuided: () => void;
  onSpontaneous: () => void;
  onQuiz: () => void;
  onToClassify: () => void;
  onLibrary: () => void;
  onPro: () => void;
  onFeedback: () => void;
};

function ActionCard({ testID, icon, title, text, onPress, variant, badge, styles, colors }: { testID: string; icon: IconName; title: string; text: string; onPress: () => void; variant?: "primary" | "secondary"; badge?: number } & Pick<ScreenProps, "styles" | "colors">) {
  const light = variant === "primary";
  return <Pressable testID={testID} accessibilityRole="button" onPress={onPress} style={({ pressed }) => [styles.actionCard, variant === "primary" && styles.actionPrimary, variant === "secondary" && styles.actionSecondary, pressed && styles.pressed]}>
    <Icon name={icon} color={light ? colors.onBrandPrimary : colors.brandPrimary} size={28} />
    <View><Text style={[styles.actionTitle, light && styles.actionTitleLight]}>{title}</Text><Text style={[styles.actionText, light && styles.actionTextLight]}>{text}</Text></View>
    {badge ? <View style={styles.countBadge}><Text testID={`${testID}-count`} style={styles.countBadgeText}>{badge}</Text></View> : null}
  </Pressable>;
}

export function HomeScreen(props: Props) {
  const { styles, colors, insets, residents, maxResidents, unclassifiedCount, pendingUploads, authUser, quizEnabled } = props;
  return <ScrollView testID="home-screen" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 22, paddingBottom: insets.bottom + 32 }]}>
    <View style={styles.header}>
      <View><Text style={styles.eyebrow}>Carnet de l’atelier</Text><Image testID="home-logo" source={require("../../assets/images/racontelle-logo.webp")} style={styles.logo} contentFit="contain" accessibilityLabel="Racontelle Care" /></View>
      <Pressable testID="home-feedback" accessibilityRole="button" accessibilityLabel="Signaler une difficulté ou envoyer un retour" onPress={props.onFeedback} style={({ pressed }) => [styles.statsCard, { paddingVertical: 10, paddingHorizontal: 12 }, pressed && styles.pressed]}>
        <Icon name="chatbubble-ellipses-outline" color={colors.onBrandTertiary} size={20} /><Text style={styles.statusText}>Retour</Text>
      </Pressable>
    </View>
    <View style={styles.status}>
      <Icon name={authUser ? "shield-checkmark-outline" : "cloud-offline-outline"} color={colors.onBrandTertiary} size={18} />
      <Text testID="home-sync-status" style={styles.statusText}>{authUser ? pendingUploads ? `${pendingUploads} souvenir${pendingUploads > 1 ? "s" : ""} en attente d’envoi` : "Tout est sauvegardé" : "Mode local actif"}</Text>
    </View>
    <EstablishmentBanner user={authUser} onAuthAction={props.onAuthAction} />

    <View style={styles.sectionHeader}>
      <Text style={styles.heading}>Les résidents</Text>
      <Pressable testID="home-add-profile" accessibilityRole="button" onPress={props.onAdd} style={styles.textButton}><Text style={styles.textButtonLabel}>Ajouter</Text></Pressable>
    </View>
    {residents.length ? <View style={styles.profileGrid}>
      {residents.map((resident) => <Pressable testID={`home-profile-${resident.id}`} key={resident.id} accessibilityRole="button" accessibilityLabel={`Ouvrir la fiche de ${residentLabel(resident)}`} onPress={() => props.onProfile(resident)} style={({ pressed }) => [styles.profileCard, pressed && styles.pressed]}>
        <Avatar resident={resident} styles={styles} size={52} />
        <View>
          <Text style={styles.profileName}>{residentLabel(resident)}</Text>
          {resident.unit ? <Text style={styles.small}>{resident.unit}</Text> : null}
          <ConsentBadge status={resident.consent_status} styles={styles} colors={colors} />
        </View>
      </Pressable>)}
    </View> : <View style={styles.empty}>
      <Icon name="people-outline" color={colors.brandPrimary} size={32} />
      <Text style={styles.heading}>Le carnet commence ici</Text>
      <Text style={[styles.body, { textAlign: "center" }]}>Créez jusqu’à {maxResidents} profils pour associer les souvenirs à la bonne personne.</Text>
      <Pressable testID="home-create-first" accessibilityRole="button" onPress={props.onAdd} style={styles.secondaryButton}><Text style={styles.secondaryText}>Créer le premier profil</Text></Pressable>
    </View>}
    <Text style={styles.small}>{residents.length}/{maxResidents} profils · les données restent aussi sur cet appareil</Text>

    <View style={styles.actionGrid}>
      <ActionCard testID="home-guided" icon="chatbubbles-outline" title="Souvenir guidé" text="Résident, thème, question" onPress={props.onGuided} variant="primary" styles={styles} colors={colors} />
      <ActionCard testID="home-free-mode" icon="mic-outline" title="Mode spontané" text="Enregistrer maintenant, classer plus tard" onPress={props.onSpontaneous} variant="secondary" styles={styles} colors={colors} />
      {quizEnabled && <ActionCard testID="home-quiz" icon="musical-notes-outline" title="Qui a dit ça ?" text="Citations et chansons en groupe" onPress={props.onQuiz} styles={styles} colors={colors} />}
      <ActionCard testID="home-to-classify" icon="file-tray-full-outline" title="À classer" text="Souvenirs spontanés à attribuer" onPress={props.onToClassify} badge={unclassifiedCount} styles={styles} colors={colors} />
      <ActionCard testID="home-archive" icon="albums-outline" title="Tous les souvenirs" text="Bibliothèque de l’atelier" onPress={props.onLibrary} styles={styles} colors={colors} />
      <ActionCard testID="home-stats" icon="briefcase-outline" title="Espace professionnel" text="Suivi, équipe, réglages" onPress={props.onPro} styles={styles} colors={colors} />
    </View>
  </ScrollView>;
}
