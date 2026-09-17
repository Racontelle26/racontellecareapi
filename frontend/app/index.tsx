import { ActivityIndicator, View } from "react-native";
import { Redirect } from "expo-router";
import { useAuth } from "@/src/auth/auth-context";
import { useTheme } from "@/src/theme";

export default function Index() {
  const { loading, user, hasCircle } = useAuth();
  const { colors } = useTheme();

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface }}>
        <ActivityIndicator color={colors.brandPrimary} size="large" />
      </View>
    );
  }

  if (!user) return <Redirect href="/(auth)/welcome" />;
  if (!hasCircle) return <Redirect href="/circle/setup" />;
  return <Redirect href="/(tabs)" />;
}
