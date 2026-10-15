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
  content: { paddingHorizontal: 24, gap: 22, width: "100%", maxWidth: 560, alignSelf: "center" },
  logo: { width: 152, height: 152, alignSelf: "center" },
  intro: { alignItems: "center", gap: 8 },
  title: { color: colors.onSurface, fontSize: 30, lineHeight: 36, textAlign: "center", fontFamily: "CormorantGaramond-SemiBold" },
  body: { color: colors.onSurfaceSecondary, fontSize: 17, lineHeight: 24, textAlign: "center", fontFamily: "CormorantGaramond-Regular" },
  form: { gap: 15, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: 24, padding: 20 },
  label: { color: colors.onSurface, fontSize: 13, fontFamily: "Montserrat-Bold" },
  input: { minHeight: 54, borderRadius: 16, borderWidth: 1, borderColor: colors.borderStrong, backgroundColor: colors.surface, paddingHorizontal: 16, color: colors.onSurface, fontSize: 17, fontFamily: "Montserrat-Medium" },
  code: { letterSpacing: 4, textAlign: "center", fontSize: 22 },
  passwordField: { minHeight: 54, borderRadius: 16, borderWidth: 1, borderColor: colors.borderStrong, backgroundColor: colors.surface, flexDirection: "row", alignItems: "center" },
  passwordInput: { flex: 1, minHeight: 52, paddingHorizontal: 16, color: colors.onSurface, fontSize: 17, fontFamily: "Montserrat-Medium" },
  passwordToggle: { width: 52, minHeight: 52, alignItems: "center", justifyContent: "center" },
  button: { minHeight: 56, borderRadius: 18, backgroundColor: colors.brandPrimary, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10, paddingHorizontal: 16 },
  buttonText: { color: colors.onBrandPrimary, fontSize: 15, fontFamily: "Montserrat-Bold", textAlign: "center" },
  link: { minHeight: 48, alignItems: "center", justifyContent: "center", paddingHorizontal: 8 },
  linkText: { color: colors.brandPrimary, fontSize: 13, lineHeight: 19, fontFamily: "Montserrat-Bold", textAlign: "center" },
  error: { borderRadius: 14, backgroundColor: colors.accentRose, padding: 14, flexDirection: "row", gap: 10, alignItems: "center" },
  errorText: { flex: 1, color: colors.error, fontSize: 13, lineHeight: 18, fontFamily: "Montserrat-Medium" },
  info: { borderRadius: 14, backgroundColor: colors.brandTertiary, padding: 14, flexDirection: "row", gap: 10, alignItems: "center" },
  infoText: { flex: 1, color: colors.onBrandTertiary, fontSize: 13, lineHeight: 18, fontFamily: "Montserrat-Medium" },
  local: { borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 8 },
  small: { color: colors.muted, fontSize: 12, lineHeight: 18, textAlign: "center", fontFamily: "Montserrat-Medium" },
  pressed: { opacity: 0.78, transform: [{ scale: 0.985 }] },
}));

type Mode = "login" | "register" | "forgot" | "reset";

const TITLES: Record<Mode, [string, string]> = {
  login: ["Connexion professionnelle", "Retrouvez les ateliers de mémoire de votre établissement."],
  register: ["Créer l’espace de l’établissement", "Un compte administrateur et un espace sécurisé pour l’atelier."],
  forgot: ["Mot de passe oublié", "Indiquez votre adresse : vous recevrez un code valable 30 minutes."],
  reset: ["Nouveau mot de passe", "Saisissez le code reçu par email puis choisissez un nouveau mot de passe."],
};

