import { useState } from "react";
import { View, Pressable, ScrollView, Switch, ActivityIndicator } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CaretRight, Users, ChatCircleDots, SignOut, Microphone, Clock, ShieldCheck } from "phosphor-react-native";
import { Body, Button, Card, Label, TextField, Title, Avatar } from "@/src/components/ui";
import { api } from "@/src/api/client";
import { useAuth } from "@/src/auth/auth-context";
import { useToast } from "@/src/components/toast";
import { AvatarPicker } from "@/src/components/avatar-picker";
import { usesNativeTabs } from "@/src/navigation";
import { AVATAR_COLORS as COLORS, makeStyles, spacing, useTheme } from "@/src/theme";
type FamilyMember = { id: string; display_name: string; relationship_label?: string | null; initials_color?: string; avatar_url?: string | null; status: string; capsule_count?: number; total_seconds?: number };

function shortDuration(seconds: number) {
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60 ? `${minutes % 60} min` : ""}`.trim();
}

export default function Profile() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const { user, member, signOut, refresh } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const membersQ = useQuery({ queryKey: ["members"], queryFn: () => api.get<FamilyMember[]>("/circle/members") });
  const activeMembers = membersQ.data?.filter((item) => item.status === "active") ?? [];

  const [name, setName] = useState(user?.display_name ?? "");
  const [relationship, setRelationship] = useState(user?.relationship_label ?? "");
  const [color, setColor] = useState(member?.initials_color ?? COLORS[0]);
  const [dailyEmail, setDailyEmail] = useState(member?.daily_email ?? true);
  const [saving, setSaving] = useState(false);
  const [confirmDeletion, setConfirmDeletion] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const consentsQ = useQuery({
    queryKey: ["consents"],
    queryFn: () => api.get<{ consents: { consent_type: string; version: string; occurred_at: string }[]; deletion_request: { created_at: string } | null }>("/me/consents"),
  });
  const consent = consentsQ.data?.consents.find((item) => item.consent_type === "cgu_beta");

  const requestDeletion = async () => {
    setRequesting(true);
    try {
      await api.post("/me/deletion-request", { scope: "account" });
      await consentsQ.refetch();
      setConfirmDeletion(false);
      toast.show("Demande de suppression envoyée", "success");
    } catch (e: any) {
      toast.show(e?.message || "La demande n’a pas pu être envoyée. Réessayez.", "error");
    } finally {
      setRequesting(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.patch("/me/preferences", {
        display_name: name.trim(),
        relationship_label: relationship.trim(),
        initials_color: color,
        daily_email: dailyEmail,
      });
      await refresh();
      qc.invalidateQueries({ queryKey: ["circle"] });
      toast.show("Profil mis à jour", "success");
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    } finally {
      setSaving(false);
    }
  };


  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + spacing.lg, paddingBottom: bottomChrome + spacing.xxl }]}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.head}>
        {member ? (
          <AvatarPicker
            memberId={member.id}
            name={name || "?"}
            color={color}
            photo={membersQ.data?.find((item) => item.id === member.id)?.avatar_url}
            size={84}
            editable
          />
        ) : (
          <Avatar name={name || "?"} color={color} size={84} />
        )}
        <Title style={styles.name}>{name}</Title>
        <Label style={styles.email}>{user?.email}</Label>
      </View>

      <Card style={styles.card}>
        <Label style={styles.section}>MON PROFIL</Label>
        <TextField label="PRÉNOM" testID="profile-name" value={name} onChangeText={setName} />
        <TextField label="LIEN DE FAMILLE" testID="profile-relationship" value={relationship} onChangeText={setRelationship} placeholder="Grand-mère, papa…" />
        <Label style={styles.section}>MA COULEUR</Label>
        <View style={styles.colorRow}>
          {COLORS.map((c) => (
            <Pressable
              key={c}
              testID={`profile-color-${c}`}
              onPress={() => setColor(c)}
              style={[styles.swatch, { backgroundColor: c }, color === c && styles.swatchActive]}
            />
          ))}
        </View>
        <View style={styles.toggleRow}>
          <View style={{ flex: 1 }}>
            <Body>Question du jour par e-mail</Body>
            <Body muted style={styles.toggleSub}>Un rappel doux, une fois par jour</Body>
          </View>
          <Switch
            testID="profile-daily-toggle"
            value={dailyEmail}
            onValueChange={setDailyEmail}
            trackColor={{ true: colors.brandSecondary, false: colors.surfaceTertiary }}
            thumbColor={colors.surface}
          />
        </View>
        <Button title="Enregistrer" testID="profile-save" loading={saving} onPress={save} />
      </Card>

      <View style={styles.familySection} testID="profile-family-section">
        <View style={styles.familyHeader}>
          <View><Label style={styles.section}>MEMBRES DE LA FAMILLE</Label><Title style={styles.familyTitle}>Leurs souvenirs</Title></View>
          <Pressable testID="profile-manage-members" onPress={() => router.push("/members")} style={styles.manageButton}><Label style={styles.manageText}>Gérer</Label></Pressable>
        </View>
        {membersQ.isLoading ? <ActivityIndicator color={colors.brandSecondary} /> : activeMembers.map((item) => (
          <Pressable key={item.id} testID={`profile-family-member-${item.id}`} onPress={() => router.push(`/family-member/${item.id}`)} style={({ pressed }) => [styles.familyCard, pressed && styles.familyCardPressed]}>
            <Avatar name={item.display_name} color={item.initials_color} photo={item.avatar_url} size={52} />
            <View style={styles.familyInfo}>
              <Body style={styles.familyName} numberOfLines={1}>{item.display_name}</Body>
              <Label style={styles.familyRelation} numberOfLines={1}>{item.relationship_label || "Membre"}</Label>
              <View style={styles.familyStats}>
                <View style={styles.familyStat}><Microphone color={colors.brandSecondary} size={15} /><Label>{item.capsule_count ?? 0} souvenir{(item.capsule_count ?? 0) > 1 ? "s" : ""}</Label></View>
                <View style={styles.familyStat}><Clock color={colors.brandSecondary} size={15} /><Label>{shortDuration(item.total_seconds ?? 0)}</Label></View>
              </View>
            </View>
            <CaretRight color={colors.muted} size={19} />
          </Pressable>
        ))}
      </View>

      <Card style={styles.linksCard}>
        <Pressable style={styles.link} testID="profile-members" onPress={() => router.push("/members")}>
          <Users color={colors.brandPrimary} size={22} />
          <Body style={styles.linkText}>Membres & invitations</Body>
          <CaretRight color={colors.muted} size={18} />
        </Pressable>
        <View style={styles.linkDivider} />
        <Pressable style={styles.link} testID="profile-feedback" onPress={() => router.push("/feedback")}>
          <ChatCircleDots color={colors.brandPrimary} size={22} />
          <Body style={styles.linkText}>Donner mon avis (bêta)</Body>
          <CaretRight color={colors.muted} size={18} />
        </Pressable>
      </Card>

      <Card style={styles.card} testID="profile-privacy">
        <Label style={styles.section}>CONFIDENTIALITÉ</Label>
        <View style={styles.privacyRow}>
          <ShieldCheck color={colors.brandSecondary} size={22} />
          <Body style={styles.privacyText}>
            {consent
              ? `Conditions de la bêta acceptées le ${new Date(consent.occurred_at).toLocaleDateString("fr-FR")} (version ${consent.version}).`
              : "Conditions de la bêta : acceptation non retrouvée."}
          </Body>
        </View>
        <Body muted style={styles.toggleSub}>
          Vos souvenirs ne sont visibles que par les membres de votre famille. Chaque personne enregistrée doit être d’accord.
        </Body>
        {consentsQ.data?.deletion_request ? (
          <Body style={styles.privacyText} testID="profile-deletion-pending">
            Demande de suppression envoyée le {new Date(consentsQ.data.deletion_request.created_at).toLocaleDateString("fr-FR")}. L’équipe Racontelle vous confirmera la suppression par e-mail.
          </Body>
        ) : confirmDeletion ? (
          <View style={styles.deleteConfirm}>
            <Body style={styles.privacyText}>
              Votre compte, votre profil et les souvenirs que vous avez enregistrés seront supprimés par l’équipe Racontelle. Cette action est définitive.
            </Body>
            <Button title="Confirmer la demande de suppression" variant="secondary" testID="profile-deletion-confirm" loading={requesting} onPress={requestDeletion} />
            <Pressable onPress={() => setConfirmDeletion(false)} style={styles.cancelLink} testID="profile-deletion-cancel">
              <Label style={styles.manageText}>Annuler</Label>
            </Pressable>
          </View>
        ) : (
          <Pressable onPress={() => setConfirmDeletion(true)} style={styles.cancelLink} testID="profile-deletion-request">
            <Label style={styles.deleteText}>Demander la suppression de mes données</Label>
          </Pressable>
        )}
      </Card>

      <Pressable style={styles.logout} testID="profile-logout" onPress={signOut}>
        <SignOut color={colors.error} size={20} />
        <Label style={styles.logoutText}>Se déconnecter</Label>
      </Pressable>
    </ScrollView>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface },
  content: { paddingHorizontal: spacing.xl, gap: spacing.lg },
  head: { alignItems: "center", gap: spacing.xs },
  name: { fontSize: 24, marginTop: spacing.sm },
  email: { color: colors.muted },
  card: { gap: spacing.md },
  section: { color: colors.brandSecondary, marginTop: spacing.xs },
  colorRow: { flexDirection: "row", gap: spacing.md, flexWrap: "wrap" },
  swatch: { width: 38, height: 38, borderRadius: 19, borderWidth: 2, borderColor: "transparent" },
  swatchActive: { borderColor: colors.onSurface },
  toggleRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginTop: spacing.xs },
  toggleSub: { fontSize: 12 },
  familySection: { gap: spacing.md },
  familyHeader: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between" },
  familyTitle: { fontSize: 22 },
  manageButton: { minWidth: 54, minHeight: 44, alignItems: "center", justifyContent: "center" },
  manageText: { color: colors.brandPrimary },
  familyCard: { minHeight: 88, flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: 20 },
  familyCardPressed: { opacity: 0.78 },
  familyInfo: { flex: 1, gap: 2 },
  familyName: { fontSize: 17 },
  familyRelation: { color: colors.muted },
  familyStats: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, marginTop: spacing.xs },
  familyStat: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  linksCard: { padding: 0, overflow: "hidden" },
  link: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg },
  linkText: { flex: 1, fontSize: 15 },
  linkDivider: { height: 1, backgroundColor: colors.divider, marginLeft: 54 },
  privacyRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  privacyText: { flex: 1, fontSize: 14, lineHeight: 20 },
  deleteConfirm: { gap: spacing.sm },
  cancelLink: { minHeight: 44, justifyContent: "center", alignSelf: "flex-start" },
  deleteText: { color: colors.error },
  logout: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, padding: spacing.md },
  logoutText: { color: colors.error, fontSize: 15 },
}));
