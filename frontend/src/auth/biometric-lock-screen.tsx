import { useState } from "react";
import { Pressable, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { FingerprintSimple, LockKey, UserCircle } from "phosphor-react-native";
import { Avatar, Body, Button, Label, Title } from "@/src/components/ui";
import { useAuth } from "@/src/auth/auth-context";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

export function BiometricLockScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const styles = useStyles();
  const { colors } = useTheme();
  const { user, member, biometricAvailable, unlockWithFingerprint, usePasswordInstead: choosePasswordLogin } = useAuth();
  const [unlocking, setUnlocking] = useState(false);
  const [message, setMessage] = useState("Votre code PIN sera proposé par le téléphone en cas d’échec.");

  const unlock = async (pinPrompt = false) => {
    setUnlocking(true);
    const result = await unlockWithFingerprint(pinPrompt);
    if (!result.success) {
      setMessage(result.expired ? "Votre session a expiré. Connectez-vous à nouveau." : result.cancelled ? "Déverrouillage annulé." : "Empreinte non reconnue. Réessayez ou utilisez votre code PIN.");
    }
    setUnlocking(false);
  };

  const passwordLogin = async () => {
    await choosePasswordLogin();
    router.replace("/(auth)/login");
  };

  return (
    <View style={[styles.overlay, { paddingTop: insets.top + spacing.xl, paddingBottom: insets.bottom + spacing.xl }]} testID="lock-screen-container">
      <View style={styles.topMark}><LockKey color={colors.brandSecondary} size={24} weight="duotone" /><Label style={styles.brand}>RACONTELLE FAMILY</Label></View>
      <View style={styles.center}>
        {user ? <Avatar name={user.display_name} color={member?.initials_color} size={76} /> : <View style={styles.fingerprintHalo}><FingerprintSimple testID="biometric-fingerprint-icon" color={colors.brandPrimary} size={54} weight="duotone" /></View>}
        <Title style={styles.title}>Déverrouiller Racontelle</Title>
        <Body muted style={styles.subtitle} testID="lock-screen-user-name">{user ? `Bienvenue, ${user.display_name}` : "Retrouvez les souvenirs de votre famille"}</Body>
        {!biometricAvailable ? <Body style={styles.warning} testID="biometric-status-message">L’empreinte n’est plus disponible sur ce téléphone. Utilisez votre mot de passe.</Body> : <Body muted style={styles.status} testID="biometric-status-message">{message}</Body>}
      </View>
      <View style={styles.actions}>
        <Button title="Déverrouiller avec mon empreinte" testID="biometric-unlock-button" loading={unlocking} disabled={!biometricAvailable} onPress={() => unlock(false)} icon={<FingerprintSimple color={colors.onBrandPrimary} size={22} weight="bold" />} />
        <Pressable testID="fallback-pin-button" disabled={!biometricAvailable || unlocking} onPress={() => unlock(true)} style={styles.pinButton}>
          <LockKey color={colors.brandPrimary} size={20} /><Label style={styles.pinText}>Utiliser le code / PIN du téléphone</Label>
        </Pressable>
        <Pressable testID="use-email-password-button" onPress={passwordLogin} style={styles.passwordButton}>
          <UserCircle color={colors.muted} size={20} /><Label style={styles.passwordText}>Se connecter avec e-mail et mot de passe</Label>
        </Pressable>
      </View>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  overlay: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, zIndex: 1000, elevation: 1000, backgroundColor: colors.surface, paddingHorizontal: spacing.xl, justifyContent: "space-between" },
  topMark: { alignItems: "center", gap: spacing.sm },
  brand: { color: colors.brandSecondary, letterSpacing: 1.4 },
  center: { alignItems: "center", gap: spacing.md },
  fingerprintHalo: { width: 112, height: 112, borderRadius: 56, alignItems: "center", justifyContent: "center", backgroundColor: colors.brandTertiary, borderWidth: 1, borderColor: colors.borderStrong },
  title: { fontSize: 31, textAlign: "center" },
  subtitle: { textAlign: "center" },
  status: { textAlign: "center", lineHeight: 21 },
  warning: { color: colors.error, textAlign: "center", lineHeight: 21 },
  actions: { gap: spacing.md },
  pinButton: { minHeight: 52, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, borderWidth: 1, borderColor: colors.brandPrimary, borderRadius: radius.pill },
  pinText: { color: colors.brandPrimary },
  passwordButton: { minHeight: 48, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm },
  passwordText: { color: colors.muted, textAlign: "center" },
}));