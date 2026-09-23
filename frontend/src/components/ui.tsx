import React from "react";
import {
  ActivityIndicator,
  Pressable,
  Text,
  TextInput,
  TextInputProps,
  TextProps,
  View,
  ViewProps,
} from "react-native";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

// ---------------------------------------------------------------------------
// Typography
// ---------------------------------------------------------------------------
export function Display({ style, ...props }: TextProps & { children: React.ReactNode }) {
  const styles = useTextStyles();
  return <Text {...props} style={[styles.display, style]} />;
}

export function Title({ style, ...props }: TextProps & { children: React.ReactNode }) {
  const styles = useTextStyles();
  return <Text {...props} style={[styles.title, style]} />;
}

export function Body({ style, muted, ...props }: TextProps & { muted?: boolean; children: React.ReactNode }) {
  const styles = useTextStyles();
  return <Text {...props} style={[styles.body, muted && styles.bodyMuted, style]} />;
}

export function Label({ style, ...props }: TextProps & { children: React.ReactNode }) {
  const styles = useTextStyles();
  return <Text {...props} style={[styles.label, style]} />;
}

const useTextStyles = makeStyles((colors) => ({
  display: { fontFamily: fonts.displaySemiBold, fontSize: 34, color: colors.onSurface, lineHeight: 40 },
  title: { fontFamily: fonts.displayMedium, fontSize: 24, color: colors.onSurface, lineHeight: 30 },
  body: { fontFamily: fonts.body, fontSize: 15, color: colors.onSurface, lineHeight: 22 },
  bodyMuted: { color: colors.muted },
  label: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.onSurfaceTertiary, letterSpacing: 0.3 },
}));

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------
type ButtonProps = {
  title: string;
  onPress?: () => void;
  variant?: "primary" | "secondary" | "ghost";
  loading?: boolean;
  disabled?: boolean;
  testID?: string;
  icon?: React.ReactNode;
};

export function Button({ title, onPress, variant = "primary", loading, disabled, testID, icon }: ButtonProps) {
  const styles = useButtonStyles();
  const { colors } = useTheme();
  const isDisabled = disabled || loading;
  const bg =
    variant === "primary" ? styles.primary : variant === "secondary" ? styles.secondary : styles.ghost;
  const txt =
    variant === "primary" ? styles.primaryText : variant === "secondary" ? styles.secondaryText : styles.ghostText;
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [styles.base, bg, pressed && !isDisabled && styles.pressed, isDisabled && styles.disabled]}
    >
      {loading ? (
        <ActivityIndicator color={variant === "primary" ? colors.onBrandPrimary : colors.brandPrimary} />
      ) : (
        <View style={styles.row}>
          {icon}
          <Text style={txt}>{title}</Text>
        </View>
      )}
    </Pressable>
  );
}

const useButtonStyles = makeStyles((colors) => ({
  base: {
    height: 54,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
  },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  primary: { backgroundColor: colors.brandPrimary },
  secondary: { backgroundColor: colors.brandTertiary },
  ghost: { backgroundColor: "transparent", borderWidth: 1, borderColor: colors.borderStrong },
  pressed: { opacity: 0.85 },
  disabled: { opacity: 0.5 },
  primaryText: { fontFamily: fonts.bodyMedium, fontSize: 16, color: colors.onBrandPrimary },
  secondaryText: { fontFamily: fonts.bodyMedium, fontSize: 16, color: colors.onBrandTertiary },
  ghostText: { fontFamily: fonts.bodyMedium, fontSize: 16, color: colors.onSurface },
}));

// ---------------------------------------------------------------------------
// TextField
// ---------------------------------------------------------------------------
type FieldProps = TextInputProps & { label?: string; testID?: string; accessory?: React.ReactNode };

export function TextField({ label, testID, style, accessory, ...props }: FieldProps) {
  const styles = useFieldStyles();
  const { colors } = useTheme();
  return (
    <View style={styles.wrap}>
      {label ? <Label style={styles.label}>{label}</Label> : null}
      <View style={styles.inputRow}>
        <TextInput
          testID={testID}
          placeholderTextColor={colors.muted}
          style={[styles.input, accessory ? styles.inputWithAccessory : undefined, style]}
          {...props}
        />
        {accessory ? <View style={styles.accessory}>{accessory}</View> : null}
      </View>
    </View>
  );
}

const useFieldStyles = makeStyles((colors) => ({
  wrap: { gap: spacing.sm },
  label: { marginLeft: spacing.xs },
  inputRow: { position: "relative" },
  input: {
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: 14,
    fontSize: 16,
    fontFamily: fonts.body,
    color: colors.onSurface,
    width: "100%",
  },
  inputWithAccessory: { paddingRight: 58 },
  accessory: { position: "absolute", right: 5, top: 0, bottom: 0, width: 48, alignItems: "center", justifyContent: "center" },
}));

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------
export function Card({ style, ...props }: ViewProps & { children: React.ReactNode }) {
  const styles = useCardStyles();
  return <View {...props} style={[styles.card, style]} />;
}

const useCardStyles = makeStyles((colors) => ({
  card: {
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
}));

// ---------------------------------------------------------------------------
// Avatar
// ---------------------------------------------------------------------------
export function Avatar({ name, color, size = 44 }: { name: string; color?: string; size?: number }) {
  const { colors } = useTheme();
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: color || colors.brand,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Text style={{ color: colors.onBrand, fontFamily: fonts.bodyMedium, fontSize: size * 0.36 }}>{initials}</Text>
    </View>
  );
}
