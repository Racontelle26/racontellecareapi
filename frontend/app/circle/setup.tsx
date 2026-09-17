import { useState } from "react";
import { View, Pressable, Image } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Tree, Users } from "phosphor-react-native";
import { Body, Button, Label, TextField, Title } from "@/src/components/ui";
import { api } from "@/src/api/client";
import { useAuth } from "@/src/auth/auth-context";
import { useToast } from "@/src/components/toast";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function CircleSetup() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const { refresh, signOut } = useAuth();
  const toast = useToast();
  const [mode, setMode] = useState<"create" | "join">("create");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    try {
      if (mode === "create") {
        if (!name.trim()) throw new Error("Donnez un nom à votre famille");
        await api.post("/circles", { name: name.trim() });
        toast.show("Cercle créé 🌱", "success");
      } else {
        if (!code.trim()) throw new Error("Entrez votre code d’invitation");
        await api.post("/invitations/accept", { code: code.trim() });
        toast.show("Bienvenue dans la famille !", "success");
      }
      await refresh();
      router.replace("/");
    } catch (e: any) {
      toast.show(e?.message || "Une erreur est survenue", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top + spacing.lg, paddingBottom: insets.bottom + spacing.lg }]}>
      <KeyboardAwareScrollView contentContainerStyle={styles.content} bottomOffset={20} showsVerticalScrollIndicator={false}>
        <Image source={require("../../assets/images/racontelle-logo.png")} style={styles.logo} resizeMode="contain" />
        <Title style={styles.title}>Votre cercle de famille</Title>
        <Body muted style={styles.sub}>
          Créez un espace privé pour votre famille, ou rejoignez celui d’un proche avec un code d’invitation.
        </Body>

        <View style={styles.toggle}>
          <Pressable
            testID="setup-mode-create"
            style={[styles.toggleBtn, mode === "create" && styles.toggleActive]}
            onPress={() => setMode("create")}
          >
            <Tree color={mode === "create" ? colors.onBrandPrimary : colors.onSurfaceTertiary} size={20} weight={mode === "create" ? "fill" : "regular"} />
            <Label style={[styles.toggleText, mode === "create" && styles.toggleTextActive]}>Créer</Label>
          </Pressable>
          <Pressable
            testID="setup-mode-join"
            style={[styles.toggleBtn, mode === "join" && styles.toggleActive]}
            onPress={() => setMode("join")}
          >
            <Users color={mode === "join" ? colors.onBrandPrimary : colors.onSurfaceTertiary} size={20} weight={mode === "join" ? "fill" : "regular"} />
            <Label style={[styles.toggleText, mode === "join" && styles.toggleTextActive]}>Rejoindre</Label>
          </Pressable>
        </View>

        {mode === "create" ? (
          <TextField
            label="NOM DE LA FAMILLE"
            testID="setup-circle-name"
            value={name}
            onChangeText={setName}
            placeholder="La famille Dupont"
          />
        ) : (
          <TextField
            label="CODE D’INVITATION"
            testID="setup-invite-code"
            value={code}
            onChangeText={setCode}
            placeholder="Ex : A1B2C3D4"
            autoCapitalize="characters"
          />
        )}

        <Button
          title={mode === "create" ? "Créer mon cercle" : "Rejoindre la famille"}
          testID="setup-submit"
          loading={loading}
          onPress={submit}
        />
        <Pressable onPress={signOut} hitSlop={8} testID="setup-logout">
          <Label style={styles.logout}>Se déconnecter</Label>
        </Pressable>
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface, paddingHorizontal: spacing.xl },
  content: { gap: spacing.lg, paddingBottom: spacing.xxl },
  logo: { width: 170, height: 58, alignSelf: "center" },
  title: { fontSize: 28, textAlign: "center" },
  sub: { textAlign: "center", marginBottom: spacing.sm },
  toggle: {
    flexDirection: "row",
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.pill,
    padding: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  toggleBtn: {
    flex: 1,
    flexDirection: "row",
    gap: spacing.sm,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
    borderRadius: radius.pill,
  },
  toggleActive: { backgroundColor: colors.brandPrimary },
  toggleText: { color: colors.onSurfaceTertiary },
  toggleTextActive: { color: colors.onBrandPrimary },
  logout: { textAlign: "center", color: colors.muted, marginTop: spacing.sm },
}));
