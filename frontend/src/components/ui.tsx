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
import { Image } from "expo-image";
import { Eye, EyeSlash } from "phosphor-react-native";
import { mediaUrl, useMediaToken } from "@/src/api/client";
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

// Allura script, reserved for short accroches (charte : « titres & accroches »).
export function Script({ style, ...props }: TextProps & { children: React.ReactNode }) {
  const styles = useTextStyles();
  return <Text {...props} style={[styles.script, style]} />;
}

const useTextStyles = makeStyles((colors) => ({
  display: { fontFamily: fonts.displaySemiBold, fontSize: 34, color: colors.onSurface, lineHeight: 40 },
  title: { fontFamily: fonts.displaySemiBold, fontSize: 25, color: colors.onSurface, lineHeight: 31 },
  // Cormorant has a small x-height: body copy is set larger than a sans-serif would be.
  body: { fontFamily: fonts.textMedium, fontSize: 17, color: colors.onSurface, lineHeight: 24 },
  bodyMuted: { color: colors.muted },
  label: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.onSurfaceTertiary, letterSpacing: 0.4 },
  script: { fontFamily: fonts.script, fontSize: 34, color: colors.brandPrimary, lineHeight: 44 },
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
  primaryText: { fontFamily: fonts.bodySemiBold, fontSize: 15, color: colors.onBrandPrimary, letterSpacing: 0.3 },
  secondaryText: { fontFamily: fonts.bodySemiBold, fontSize: 15, color: colors.onBrandTertiary, letterSpacing: 0.3 },
  ghostText: { fontFamily: fonts.bodySemiBold, fontSize: 15, color: colors.onSurface, letterSpacing: 0.3 },
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
// PasswordField — eye toggle + autofill hints so the phone's password manager
// (Google, Samsung, iCloud Keychain) offers to save and refill the password.
// ---------------------------------------------------------------------------
type PasswordFieldProps = Omit<FieldProps, "secureTextEntry" | "accessory"> & { isNew?: boolean };

export function PasswordField({ isNew, testID, ...props }: PasswordFieldProps) {
  const { colors } = useTheme();
  const [visible, setVisible] = React.useState(false);
  return (
    <TextField
      {...props}
      testID={testID}
      secureTextEntry={!visible}
      autoCapitalize="none"
      autoCorrect={false}
      autoComplete={isNew ? "new-password" : "current-password"}
      textContentType={isNew ? "newPassword" : "password"}
      importantForAutofill="yes"
      accessory={
        <Pressable
          testID={testID ? `${testID}-visibility` : undefined}
          onPress={() => setVisible((v) => !v)}
          hitSlop={8}
          style={{ width: 44, height: 44, alignItems: "center", justifyContent: "center" }}
          accessibilityRole="button"
          accessibilityLabel={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
        >
          {visible ? <EyeSlash color={colors.muted} size={23} /> : <Eye color={colors.muted} size={23} />}
        </Pressable>
      }
    />
  );
}

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
export function Avatar({ name, color, size = 44, photo }: { name: string; color?: string; size?: number; photo?: string | null }) {
  const { colors } = useTheme();
  const token = useMediaToken();
  const uri = mediaUrl(photo, token);
  if (uri) {
    return (
      <Image
        source={{ uri }}
        style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: color || colors.brand }}
        contentFit="cover"
        transition={150}
        accessibilityLabel={`Photo de ${name}`}
      />
    );
  }
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
      <Text style={{ color: colors.onBrand, fontFamily: fonts.bodySemiBold, fontSize: size * 0.34 }}>{initials}</Text>
    </View>
  );
}
