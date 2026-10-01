import { useState } from "react";
import { View, Pressable, ActivityIndicator } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CaretLeft, PaperPlaneTilt, ArrowsClockwise, XCircle, UserPlus, PencilSimple, Trash } from "phosphor-react-native";
import { Body, Button, Card, Label, TextField, Title, Avatar } from "@/src/components/ui";
import { api } from "@/src/api/client";
import { useAuth } from "@/src/auth/auth-context";
import { useToast } from "@/src/components/toast";
import { confirmAction } from "@/src/components/confirm";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Member = { id: string; user_id?: string | null; display_name: string; initials_color?: string; avatar_url?: string | null; relationship_label?: string | null; status: string; role?: string; capsule_count?: number };
type Invitation = { id: string; member_id: string; email: string; code?: string };
type FormMode = "direct" | "invite" | "edit" | null;

export default function Members() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const toast = useToast();
  const qc = useQueryClient();
  const { member } = useAuth();
  const isOwner = member?.role === "owner";
  const membersQ = useQuery({ queryKey: ["members"], queryFn: () => api.get<Member[]>("/circle/members") });
  const invitesQ = useQuery({ queryKey: ["invitations"], queryFn: () => api.get<Invitation[]>("/circle/invitations"), enabled: isOwner });

  const [formMode, setFormMode] = useState<FormMode>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [rel, setRel] = useState("");
  const [sending, setSending] = useState(false);

  const active = membersQ.data?.filter((item) => item.status === "active") ?? [];
  const pending = membersQ.data?.filter((item) => item.status === "pending") ?? [];
  const directCount = active.filter((item) => item.role === "owner" || item.role === "profile").length;

  const resetForm = () => {
    setFormMode(null); setEditingId(null); setName(""); setEmail(""); setRel("");
  };

  const openEdit = (item: Member) => {
    setEditingId(item.id); setName(item.display_name); setRel(item.relationship_label || ""); setEmail(""); setFormMode("edit");
  };

  const saveProfile = async () => {
    if (!name.trim() || !rel.trim()) return toast.show("Prénom et lien familial requis", "error");
    setSending(true);
    try {
      const payload = { display_name: name.trim(), relationship_label: rel.trim() };
      if (formMode === "edit" && editingId) await api.patch(`/circle/members/${editingId}`, payload);
      else await api.post("/circle/members", payload);
      toast.show(formMode === "edit" ? "Profil modifié" : "Profil familial ajouté", "success");
      resetForm();
      await Promise.all([qc.invalidateQueries({ queryKey: ["members"] }), qc.invalidateQueries({ queryKey: ["circle"] })]);
    } catch (e: any) {
      toast.show(e?.message || "Enregistrement impossible", "error");
    } finally {
      setSending(false);
    }
  };

  const invite = async () => {
    if (!name.trim() || !email.trim()) return toast.show("Prénom et e-mail requis", "error");
    setSending(true);
    try {
      const res = await api.post<{ code: string }>("/circle/invitations", { display_name: name.trim(), email: email.trim(), relationship_label: rel.trim() || undefined });
      toast.show(`Invitation envoyée · code ${res.code}`, "success");
      resetForm();
      await Promise.all([qc.invalidateQueries({ queryKey: ["members"] }), qc.invalidateQueries({ queryKey: ["invitations"] }), qc.invalidateQueries({ queryKey: ["circle"] })]);
    } catch (e: any) {
      toast.show(e?.message || "Envoi impossible", "error");
    } finally {
      setSending(false);
    }
  };

  const deleteProfile = async (id: string) => {
    if (confirmDeleteId !== id) return setConfirmDeleteId(id);
    try {
      await api.del(`/circle/members/${id}`);
      setConfirmDeleteId(null);
      await Promise.all([qc.invalidateQueries({ queryKey: ["members"] }), qc.invalidateQueries({ queryKey: ["circle"] })]);
      toast.show("Profil supprimé", "info");
    } catch (e: any) {
      toast.show(e?.message || "Suppression impossible", "error");
    }
  };

  const resend = async (invitation: Invitation) => {
    try {
      const res = await api.post<{ code: string }>(`/circle/invitations/${invitation.id}/resend`);
      toast.show(`Invitation renvoyée · nouveau code ${res.code} (l’ancien ne fonctionne plus)`, "info");
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    }
  };

  const revoke = async (invitation: Invitation) => {
    const ok = await confirmAction(
      "Annuler cette invitation ?",
      `Le code envoyé à ${invitation.email} ne fonctionnera plus.`,
      "Annuler l’invitation",
    );
    if (!ok) return;
    try {
      await api.del(`/circle/invitations/${invitation.id}`);
      await Promise.all([qc.invalidateQueries({ queryKey: ["members"] }), qc.invalidateQueries({ queryKey: ["invitations"] }), qc.invalidateQueries({ queryKey: ["circle"] })]);
      toast.show("Invitation annulée", "info");
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    }
  };

  return (
    <View style={styles.container} testID="members-page">
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Pressable onPress={() => router.back()} style={styles.iconButton} testID="members-back"><CaretLeft color={colors.onSurface} size={26} /></Pressable>
        <Title style={styles.headerTitle}>Membres</Title><View style={styles.iconButton} />
      </View>
      <KeyboardAwareScrollView contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + spacing.xxl }]} bottomOffset={20} showsVerticalScrollIndicator={false}>
        <Card style={styles.counterCard} testID="members-direct-counter">
          <View><Label style={styles.counterLabel}>PROFILS FAMILIAUX</Label><Title style={styles.counterTitle}>{Math.min(directCount, 4)}/4 créés directement</Title></View>
          <Body muted>{directCount < 4 ? `${4 - directCount} profil${4 - directCount > 1 ? "s" : ""} encore disponible${4 - directCount > 1 ? "s" : ""} sans e-mail. Les proches qui ont un smartphone peuvent être invités par e-mail à tout moment.` : "Les prochains membres seront invités par e-mail."}</Body>
        </Card>

        {membersQ.isLoading ? <ActivityIndicator color={colors.brandSecondary} style={{ marginTop: spacing.xl }} /> : (
          <>
            {active.map((item) => {
              const managed = isOwner && !item.user_id && item.role === "profile";
              return (
                <Card key={item.id} style={styles.memberCard} testID={`member-${item.id}`}>
                  <Avatar name={item.display_name} color={item.initials_color} photo={item.avatar_url} size={48} />
                  <View style={styles.memberInfo}>
                    <Body style={styles.memberName}>{item.display_name}</Body>
                    <Label style={styles.memberSub}>{item.relationship_label || "Membre"}{item.role === "owner" ? " · créateur" : ""} · {item.capsule_count ?? 0} souvenir{(item.capsule_count ?? 0) > 1 ? "s" : ""}</Label>
                    {confirmDeleteId === item.id ? <Label style={styles.confirmHint}>Appuyez encore pour confirmer</Label> : null}
                  </View>
                  {managed ? <View style={styles.memberActions}>
                    <Pressable testID={`member-edit-${item.id}`} onPress={() => openEdit(item)} style={styles.iconButton}><PencilSimple color={colors.brandPrimary} size={21} /></Pressable>
                    <Pressable testID={`member-delete-${item.id}`} onPress={() => deleteProfile(item.id)} style={styles.iconButton}><Trash color={colors.error} size={20} /></Pressable>
                  </View> : null}
                </Card>
              );
            })}

            {pending.length ? <Label style={styles.section}>INVITATIONS EN ATTENTE</Label> : null}
            {pending.map((item) => {
              const invitation = invitesQ.data?.find((entry) => entry.member_id === item.id);
              return <Card key={item.id} style={styles.memberCard} testID={`pending-${item.id}`}>
                <Avatar name={item.display_name} color={item.initials_color} photo={item.avatar_url} size={48} />
                <View style={styles.memberInfo}><Body style={styles.memberName}>{item.display_name}</Body><Label style={styles.memberSub}>Invitation en attente</Label></View>
                {isOwner && invitation ? <View style={styles.memberActions}>
                  <Pressable onPress={() => resend(invitation)} style={styles.iconButton} testID={`resend-${item.id}`}><ArrowsClockwise color={colors.brandPrimary} size={22} /></Pressable>
                  <Pressable onPress={() => revoke(invitation)} style={styles.iconButton} testID={`revoke-${item.id}`}><XCircle color={colors.error} size={22} /></Pressable>
                </View> : null}
              </Card>;
            })}

            {isOwner && formMode ? <Card style={styles.form} testID={`member-${formMode}-form`}>
              <Label style={styles.section}>{formMode === "invite" ? "INVITATION PAR E-MAIL" : formMode === "edit" ? "MODIFIER LE PROFIL" : "NOUVEAU PROFIL"}</Label>
              <TextField label="PRÉNOM" testID="member-form-name" value={name} onChangeText={setName} placeholder="Papy Jean" />
              <TextField label="LIEN FAMILIAL" testID="member-form-relation" value={rel} onChangeText={setRel} placeholder="Grand-père" />
              {formMode === "invite" ? <TextField label="E-MAIL" testID="member-form-email" value={email} onChangeText={setEmail} placeholder="jean@exemple.fr" autoCapitalize="none" keyboardType="email-address" /> : null}
              <Button title={formMode === "invite" ? "Envoyer l’invitation" : formMode === "edit" ? "Enregistrer les modifications" : "Créer ce profil"} testID="member-form-submit" loading={sending} onPress={formMode === "invite" ? invite : saveProfile} icon={formMode === "invite" ? <PaperPlaneTilt color={colors.onBrandPrimary} size={18} weight="fill" /> : undefined} />
              <Pressable onPress={resetForm} testID="member-form-cancel" style={styles.cancelButton}><Label style={styles.cancel}>Annuler</Label></Pressable>
            </Card> : null}

            {isOwner && !formMode ? (
              <>
                <Pressable style={styles.addButton} testID="members-invite-open" onPress={() => setFormMode("invite")}><PaperPlaneTilt color={colors.brandPrimary} size={22} /><Body style={styles.addText}>Inviter un membre par e-mail</Body></Pressable>
                {directCount < 4 ? (
                  <Pressable style={styles.addButton} testID="members-add-profile" onPress={() => setFormMode("direct")}><UserPlus color={colors.brandPrimary} size={22} /><Body style={styles.addText}>Ajouter un profil sans e-mail</Body></Pressable>
                ) : null}
              </>
            ) : null}
          </>
        )}
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerTitle: { fontSize: 22 },
  iconButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  content: { padding: spacing.xl, gap: spacing.md },
  counterCard: { gap: spacing.sm, backgroundColor: colors.brandTertiary },
  counterLabel: { color: colors.brandPrimary },
  counterTitle: { fontSize: 22, color: colors.onBrandTertiary },
  memberCard: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  memberInfo: { flex: 1, gap: 2 },
  memberName: { fontSize: 16 },
  memberSub: { color: colors.muted },
  memberActions: { flexDirection: "row" },
  confirmHint: { color: colors.error, fontSize: 11 },
  section: { color: colors.brandSecondary, marginTop: spacing.sm },
  form: { gap: spacing.md },
  cancelButton: { minHeight: 44, alignItems: "center", justifyContent: "center" },
  cancel: { color: colors.muted },
  addButton: { minHeight: 58, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, borderWidth: 1.5, borderStyle: "dashed", borderColor: colors.brandTertiary, borderRadius: radius.lg, padding: spacing.lg },
  addText: { color: colors.brandPrimary, fontSize: 15 },
}));