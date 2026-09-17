import { useState } from "react";
import { View, Pressable } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { CaretLeft } from "phosphor-react-native";
import { Body, Button, TextField, Title } from "@/src/components/ui";
import { api } from "@/src/api/client";
import { useToast } from "@/src/components/toast";
import { makeStyles, spacing, useTheme } from "@/src/theme";

export default function ForgotPassword() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const toast = useToast();
  const [step, setStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const requestCode = async () => {
    if (!email.trim()) return toast.show("Entrez votre e-mail", "error");
    setLoading(true);
    try {
      await api.post("/auth/request-reset", { email: email.trim() });
      toast.show("Si l’e-mail existe, un code vous a été envoyé", "info");
      setStep(2);
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    } finally {
      setLoading(false);
    }
  };

  const resetPassword = async () => {
    if (!code.trim() || password.length < 6) return toast.show("Code et nouveau mot de passe requis", "error");
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token: code.trim(), new_password: password });
      toast.show("Mot de passe mis à jour", "success");
      router.replace("/(auth)/login");
    } catch (e: any) {
      toast.show(e?.message || "Code invalide", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top + spacing.sm }]}>
      <Pressable style={styles.back} onPress={() => router.back()} hitSlop={12} testID="forgot-back">
        <CaretLeft color={colors.onSurface} size={24} />
      </Pressable>
      <KeyboardAwareScrollView contentContainerStyle={styles.content} bottomOffset={20} showsVerticalScrollIndicator={false}>
        <Title style={styles.title}>Mot de passe oublié</Title>
        {step === 1 ? (
          <>
            <Body muted style={styles.sub}>Nous vous enverrons un code de réinitialisation par e-mail.</Body>
            <View style={styles.form}>
              <TextField
                label="E-MAIL"
                testID="forgot-email"
                value={email}
                onChangeText={setEmail}
                placeholder="vous@exemple.fr"
                autoCapitalize="none"
                keyboardType="email-address"
              />
              <Button title="Envoyer le code" testID="forgot-request" loading={loading} onPress={requestCode} />
            </View>
          </>
        ) : (
          <>
            <Body muted style={styles.sub}>Saisissez le code reçu et votre nouveau mot de passe.</Body>
            <View style={styles.form}>
              <TextField
                label="CODE REÇU"
                testID="forgot-code"
                value={code}
                onChangeText={setCode}
                placeholder="Ex : A1B2C3D4"
                autoCapitalize="characters"
              />
              <TextField
                label="NOUVEAU MOT DE PASSE"
                testID="forgot-password"
                value={password}
                onChangeText={setPassword}
                placeholder="6 caractères minimum"
                secureTextEntry
              />
              <Button title="Réinitialiser" testID="forgot-submit" loading={loading} onPress={resetPassword} />
            </View>
          </>
        )}
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface, paddingHorizontal: spacing.xl },
  back: { width: 40, height: 40, justifyContent: "center" },
  content: { paddingTop: spacing.lg, paddingBottom: spacing.xxl, gap: spacing.md },
  title: { fontSize: 30 },
  sub: { marginBottom: spacing.md },
  form: { gap: spacing.lg },
}));
