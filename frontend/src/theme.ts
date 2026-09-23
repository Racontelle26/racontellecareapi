// Design tokens for Racontelle. Light theme only.
// Keys mirror the "color" block of /app/design_guidelines.json.
// Use makeStyles() for stylesheets and useTheme().colors for color props.

import { useMemo } from "react";
import { Appearance, StyleSheet, useColorScheme } from "react-native";

export type ColorScheme = "light" | "dark";

const light = {
  surface: "#FDFBF7",
  onSurface: "#3A332C",
  surfaceSecondary: "#F5F2EB",
  onSurfaceSecondary: "#4A423B",
  surfaceTertiary: "#EBE6DC",
  onSurfaceTertiary: "#5C5249",
  surfaceInverse: "#3A332C",
  onSurfaceInverse: "#FDFBF7",
  muted: "#8A8177",

  brand: "#C98B8B",
  onBrand: "#FDFBF7",
  brandPrimary: "#B57477",
  onBrandPrimary: "#FDFBF7",
  brandSecondary: "#738A70",
  onBrandSecondary: "#FDFBF7",
  brandTertiary: "#F2DADA",
  onBrandTertiary: "#824D4D",

  success: "#738A70",
  onSuccess: "#FDFBF7",
  warning: "#D1A054",
  onWarning: "#FDFBF7",
  error: "#A85252",
  onError: "#FDFBF7",
  info: "#8A9691",
  onInfo: "#FDFBF7",

  border: "#EBE6DC",
  borderStrong: "#D6CFC1",
  divider: "#EBE6DC",
};

export type ThemeColors = typeof light;

export const defaultScheme = "light" satisfies ColorScheme;

export const themes: { light: ThemeColors; dark?: ThemeColors } = { light };

export function setColorScheme(scheme: ColorScheme | null) {
  Appearance.setColorScheme?.(scheme ?? "unspecified");
}

setColorScheme?.(themes.dark ? null : defaultScheme);

export function useTheme(): { scheme: ColorScheme; colors: ThemeColors } {
  const system = useColorScheme();
  const scheme: ColorScheme = system === "dark" && themes.dark ? "dark" : defaultScheme;
  return { scheme, colors: themes[scheme] ?? themes.light };
}

export function makeStyles<T extends StyleSheet.NamedStyles<T> | StyleSheet.NamedStyles<any>>(
  factory: (colors: ThemeColors) => T & StyleSheet.NamedStyles<any>,
): () => T {
  return function useStyles(): T {
    const { colors } = useTheme();
    return useMemo(() => StyleSheet.create(factory(colors)), [colors]);
  };
}

// Typography helpers — Cormorant Garamond for display, DM Sans for body.
export const fonts = {
  display: "Cormorant",
  displayMedium: "CormorantMedium",
  displaySemiBold: "CormorantSemiBold",
  body: "DMSans",
  bodyMedium: "DMSansMedium",
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 48 };
export const radius = { sm: 6, md: 12, lg: 20, pill: 999 };
