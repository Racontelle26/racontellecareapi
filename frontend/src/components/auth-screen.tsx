import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError, authApi } from "../api";
import { makeStyles, useTheme } from "../theme";
import type { AuthSession } from "../types";

const useStyles = makeStyles((colors) => ({
  root: { flex: 1, backgroundColor: colors.surface },
  content: { paddingHorizontal: 24, gap: 22 },
  logo: { width: 210, height: 72, alignSelf: "center" },
  intro: { alignItems: "center", gap: 8 },
  title: { color: colors.onSurface, fontSize: 30, lineHeight: 36, textAlign: "center", fontFamily: "CormorantGaramond-SemiBold" },
  body: { color: colors.onSurfaceSecondary, fontSize: 17, lineHeight: 24, textAlign: "center", fontFamily: "CormorantGaramond-Regular" },
  form: { gap: 15, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: 24, padding: 20 },
  label: { color: colors.onSurface, fontSize: 13, fontFamily: "Montserrat-Bold" },
  input: { minHeight: 54, borderRadius: 16, borderWidth: 1, borderColor: colors.borderStrong, backgroundColor: colors.surface, paddingHorizontal: 16, color: colors.onSurface, fontSize: 17, fontFamily: "Montserrat-Medium" },
  passwordField: { minHeight: 54, borderRadius: 16, borderWidth: 1, borderColor: colors.borderStrong, backgroundColor: colors.surface, flexDirection: "row", alignItems: "center" },
  passwordInput: { flex: 1, minHeight: 52, paddingHorizontal: 16, color: colors.onSurface, fontSize: 17, fontFamily: "Montserrat-Medium" },
  passwordToggle: { width: 52, minHeight: 52, alignItems: "center", justifyContent: "center" },
  button: { minHeight: 54, borderRadius: 18, backgroundColor: colors.brandPrimary, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10, paddingHorizontal: 16 },
  buttonText: { color: colors.onBrandPrimary, fontSize: 15, fontFamily: "Montserrat-Bold", textAlign: "center" },
  link: { minHeight: 48, alignItems: "center", justifyContent: "center", paddingHorizontal: 8 },
  linkText: { color: colors.brandPrimary, fontSize: 13, lineHeight: 19, fontFamily: "Montserrat-Bold", textAlign: "center" },
  error: { borderRadius: 14, backgroundColor: colors.brandTertiary, padding: 14, flexDirection: "row", gap: 10, alignItems: "center" },
  errorText: { flex: 1, color: colors.error, fontSize: 13, lineHeight: 18, fontFamily: "Montserrat-Medium" },
  local: { borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 8 },
  small: { color: colors.muted, fontSize: 12, lineHeight: 18, textAlign: "center", fontFamily: "Montserrat-Medium" },
  pressed: { opacity: 0.78, transform: [{ scale: 0.985 }] },
}));

