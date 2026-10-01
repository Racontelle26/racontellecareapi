import { View, Image, Pressable } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Body, Button, Display, Label, Script } from "@/src/components/ui";
import { GrowingTree } from "@/src/components/growing-tree";
import { makeStyles, spacing } from "@/src/theme";

export default function Welcome() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();

  return (
    <View style={[styles.container, { paddingTop: insets.top, paddingBottom: insets.bottom + spacing.lg }]}>
      <View style={styles.top}>
        <Image
          source={require("../../assets/images/racontelle-logo.png")}
          style={styles.logo}
          resizeMode="contain"
        />
        <View style={styles.tree}>
          <GrowingTree count={9} level={6} maxLevel={9} size={190} />
        </View>
        <Script style={styles.accroche}>Une question. Une voix. Un souvenir.</Script>
        <Display style={styles.headline}>Les voix que l’on aime racontent les plus belles histoires</Display>
        <Body muted style={styles.sub}>
          Réunissez votre famille dans un espace privé, répondez à voix haute à des questions de vie et gardez
          chaque souvenir dans votre album familial.
        </Body>
      </View>

      <View style={styles.actions}>
        <Button title="Créer mon espace famille" testID="welcome-create-btn" onPress={() => router.push("/(auth)/register")} />
        <Button
          title="J’ai déjà un compte"
          variant="ghost"
          testID="welcome-login-btn"
          onPress={() => router.push("/(auth)/login")}
        />
        <Pressable
          style={styles.inviteLink}
          testID="welcome-invite-link"
          onPress={() => router.push({ pathname: "/(auth)/register", params: { invite: "1" } })}
        >
          <Label style={styles.inviteText}>J’ai reçu un code d’invitation</Label>
        </Pressable>
      </View>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface, paddingHorizontal: spacing.xl, justifyContent: "space-between" },
  top: { alignItems: "center", flex: 1, justifyContent: "center", gap: spacing.md },
  logo: { width: 240, height: 70 },
  tree: { marginVertical: spacing.xs },
  accroche: { textAlign: "center", fontSize: 25, lineHeight: 34 },
  headline: { textAlign: "center", fontSize: 28, lineHeight: 34 },
  sub: { textAlign: "center", paddingHorizontal: spacing.sm },
  actions: { gap: spacing.md },
  inviteLink: { minHeight: 44, alignItems: "center", justifyContent: "center" },
  inviteText: { color: colors.brandPrimary, textDecorationLine: "underline" },
}));
