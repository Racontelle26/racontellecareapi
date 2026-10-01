import { ActivityIndicator, Pressable, ScrollView, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery } from "@tanstack/react-query";
import { CaretLeft, Clock, Microphone, Play } from "phosphor-react-native";
import { Body, Card, Label, Title } from "@/src/components/ui";
import { AvatarPicker } from "@/src/components/avatar-picker";
import { api } from "@/src/api/client";
import { useAuth } from "@/src/auth/auth-context";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Member = { id: string; display_name: string; relationship_label?: string | null; initials_color?: string; avatar_url?: string | null; status: string; capsule_count?: number; total_seconds?: number };
type Capsule = { id: string; question_text?: string; theme?: string; duration_sec: number; recorded_at: string };

function durationLabel(seconds: number) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hours) return `${hours} h ${minutes} min`;
  if (minutes) return `${minutes} min ${secs ? `${secs} s` : ""}`.trim();
  return `${secs} s`;
}

function dateLabel(value: string) {
  return new Date(value).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}

export default function FamilyMemberDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const { member: me } = useAuth();
  const membersQ = useQuery({ queryKey: ["members"], queryFn: () => api.get<Member[]>("/circle/members") });
  const memoriesQ = useQuery({ queryKey: ["capsules", "member", id], queryFn: () => api.get<Capsule[]>(`/capsules?narrator=${encodeURIComponent(String(id))}`) });
  const member = membersQ.data?.find((item) => item.id === id && item.status === "active");
  const memories = memoriesQ.data ?? [];
  const totalSeconds = member?.total_seconds ?? memories.reduce((sum, item) => sum + (item.duration_sec || 0), 0);

  return (
    <View style={styles.container} testID="family-member-detail-page">
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Pressable testID="family-member-back" onPress={() => router.back()} style={styles.iconButton}><CaretLeft color={colors.onSurface} size={26} /></Pressable>
        <Label style={styles.headerLabel}>FICHE MEMBRE</Label><View style={styles.iconButton} />
      </View>
      {membersQ.isLoading || memoriesQ.isLoading ? <ActivityIndicator testID="family-member-loading" color={colors.brandSecondary} style={styles.loader} /> : !member ? (
        <View style={styles.empty} testID="family-member-error"><Title>Membre introuvable</Title><Body muted>Ce profil n’est plus actif.</Body></View>
      ) : (
        <ScrollView contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + spacing.xxl }]} showsVerticalScrollIndicator={false}>
          <View style={styles.identity}>
            <AvatarPicker
              memberId={member.id}
              name={member.display_name}
              color={member.initials_color}
              photo={member.avatar_url}
              size={96}
              editable={me?.id === member.id || me?.role === "owner"}
            />
            {me?.id === member.id || me?.role === "owner" ? (
              <Label style={styles.photoHint}>{member.avatar_url ? "Touchez la photo pour la changer" : "Touchez pour ajouter une photo"}</Label>
            ) : null}
            <Title style={styles.name} testID="family-member-name" numberOfLines={2} adjustsFontSizeToFit minimumFontScale={0.72}>{member.display_name}</Title>
            <Label style={styles.relationship} numberOfLines={2}>{member.relationship_label || "Membre de la famille"}</Label>
          </View>
          <View style={styles.statsRow}>
            <Card style={styles.statCard} testID="family-member-memory-count"><Microphone color={colors.brandPrimary} size={24} /><Title style={styles.statValue}>{memories.length}</Title><Label style={styles.statLabel}>SOUVENIR{memories.length > 1 ? "S" : ""}</Label></Card>
            <Card style={styles.statCard} testID="family-member-total-duration"><Clock color={colors.brandSecondary} size={24} /><Title style={styles.statValue}>{durationLabel(totalSeconds)}</Title><Label style={styles.statLabel}>TEMPS ENREGISTRÉ</Label></Card>
          </View>
          <View style={styles.memoriesHeader}><Title style={styles.memoriesTitle}>Ses souvenirs</Title><Label style={styles.countLabel}>{memories.length}</Label></View>
          {memories.length === 0 ? <Card style={styles.emptyCard} testID="family-member-empty-memories"><Body muted style={styles.emptyText}>Aucun souvenir n’a encore été rattaché à ce profil.</Body></Card> : memories.map((memory) => (
            <Pressable key={memory.id} testID={`family-member-memory-item-${memory.id}`} onPress={() => router.push(`/capsule/${memory.id}`)} style={({ pressed }) => [styles.memoryCard, pressed && styles.pressed]}>
              <View style={styles.memoryText}><Label style={styles.theme}>{memory.theme?.toUpperCase() || "SUR LE VIF"}</Label><Body style={styles.memoryTitle} numberOfLines={2}>{memory.question_text || "Souvenir familial"}</Body><Label style={styles.memoryMeta}>{dateLabel(memory.recorded_at)} · {durationLabel(memory.duration_sec)}</Label></View>
              <View style={styles.playIcon}><Play color={colors.onBrandPrimary} size={17} weight="fill" /></View>
            </Pressable>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  iconButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  headerLabel: { color: colors.brandSecondary },
  loader: { marginTop: spacing.xxxl },
  content: { padding: spacing.xl, gap: spacing.xl },
  identity: { alignItems: "center", gap: spacing.xs, paddingVertical: spacing.md },
  name: { width: "100%", fontSize: 30, marginTop: spacing.sm, textAlign: "center" },
  relationship: { width: "100%", color: colors.muted, textAlign: "center" },
  photoHint: { color: colors.brandPrimary, fontSize: 12, marginTop: spacing.xs },
  statsRow: { flexDirection: "row", gap: spacing.md },
  statCard: { flex: 1, minHeight: 132, alignItems: "center", justifyContent: "center", gap: spacing.xs, paddingHorizontal: spacing.sm },
  statValue: { fontSize: 23, textAlign: "center" },
  statLabel: { color: colors.muted, fontSize: 10, textAlign: "center" },
  memoriesHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  memoriesTitle: { fontSize: 24 },
  countLabel: { color: colors.brandPrimary },
  memoryCard: { minHeight: 92, flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, padding: spacing.lg },
  pressed: { opacity: 0.78 },
  memoryText: { flex: 1, gap: spacing.xs },
  theme: { color: colors.brandSecondary, fontSize: 10 },
  memoryTitle: { fontSize: 16, lineHeight: 22 },
  memoryMeta: { color: colors.muted, fontSize: 11 },
  playIcon: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center", backgroundColor: colors.brandPrimary },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.sm, padding: spacing.xl },
  emptyCard: { alignItems: "center" },
  emptyText: { textAlign: "center" },
}));