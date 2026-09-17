// Design tokens for this app. Light theme only.Always modify the colors and theme to Dark, Light or Dark and Light according to the design guidelines.
//
// The keys match the "color" block of /app/design_guidelines.json. Fill the
// values from that file (or from the user's brand colors). Keep every key; do
// not add a second theme or colors file; do not write color literals in
// components.
//
// How the names work: a plain key is a background, and its `on` partner is the
// text or icon color that sits on top of it. Always use them as a pair.
//   <View style={{ backgroundColor: colors.brandPrimary }}>
//     <Text style={{ color: colors.onBrandPrimary }}>Continue</Text>
//   </View>
//
// Styling a screen or component: build the sheet with makeStyles so colors
// and layout live together and follow the active scheme:
//   const useStyles = makeStyles((colors) => ({
//     card: { backgroundColor: colors.surfaceSecondary, padding: 16 },
//     title: { color: colors.onSurfaceSecondary, fontSize: 16 },
//   }));
//   function Screen() {
//     const styles = useStyles();
//     return <View style={styles.card}><Text style={styles.title}>Hi</Text></View>;
//   }
// For color props that are not styles (icon color, placeholderTextColor,
// ActivityIndicator) read useTheme().colors inside the component.
// Never call StyleSheet.create with color values at module level; it cannot
// follow the scheme.
//
// To support dark mode later: add `dark` to `themes` with every key filled.
// Nothing else changes; the device setting takes over automatically.
// Feel free to add as many new colors as you need to support the design guidelines.

import { useMemo } from "react";
import { Appearance, StyleSheet, useColorScheme } from "react-native";

export type ColorScheme = "light" | "dark";

const light = {
  // ---------------------------------------------------------------------------
  // Surfaces: backgrounds, from the screen down to small fills.
  // Charte Racontelle : blanc doux, rose thé, sauge douce, brun mémoire,
  // bleu encre doux.
  // ---------------------------------------------------------------------------
  surface: "#FFFFFF",
  onSurface: "#2F3E52",
  surfaceSecondary: "#F7F3EE",
  onSurfaceSecondary: "#4A5568",
  surfaceTertiary: "#EFE8DF",
  onSurfaceTertiary: "#2F3E52",
  surfaceInverse: "#2F3E52",
  onSurfaceInverse: "#FFFFFF",
  muted: "#7C8698",

  // ---------------------------------------------------------------------------
  // Brand: rose thé #E7A7A5, sauge douce #B9C5B3, bleu encre doux #2F3E52.
  // ---------------------------------------------------------------------------
  brand: "#E7A7A5",
  onBrand: "#2F3E52",
  brandPrimary: "#2F3E52",
  onBrandPrimary: "#FFFFFF",
  brandSecondary: "#B9C5B3",
  onBrandSecondary: "#2F3E52",
  brandTertiary: "#F6E8E7",
  onBrandTertiary: "#A65F5B",

  // ---------------------------------------------------------------------------
  // Status: semantic only. Brun mémoire #A67C63 porte les avertissements.
  // ---------------------------------------------------------------------------
  success: "#5F6E57",
  onSuccess: "#FFFFFF",
  warning: "#A67C63",
  onWarning: "#FFFFFF",
  error: "#B0544E",
  onError: "#FFFFFF",
  info: "#2F3E52",
  onInfo: "#FFFFFF",

  // ---------------------------------------------------------------------------
  // Lines
  // ---------------------------------------------------------------------------
  border: "#E9E1D7",
  borderStrong: "#A67C63",
  divider: "#F0EAE2",
};

export type ThemeColors = typeof light;

export const defaultScheme = "light" satisfies ColorScheme;

export const themes: { light: ThemeColors; dark?: ThemeColors } = { light };

// In-app theme toggle, only after `dark` exists in `themes`. Call
// setColorScheme("dark"), setColorScheme("light"), or setColorScheme(null) to
// follow the device. Every useTheme() consumer re-renders. Persisting the
// choice and re-applying it on launch is the toggle's job.
export function setColorScheme(scheme: ColorScheme | null) {
  // RN 0.86 re-reads the device scheme only for the literal "unspecified";
  // null would pin useColorScheme() to null and the app to light.
  Appearance.setColorScheme?.(scheme ?? "unspecified");
}

// Keep native surfaces (alerts, pickers, navigation chrome) on the schemes this
// app ships: light only forces light; once `dark` exists the device decides.
// Optional call because react-native-web does not implement it.
setColorScheme?.(themes.dark ? null : defaultScheme);

export function useTheme(): { scheme: ColorScheme; colors: ThemeColors } {
  const system = useColorScheme();
  const scheme: ColorScheme = system === "dark" && themes.dark ? "dark" : defaultScheme;
  return { scheme, colors: themes[scheme] ?? themes.light };
}

// Themed StyleSheet: returns a hook that builds the sheet from the active
// scheme's colors and memoizes it until the scheme changes.
export function makeStyles<T extends StyleSheet.NamedStyles<T> | StyleSheet.NamedStyles<any>>(
  factory: (colors: ThemeColors) => T & StyleSheet.NamedStyles<any>,
): () => T {
  return function useStyles(): T {
    const { colors } = useTheme();
    return useMemo(() => StyleSheet.create(factory(colors)), [colors]);
  };
}