export function AuthScreen({ onAuthenticated, onContinueLocal, initialMessage, initialEmail }: { onAuthenticated: (session: AuthSession) => void; onContinueLocal: () => void; initialMessage?: string | null; initialEmail?: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState(initialEmail ?? "");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState("");
  const [facility, setFacility] = useState("");
  const [error, setError] = useState<string | null>(initialMessage ?? null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const switchMode = (next: Mode) => {
    setMode(next);
    setError(null);
    setInfo(null);
    setPassword("");
    setConfirm("");
    if (next !== "reset") setCode("");
  };

  const run = async (task: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await task();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Connexion au serveur impossible. Vérifiez le réseau et réessayez.");
    } finally {
      setBusy(false);
    }
  };

  const submit = () => {
    const cleanEmail = email.trim();
    if (!cleanEmail) return setError("Indiquez votre adresse email professionnelle.");
    if (mode === "forgot") {
      return void run(async () => {
        const result = await authApi.forgotPassword(cleanEmail);
        switchMode("reset");
        setInfo(result.message);
      });
    }
    if (password.length < 12) return setError("Le mot de passe doit contenir au moins 12 caractères.");
    if (mode === "reset") {
      if (code.replace(/[^a-z0-9]/gi, "").length < 6) return setError("Saisissez le code reçu par email.");
      if (password !== confirm) return setError("Les deux mots de passe ne sont pas identiques.");
      return void run(async () => {
        const result = await authApi.resetPassword(cleanEmail, code.trim(), password);
        switchMode("login");
        setInfo(result.message);
      });
    }
    if (mode === "register" && (!name.trim() || !facility.trim())) return setError("Complétez tous les champs.");
    return void run(async () => {
      const session = mode === "register"
        ? await authApi.register({ email: cleanEmail, password, full_name: name.trim(), establishment_name: facility.trim() })
        : await authApi.login(cleanEmail, password);
      onAuthenticated(session);
    });
  };

  const passwordField = (value: string, onChange: (text: string) => void, testID: string, placeholder: string, autoComplete: "current-password" | "new-password") => <View style={styles.passwordField}>
    <TextInput testID={testID} value={value} onChangeText={onChange} placeholder={placeholder} placeholderTextColor={colors.muted} style={styles.passwordInput} secureTextEntry={!showPassword} autoCapitalize="none" autoComplete={autoComplete} onSubmitEditing={submit} />
    <Pressable testID={`${testID}-visibility`} accessibilityRole="button" accessibilityLabel={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"} onPress={() => setShowPassword((visible) => !visible)} style={({ pressed }) => [styles.passwordToggle, pressed && styles.pressed]}><Ionicons name={showPassword ? "eye-off-outline" : "eye-outline"} color={colors.brandPrimary} size={23} /></Pressable>
  </View>;

  const [title, subtitle] = TITLES[mode];
  const buttonLabel = { login: "Se connecter", register: "Créer l’établissement et mon compte", forgot: "Recevoir un code", reset: "Changer le mot de passe" }[mode];
  const buttonIcon = { login: "lock-open-outline", register: "business-outline", forgot: "mail-outline", reset: "key-outline" }[mode] as keyof typeof Ionicons.glyphMap;

  return <KeyboardAvoidingView testID="auth-screen" behavior={Platform.OS === "ios" ? "padding" : "height"} style={styles.root}>
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.content, { paddingTop: insets.top + 28, paddingBottom: insets.bottom + 28 }]}>
      <Image testID="auth-logo" source={require("../../assets/images/racontelle-logo.webp")} style={styles.logo} contentFit="contain" accessibilityLabel="Racontelle Care" />
      <View style={styles.intro}><Text testID="auth-title" style={styles.title}>{title}</Text><Text style={styles.body}>{subtitle}</Text></View>
      <View style={styles.form}>
        {mode === "register" && <>
          <Text style={styles.label}>Nom de l’établissement</Text>
          <TextInput testID="auth-register-facility-input" value={facility} onChangeText={setFacility} placeholder="EHPAD Les Glycines" placeholderTextColor={colors.muted} style={styles.input} autoCapitalize="words" />
          <Text style={styles.label}>Votre nom</Text>
          <TextInput testID="auth-register-name-input" value={name} onChangeText={setName} placeholder="Camille Martin" placeholderTextColor={colors.muted} style={styles.input} autoCapitalize="words" />
        </>}
        <Text style={styles.label}>Adresse email professionnelle</Text>
        <TextInput testID={`auth-${mode}-email-input`} value={email} onChangeText={setEmail} editable={mode !== "reset"} placeholder="soignant@ehpad.fr" placeholderTextColor={colors.muted} style={styles.input} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
        {mode === "reset" && <>
          <Text style={styles.label}>Code reçu par email</Text>
          <TextInput testID="auth-reset-code-input" value={code} onChangeText={(value) => setCode(value.toUpperCase())} placeholder="ABCD-EFGH" placeholderTextColor={colors.muted} style={[styles.input, styles.code]} autoCapitalize="characters" autoCorrect={false} maxLength={12} />
        </>}
        {mode !== "forgot" && <>
          <Text style={styles.label}>{mode === "reset" ? "Nouveau mot de passe" : "Mot de passe"}</Text>
          {passwordField(password, setPassword, `auth-${mode}-password-input`, "12 caractères minimum", mode === "login" ? "current-password" : "new-password")}
        </>}
        {mode === "reset" && <>
          <Text style={styles.label}>Confirmez le nouveau mot de passe</Text>
          {passwordField(confirm, setConfirm, "auth-reset-confirm-input", "Le même, une seconde fois", "new-password")}
        </>}
        {info && <View testID="auth-info-banner" style={styles.info}><Ionicons name="information-circle-outline" color={colors.onBrandTertiary} size={22} /><Text style={styles.infoText}>{info}</Text></View>}
        {error && <View testID="auth-login-error-banner" style={styles.error}><Ionicons name="alert-circle-outline" color={colors.error} size={22} /><Text style={styles.errorText}>{error}</Text></View>}
        <Pressable testID={`auth-${mode}-submit-button`} accessibilityRole="button" disabled={busy} onPress={submit} style={({ pressed }) => [styles.button, busy && { opacity: 0.6 }, pressed && styles.pressed]}>
          {busy ? <ActivityIndicator color={colors.onBrandPrimary} /> : <Ionicons name={buttonIcon} color={colors.onBrandPrimary} size={21} />}
          <Text style={styles.buttonText}>{buttonLabel}</Text>
        </Pressable>
        {mode === "login" && <Pressable testID="auth-forgot-password-button" accessibilityRole="button" onPress={() => switchMode("forgot")} style={({ pressed }) => [styles.link, pressed && styles.pressed]}><Text style={styles.linkText}>Mot de passe oublié ?</Text></Pressable>}
        {mode === "reset" && <Pressable testID="auth-resend-code-button" accessibilityRole="button" onPress={() => switchMode("forgot")} style={({ pressed }) => [styles.link, pressed && styles.pressed]}><Text style={styles.linkText}>Je n’ai pas reçu de code</Text></Pressable>}
      </View>
      {mode === "login"
        ? <Pressable testID="auth-login-switch-register-button" accessibilityRole="button" onPress={() => switchMode("register")} style={({ pressed }) => [styles.link, pressed && styles.pressed]}><Text style={styles.linkText}>Pas encore de compte ? Créer l’espace de l’établissement</Text></Pressable>
        : <Pressable testID="auth-back-to-login-button" accessibilityRole="button" onPress={() => switchMode("login")} style={({ pressed }) => [styles.link, pressed && styles.pressed]}><Text style={styles.linkText}>Retour à la connexion</Text></Pressable>}
      {mode === "forgot" && <Text style={styles.small}>Sans email reçu, un administrateur de l’établissement peut définir un mot de passe temporaire pour vous.</Text>}
      <View style={styles.local}><Text style={styles.small}>Sans compte, vous pouvez enregistrer sur cet appareil uniquement : ces souvenirs n’auront pas de copie sur le serveur. Une fois connecté, un réseau faible ne pose pas de problème : l’envoi se fait dès que possible.</Text><Pressable testID="auth-continue-local-button" accessibilityRole="button" onPress={onContinueLocal} style={styles.link}><Text style={styles.linkText}>Continuer uniquement sur cet appareil</Text></Pressable></View>
    </ScrollView>
  </KeyboardAvoidingView>;
}
