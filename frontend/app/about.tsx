import { Linking, Pressable, ScrollView, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { CaretLeft, EnvelopeSimple, Heart } from "phosphor-react-native";
import { Body, Label, Title } from "@/src/components/ui";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function AboutRacontelle() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();

  const contact = () => Linking.openURL("mailto:laracontelle@gmail.com");

  return (
    <View style={styles.container} testID="racontelle-about-page">
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Pressable testID="about-back" onPress={() => router.back()} style={styles.backButton}>
          <CaretLeft color={colors.onSurface} size={26} />
        </Pressable>
        <Label style={styles.headerLabel}>À PROPOS</Label>
        <View style={styles.backButton} />
      </View>
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + spacing.xxl }]} showsVerticalScrollIndicator={false}>
        <View style={styles.mark}>
          <Heart color={colors.brandPrimary} size={30} weight="duotone" />
        </View>
        <Title style={styles.title} testID="about-title">Racontelle</Title>
        <Body style={styles.text} testID="about-description">
          Racontelle est un projet d&apos;application simple pour enregistrer les souvenirs vocaux de ceux qu&apos;on aime : les premiers mots des enfants, leurs petites expressions, les anecdotes des parents, les récits des grands-parents.
        </Body>
        <Body style={styles.text}>
          L&apos;objectif : créer peu à peu une bibliothèque vocale familiale, intime et facile à enrichir.
        </Body>
        <Body style={styles.contactIntro}>N&apos;hésitez pas à m&apos;écrire :</Body>
        <Pressable testID="about-email-link" onPress={contact} style={styles.emailButton}>
          <EnvelopeSimple color={colors.brandPrimary} size={22} />
          <Body style={styles.email}>laracontelle@gmail.com</Body>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.lg, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  backButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  headerLabel: { color: colors.brandSecondary },
  content: { paddingHorizontal: spacing.xl, paddingTop: spacing.xxxl, gap: spacing.xl, alignItems: "center" },
  mark: { width: 64, height: 64, borderRadius: 32, alignItems: "center", justifyContent: "center", backgroundColor: colors.brandTertiary },
  title: { fontSize: 36, color: colors.brandPrimary },
  text: { fontSize: 18, lineHeight: 29, textAlign: "center" },
  contactIntro: { marginTop: spacing.sm, color: colors.muted },
  emailButton: { minHeight: 52, flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingHorizontal: spacing.lg, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  email: { color: colors.brandPrimary, fontSize: 16 },
}));