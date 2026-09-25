import { QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { LogBox } from "react-native";
import { KeyboardProvider } from "react-native-keyboard-controller";

import { ErrorBoundary } from "@/src/components/error-boundary";
import { queryClient } from "@/src/query-client";

// Disable logbox errors etc so that users can see the app
// and agent works as expected.
LogBox.ignoreAllLogs(true)

export default function RootLayout() {
  // Charte Racontelle Care : Allura (titres & accroches), Cormorant Garamond
  // (textes & corps), Montserrat (menus, boutons, petits titres).
  const [fontsLoaded] = useFonts({
    "Allura-Regular": require("../assets/fonts/Allura-Regular.ttf"),
    "CormorantGaramond-Regular": require("../assets/fonts/CormorantGaramond-Regular.ttf"),
    "CormorantGaramond-SemiBold": require("../assets/fonts/CormorantGaramond-SemiBold.ttf"),
    "Montserrat-Medium": require("../assets/fonts/Montserrat-Medium.ttf"),
    "Montserrat-Bold": require("../assets/fonts/Montserrat-Bold.ttf"),
  });

  if (!fontsLoaded) return null;

  // One app level ErrorBoundary; a render crash shows a reload screen
  // instead of a blank app.
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <KeyboardProvider>
          {/* Fond blanc Racontelle : icônes de la barre d'état en foncé pour rester lisibles. */}
          <StatusBar style="dark" />
          <Stack screenOptions={{ headerShown: false }} />
        </KeyboardProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
