import { Ionicons } from "@expo/vector-icons";
import { Pressable, Text, View } from "react-native";

import { makeStyles, useTheme } from "../theme";
import type { AuthUser } from "../types";

const useStyles = makeStyles((colors) => ({
  card: { borderRadius: 18, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary, padding: 14, gap: 10 },
  top: { flexDirection: "row", alignItems: "center", gap: 10 },
  text: { flex: 1, gap: 3 },
  facility: { color: colors.onSurface, fontSize: 14, lineHeight: 19, fontFamily: "Montserrat-Bold" },
  user: { color: colors.muted, fontSize: 12, lineHeight: 17, fontFamily: "Montserrat-Medium" },
  badge: { alignSelf: "flex-start", borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6, backgroundColor: colors.brandSecondary },
  badgeAdmin: { backgroundColor: colors.brandPrimary },
  badgeText: { color: colors.onBrandSecondary, fontSize: 11, fontFamily: "Montserrat-Bold" },
  badgeTextAdmin: { color: colors.onBrandPrimary },
  action: { minHeight: 44, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 7, borderTopWidth: 1, borderTopColor: colors.divider, paddingTop: 10 },
  actionText: { color: colors.brandPrimary, fontSize: 12, fontFamily: "Montserrat-Bold" },
  pressed: { opacity: 0.75 },
}));

export function EstablishmentBanner({ user, onAuthAction }: { user: AuthUser | null; onAuthAction: () => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const admin = user?.role === "admin";
  return <View testID="header-establishment-card" style={styles.card}>
    <View style={styles.top}><Ionicons name={user ? "business-outline" : "phone-portrait-outline"} color={colors.brandPrimary} size={23} /><View style={styles.text}><Text testID="header-facility-title" style={styles.facility}>{user?.establishment_name ?? "Mode local sur cet appareil"}</Text><Text testID="header-user-name-text" style={styles.user}>{user ? user.full_name : "Synchronisation serveur suspendue"}</Text></View><View testID="header-user-role-badge" style={[styles.badge, admin && styles.badgeAdmin]}><Text style={[styles.badgeText, admin && styles.badgeTextAdmin]}>{admin ? "Administrateur" : user ? "Membre" : "Local"}</Text></View></View>
    <Pressable testID="header-auth-action-button" accessibilityRole="button" onPress={onAuthAction} style={({ pressed }) => [styles.action, pressed && styles.pressed]}><Ionicons name={user ? "log-out-outline" : "log-in-outline"} color={colors.brandPrimary} size={18} /><Text style={styles.actionText}>{user ? "Se déconnecter" : "Se connecter pour synchroniser"}</Text></Pressable>
  </View>;
}