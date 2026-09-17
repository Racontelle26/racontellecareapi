import { useEffect } from "react";
import { LogBox, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { KeyboardProvider } from "react-native-keyboard-controller";
import { BottomSheetModalProvider } from "@gorhom/bottom-sheet";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { useFonts } from "expo-font";
import * as SplashScreen from "expo-splash-screen";

import { ErrorBoundary } from "@/src/components/error-boundary";
import { ToastProvider } from "@/src/components/toast";
import { AuthProvider } from "@/src/auth/auth-context";
import { queryClient } from "@/src/query-client";
import { useTheme } from "@/src/theme";

LogBox.ignoreAllLogs(true);
SplashScreen.preventAutoHideAsync().catch(() => {});

export default function RootLayout() {
  const { colors } = useTheme();
  const [loaded, error] = useFonts({
    Cormorant: require("../assets/fonts/CormorantGaramond-Regular.ttf"),
    CormorantMedium: require("../assets/fonts/CormorantGaramond-Medium.ttf"),
    CormorantSemiBold: require("../assets/fonts/CormorantGaramond-SemiBold.ttf"),
    DMSans: require("../assets/fonts/DMSans-Regular.ttf"),
    DMSansMedium: require("../assets/fonts/DMSans-Medium.ttf"),
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
                    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.surface } }}>
                      <Stack.Screen name="record" options={{ presentation: "modal" }} />
                      <Stack.Screen name="feedback" options={{ presentation: "modal" }} />
                    </Stack>
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
