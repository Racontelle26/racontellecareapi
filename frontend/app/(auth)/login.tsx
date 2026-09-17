import { useState } from "react";
import { View, Pressable } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { CaretLeft } from "phosphor-react-native";
import { Body, Button, Label, TextField, Title } from "@/src/components/ui";
import { useAuth } from "@/src/auth/auth-context";
import { useToast } from "@/src/components/toast";
import { makeStyles, spacing, useTheme } from "@/src/theme";

export default function Login() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const { signIn } = useAuth();
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!email.trim() || !password) {
      toast.show("Renseignez votre e-mail et mot de passe", "error");
      return;
    }
    setLoading(true);
    try {
      await signIn(email.trim(), password);
      router.replace("/");
    } catch (e: any) {
      toast.show(e?.message || "Connexion impossible", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top + spacing.sm }]}>
      <Pressable style={styles.back} onPress={() => router.back()} hitSlop={12} testID="login-back">
        <CaretLeft color={colors.onSurface} size={24} />
      </Pressable>
      <KeyboardAwareScrollView
        contentContainerStyle={styles.content}
        bottomOffset={20}
        showsVerticalScrollIndicator={false}
      >
        <Title style={styles.title}>Bon retour parmi nous</Title>
        <Body muted style={styles.sub}>Reprenez la collecte de vos souvenirs de famille.</Body>

        <View style={styles.form}>
          <TextField
            label="E-MAIL"
            testID="login-email"
            value={email}
            onChangeText={setEmail}
            placeholder="vous@exemple.fr"
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
          />
          <TextField
            label="MOT DE PASSE"
            testID="login-password"
            value={password}
            onChangeText={setPassword}
            placeholder="••••••••"
            secureTextEntry
          />
          <Pressable onPress={() => router.push("/(auth)/forgot-password")} testID="login-forgot" hitSlop={8}>
            <Label style={styles.forgot}>Mot de passe oublié ?</Label>
          </Pressable>
          <Button title="Se connecter" testID="login-submit" loading={loading} onPress={submit} />
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface, paddingHorizontal: spacing.xl },
  back: { width: 40, height: 40, justifyContent: "center" },
  content: { paddingTop: spacing.lg, paddingBottom: spacing.xxl, gap: spacing.sm },
  title: { fontSize: 30 },
  sub: { marginBottom: spacing.lg },
  form: { gap: spacing.lg },
  forgot: { color: colors.brandPrimary, textAlign: "right" },
}));