export function AuthScreen({ onAuthenticated, onContinueLocal, initialMessage, initialEmail }: { onAuthenticated: (session: AuthSession) => void; onContinueLocal: () => void; initialMessage?: string | null; initialEmail?: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [registering, setRegistering] = useState(false);
  const [email, setEmail] = useState(initialEmail ?? "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState("");
  const [facility, setFacility] = useState("");
  const [error, setError] = useState<string | null>(initialMessage ?? null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!email.trim() || password.length < 12 || (registering && (!name.trim() || !facility.trim()))) {
      setError("Complétez tous les champs. Le mot de passe doit contenir au moins 12 caractères.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const session = registering
        ? await authApi.register({ email: email.trim(), password, full_name: name.trim(), establishment_name: facility.trim() })
        : await authApi.login(email.trim(), password);
      onAuthenticated(session);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Connexion momentanément indisponible.");
    } finally {
      setBusy(false);
    }
  };

  return <KeyboardAvoidingView testID="auth-screen" behavior={Platform.OS === "ios" ? "padding" : "height"} style={styles.root}>
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.content, { paddingTop: insets.top + 28, paddingBottom: insets.bottom + 28 }]}>
      <Image testID="auth-logo" source={require("../../assets/images/racontelle-logo.webp")} style={styles.logo} contentFit="contain" />
      <View style={styles.intro}><Text testID="auth-title" style={styles.title}>{registering ? "Créer un compte et un établissement" : "Connexion professionnelle"}</Text><Text style={styles.body}>{registering ? "Créez l’espace sécurisé de votre établissement." : "Retrouvez les ateliers de mémoire de votre établissement."}</Text></View>
      <View style={styles.form}>
        {registering && <><Text style={styles.label}>Nom de l’établissement</Text><TextInput testID="auth-register-facility-input" value={facility} onChangeText={setFacility} placeholder="EHPAD Les Glycines" placeholderTextColor={colors.muted} style={styles.input} autoCapitalize="words" /><Text style={styles.label}>Votre nom</Text><TextInput testID="auth-register-name-input" value={name} onChangeText={setName} placeholder="Camille Martin" placeholderTextColor={colors.muted} style={styles.input} autoCapitalize="words" /></>}
        <Text style={styles.label}>Adresse email professionnelle</Text><TextInput testID={registering ? "auth-register-email-input" : "auth-login-email-input"} value={email} onChangeText={setEmail} placeholder="soignant@ehpad.fr" placeholderTextColor={colors.muted} style={styles.input} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
        <Text style={styles.label}>Mot de passe</Text><View style={styles.passwordField}><TextInput testID={registering ? "auth-register-password-input" : "auth-login-password-input"} value={password} onChangeText={setPassword} placeholder="12 caractères minimum" placeholderTextColor={colors.muted} style={styles.passwordInput} secureTextEntry={!showPassword} autoCapitalize="none" autoComplete={registering ? "new-password" : "current-password"} onSubmitEditing={() => void submit()} /><Pressable testID="auth-password-visibility-toggle" accessibilityRole="button" accessibilityLabel={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"} onPress={() => setShowPassword((visible) => !visible)} style={({ pressed }) => [styles.passwordToggle, pressed && styles.pressed]}><Ionicons name={showPassword ? "eye-off-outline" : "eye-outline"} color={colors.brandPrimary} size={23} /></Pressable></View>
        {error && <View testID="auth-login-error-banner" style={styles.error}><Ionicons name="alert-circle-outline" color={colors.error} size={22} /><Text style={styles.errorText}>{error}</Text></View>}
        <Pressable testID={registering ? "auth-register-submit-button" : "auth-login-submit-button"} accessibilityRole="button" disabled={busy} onPress={() => void submit()} style={({ pressed }) => [styles.button, busy && { opacity: 0.6 }, pressed && styles.pressed]}>{busy ? <ActivityIndicator color={colors.onBrandPrimary} /> : <Ionicons name={registering ? "business-outline" : "lock-open-outline"} color={colors.onBrandPrimary} size={21} />}<Text style={styles.buttonText}>{registering ? "Créer l’établissement et mon compte" : "Se connecter"}</Text></Pressable>
      </View>
      <Pressable testID={registering ? "auth-register-switch-login-button" : "auth-login-switch-register-button"} accessibilityRole="button" onPress={() => { setRegistering((value) => !value); setError(null); }} style={({ pressed }) => [styles.link, pressed && styles.pressed]}><Text style={styles.linkText}>{registering ? "Déjà inscrit ? Connexion professionnelle" : "Pas encore de compte ? Créer un établissement"}</Text></Pressable>
      <View style={styles.local}><Text style={styles.small}>Sans connexion, vous pouvez continuer à enregistrer localement. La synchronisation, l’IA et les exports resteront suspendus.</Text><Pressable testID="auth-continue-local-button" accessibilityRole="button" onPress={onContinueLocal} style={styles.link}><Text style={styles.linkText}>Continuer uniquement sur cet appareil</Text></Pressable></View>
    </ScrollView>
  </KeyboardAvoidingView>;
}