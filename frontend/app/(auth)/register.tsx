import { useState } from "react";
import { View, Pressable } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { CaretLeft, Check } from "phosphor-react-native";
import { Body, Button, PasswordField, TextField, Title } from "@/src/components/ui";
import { useAuth } from "@/src/auth/auth-context";
import { useToast } from "@/src/components/toast";
import { makeStyles, spacing, useTheme } from "@/src/theme";

export default function Register() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const { signUp } = useAuth();
  const toast = useToast();
  const [name, setName] = useState("");
  const [relationship, setRelationship] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const { invite } = useLocalSearchParams<{ invite?: string }>();

  const submit = async () => {
    if (!name.trim() || !email.trim() || password.length < 6) {
      toast.show("Complétez tous les champs (mot de passe : 6 caractères min.)", "error");
      return;
    }
    if (!accepted) {
      toast.show("Cochez la case d’acceptation des conditions de la bêta", "error");
      return;
    }
    setLoading(true);
    try {
      await signUp({
        display_name: name.trim(),
        relationship_label: relationship.trim() || undefined,
        email: email.trim(),
        password,
        accept_terms: true,
      });
      router.replace("/");
    } catch (e: any) {
      toast.show(e?.message || "Inscription impossible", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top + spacing.sm }]}>
      <Pressable style={styles.back} onPress={() => router.back()} hitSlop={12} testID="register-back">
        <CaretLeft color={colors.onSurface} size={24} />
      </Pressable>
      <KeyboardAwareScrollView contentContainerStyle={styles.content} bottomOffset={20} showsVerticalScrollIndicator={false}>
        <Title style={styles.title}>Créer votre compte</Title>
        <Body muted style={styles.sub}>
          {invite
            ? "Créez d’abord votre compte. À l’écran suivant, choisissez « Rejoindre » et saisissez le code reçu par e-mail."
            : "Vous serez le premier personnage de votre histoire de famille."}
        </Body>

        <View style={styles.form}>
          <TextField label="VOTRE PRÉNOM" testID="register-name" value={name} onChangeText={setName} placeholder="Marie" />
          <TextField
            label="LIEN DE FAMILLE (OPTIONNEL)"
            testID="register-relationship"
            value={relationship}
            onChangeText={setRelationship}
            placeholder="Grand-mère, papa, fille…"
          />
          <TextField
            label="E-MAIL"
            testID="register-email"
            value={email}
            onChangeText={setEmail}
            placeholder="vous@exemple.fr"
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
            textContentType="username"
            importantForAutofill="yes"
          />
          <PasswordField
            label="MOT DE PASSE"
            testID="register-password"
            value={password}
            onChangeText={setPassword}
            placeholder="6 caractères minimum"
            isNew
          />
          <Pressable
            style={styles.termsRow}
            onPress={() => setAccepted((v) => !v)}
            testID="register-accept-terms"
            accessibilityRole="checkbox"
            accessibilityState={{ checked: accepted }}
          >
            <View style={[styles.box, accepted && styles.boxOn]}>
              {accepted ? <Check color={colors.onBrandPrimary} size={16} weight="bold" /> : null}
            </View>
            <Body style={styles.terms}>
              J’accepte les conditions de la bêta Racontelle et je m’engage à n’enregistrer que des proches qui
              y consentent. Mes souvenirs restent privés, visibles par ma seule famille, et je peux demander leur
              suppression à tout moment.
            </Body>
          </Pressable>
          <Button title="Créer mon compte" testID="register-submit" loading={loading} onPress={submit} />
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
  termsRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md, minHeight: 44 },
  box: { width: 24, height: 24, borderRadius: 6, borderWidth: 2, borderColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", marginTop: 2 },
  boxOn: { backgroundColor: colors.brandPrimary },
  terms: { flex: 1, fontSize: 14, lineHeight: 20 },
}));
