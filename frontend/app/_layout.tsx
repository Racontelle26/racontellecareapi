import { useEffect } from "react";
import { ActivityIndicator, LogBox, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { KeyboardProvider } from "react-native-keyboard-controller";
import { BottomSheetModalProvider } from "@gorhom/bottom-sheet";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack, useRouter, useSegments } from "expo-router";
import { useFonts } from "expo-font";
// Per-weight imports: the package root would bundle all 18 Montserrat weights.
import { Montserrat_400Regular } from "@expo-google-fonts/montserrat/400Regular";
import { Montserrat_500Medium } from "@expo-google-fonts/montserrat/500Medium";
import { Montserrat_600SemiBold } from "@expo-google-fonts/montserrat/600SemiBold";
import { Allura_400Regular } from "@expo-google-fonts/allura/400Regular";
import * as SplashScreen from "expo-splash-screen";

import { ErrorBoundary } from "@/src/components/error-boundary";
import { ToastProvider } from "@/src/components/toast";
import { AuthProvider, useAuth } from "@/src/auth/auth-context";
import { queryClient } from "@/src/query-client";
import { useTheme } from "@/src/theme";

LogBox.ignoreAllLogs(true);
SplashScreen.preventAutoHideAsync().catch(() => {});

function RootNavigator() {
  const { colors } = useTheme();
  const { loading, user, hasCircle } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    const root = segments[0];
    const inAuth = root === "(auth)";
    const inSetup = root === "circle";
    if (!user) {
      if (!inAuth) router.replace("/(auth)/welcome");
    } else if (!hasCircle) {
      if (!inSetup) router.replace("/circle/setup");
    } else if (inAuth || inSetup) {
      router.replace("/(tabs)");
    }
  }, [loading, user, hasCircle, segments, router]);

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.brandPrimary} size="large" />
      </View>
    );
  }

  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.surface } }}>
      <Stack.Screen name="record" options={{ presentation: "modal" }} />
      <Stack.Screen name="feedback" options={{ presentation: "modal" }} />
    </Stack>
  );
}

export default function RootLayout() {
  const { colors } = useTheme();
  const [loaded, error] = useFonts({
    Cormorant: require("../assets/fonts/CormorantGaramond-Regular.ttf"),
    CormorantMedium: require("../assets/fonts/CormorantGaramond-Medium.ttf"),
    CormorantSemiBold: require("../assets/fonts/CormorantGaramond-SemiBold.ttf"),
    Montserrat: Montserrat_400Regular,
    MontserratMedium: Montserrat_500Medium,
    MontserratSemiBold: Montserrat_600SemiBold,
    Allura: Allura_400Regular,
  });

  const ready = loaded || !!error;

  useEffect(() => {
    if (ready) SplashScreen.hideAsync().catch(() => {});
  }, [ready]);

  if (!ready) return <View style={{ flex: 1, backgroundColor: colors.surface }} />;

  return (
    <ErrorBoundary>
      <GestureHandlerRootView style={{ flex: 1 }}>
        <SafeAreaProvider>
          <QueryClientProvider client={queryClient}>
            <KeyboardProvider>
              <AuthProvider>
                <BottomSheetModalProvider>
                  <ToastProvider>
                    <RootNavigator />
                  </ToastProvider>
                </BottomSheetModalProvider>
              </AuthProvider>
            </KeyboardProvider>
          </QueryClientProvider>
        </SafeAreaProvider>
      </GestureHandlerRootView>
    </ErrorBoundary>
  );
}
