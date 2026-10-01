// Design tokens for Racontelle. Light theme only.
// Charte graphique Racontelle : Blanc doux #FFFFFF, Rose thé #E7A7A5, Sauge douce #B9C5B3,
// Brun mémoire #A67C63, Bleu encre doux #2F3E52 ; Allura (accroches), Cormorant Garamond (textes),
// Montserrat (menus, boutons, petits titres).
// Charter hues too light to carry text (rose thé, sauge) get a deeper shade of the same hue for
// text and buttons, so body text keeps a 4.5:1 contrast on white.
// Use makeStyles() for stylesheets and useTheme().colors for color props.

import { useMemo } from "react";
import { Appearance, StyleSheet, useColorScheme } from "react-native";

export type ColorScheme = "light" | "dark";

export const charte = {
  blancDoux: "#FFFFFF",
  roseThe: "#E7A7A5",
  saugeDouce: "#B9C5B3",
  brunMemoire: "#A67C63",
  bleuEncre: "#2F3E52",
};

const light = {
  surface: charte.blancDoux,
  onSurface: charte.bleuEncre,
  surfaceSecondary: "#FBF6F4",
  onSurfaceSecondary: "#3B4A5E",
  surfaceTertiary: "#F3EAE6",
  onSurfaceTertiary: "#4E5A69",
  surfaceInverse: charte.bleuEncre,
  onSurfaceInverse: charte.blancDoux,
  muted: "#6F6660",

  brand: charte.roseThe,
  onBrand: charte.blancDoux,
  brandPrimary: "#AE5856", // rose thé, deepened for white text on buttons
  onBrandPrimary: charte.blancDoux,
  brandSecondary: "#5F7359", // sauge douce, deepened for labels and icons
  onBrandSecondary: charte.blancDoux,
  brandTertiary: "#F9E6E5",
  onBrandTertiary: "#7E3F3E",
  brandSoft: charte.saugeDouce,
  accent: charte.brunMemoire,

  success: "#5F7359",
  onSuccess: charte.blancDoux,
  warning: charte.brunMemoire,
  onWarning: charte.blancDoux,
  error: "#A64542",
  onError: charte.blancDoux,
  info: "#5A6B7E",
  onInfo: charte.blancDoux,

  border: "#EFE6E2",
  borderStrong: "#DCCFC9",
  divider: "#EFE6E2",
};

// Avatar colours drawn from the charter (deep enough for white initials).
export const AVATAR_COLORS = ["#C97B79", "#7F9478", charte.brunMemoire, charte.bleuEncre, "#AE5856", "#6E8A8A"];

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

// Typography — charte Racontelle.
export const fonts = {
  script: "Allura", // titres & accroches, used sparingly
  display: "Cormorant",
  displayMedium: "CormorantMedium",
  displaySemiBold: "CormorantSemiBold",
  text: "Cormorant", // textes & corps
  textMedium: "CormorantMedium",
  body: "Montserrat", // menus, boutons, petits titres, champs de saisie
  bodyMedium: "MontserratMedium",
  bodySemiBold: "MontserratSemiBold",
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 48 };
export const radius = { sm: 6, md: 12, lg: 20, pill: 999 };
