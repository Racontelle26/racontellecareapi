import React, { createContext, useCallback, useContext, useRef, useState } from "react";
import { Animated, Platform, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { fonts, radius, spacing, useTheme } from "@/src/theme";

type ToastKind = "success" | "error" | "info";
type ToastCtx = { show: (message: string, kind?: ToastKind) => void };

const Ctx = createContext<ToastCtx | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const [message, setMessage] = useState<string | null>(null);
  const [kind, setKind] = useState<ToastKind>("info");
  const opacity = useRef(new Animated.Value(0)).current;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback(
    (msg: string, k: ToastKind = "info") => {
      setMessage(msg);
      setKind(k);
      if (timer.current) clearTimeout(timer.current);
      Animated.timing(opacity, { toValue: 1, duration: 220, useNativeDriver: Platform.OS !== "web" }).start();
      timer.current = setTimeout(() => {
        Animated.timing(opacity, { toValue: 0, duration: 220, useNativeDriver: Platform.OS !== "web" }).start(() =>
          setMessage(null),
        );
      }, 2600);
    },
    [opacity],
  );

  const bg = kind === "error" ? colors.error : kind === "success" ? colors.success : colors.surfaceInverse;

  return (
    <Ctx.Provider value={{ show }}>
      {children}
      {message ? (
        <Animated.View
          style={[styles.wrap, { top: insets.top + spacing.md, opacity, pointerEvents: "none" }]}
          testID="app-toast"
        >
          <View style={[styles.toast, { backgroundColor: bg }]}>
            <Text style={[styles.text, { color: colors.onSurfaceInverse }]}>{message}</Text>
          </View>
        </Animated.View>
      ) : null}
    </Ctx.Provider>
  );
}

export function useToast(): ToastCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

const styles = StyleSheet.create({
  wrap: { position: "absolute", left: spacing.lg, right: spacing.lg, alignItems: "center", zIndex: 9999 },
  toast: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    maxWidth: 480,
  },
  text: { fontFamily: fonts.bodyMedium, fontSize: 14, textAlign: "center" },
});
