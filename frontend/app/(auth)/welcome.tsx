import { View, Image } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Body, Button, Display } from "@/src/components/ui";
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
          <GrowingTree count={9} level={6} maxLevel={9} size={260} />
        </View>
        <Display style={styles.headline}>Chaque voix devient un souvenir précieux</Display>
        <Body muted style={styles.sub}>
          Réunissez votre famille autour de questions inspirantes, enregistrez vos souvenirs à voix haute et
          regardez votre arbre familial grandir.
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
      </View>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface, paddingHorizontal: spacing.xl, justifyContent: "space-between" },
  top: { alignItems: "center", flex: 1, justifyContent: "center", gap: spacing.md },
  logo: { width: 200, height: 70 },
  tree: { marginVertical: spacing.sm },
  headline: { textAlign: "center", fontSize: 30, lineHeight: 36 },
  sub: { textAlign: "center", paddingHorizontal: spacing.sm },
  actions: { gap: spacing.md },
}));
