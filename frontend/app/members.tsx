import { useState } from "react";
import { View, Pressable, ActivityIndicator } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CaretLeft, PaperPlaneTilt, ArrowsClockwise, XCircle, UserPlus } from "phosphor-react-native";
import { Body, Button, Card, Label, TextField, Title, Avatar } from "@/src/components/ui";
import { api } from "@/src/api/client";
import { useAuth } from "@/src/auth/auth-context";
import { useToast } from "@/src/components/toast";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Member = { id: string; display_name: string; initials_color?: string; relationship_label?: string | null; status: string; role?: string; capsule_count?: number };
type Invitation = { id: string; email: string; code: string; display_name?: string };

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

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [rel, setRel] = useState("");
  const [sending, setSending] = useState(false);

  const invite = async () => {
    if (!name.trim() || !email.trim()) return toast.show("Prénom et e-mail requis", "error");
    setSending(true);
    try {
      const res = await api.post<{ code: string }>("/circle/invitations", {
        display_name: name.trim(),
        email: email.trim(),
        relationship_label: rel.trim() || undefined,
      });
      toast.show(`Invitation envoyée · code ${res.code}`, "success");
      setName(""); setEmail(""); setRel(""); setShowForm(false);
      qc.invalidateQueries({ queryKey: ["members"] });
      qc.invalidateQueries({ queryKey: ["invitations"] });
      qc.invalidateQueries({ queryKey: ["circle"] });
    } catch (e: any) {
      toast.show(e?.message || "Envoi impossible", "error");
    } finally {
      setSending(false);
    }
  };

  const resend = async (inv: Invitation) => {
    try {
      await api.post(`/circle/invitations/${inv.id}/resend`);
      toast.show("Invitation renvoyée", "info");
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    }
  };

  const revoke = async (inv: Invitation) => {
    try {
      await api.del(`/circle/invitations/${inv.id}`);
      qc.invalidateQueries({ queryKey: ["members"] });
      qc.invalidateQueries({ queryKey: ["invitations"] });
      qc.invalidateQueries({ queryKey: ["circle"] });
      toast.show("Invitation annulée", "info");
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    }
  };

  const active = membersQ.data?.filter((m) => m.status === "active") ?? [];
  const pending = membersQ.data?.filter((m) => m.status === "pending") ?? [];

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Pressable onPress={() => router.back()} hitSlop={12} testID="members-back">
          <CaretLeft color={colors.onSurface} size={26} />
        </Pressable>
        <Title style={styles.headerTitle}>Membres</Title>
        <View style={{ width: 26 }} />
      </View>

      <KeyboardAwareScrollView
        contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + spacing.xxl }]}
        bottomOffset={20}
        showsVerticalScrollIndicator={false}
      >
        {membersQ.isLoading ? (
          <ActivityIndicator color={colors.brandSecondary} style={{ marginTop: spacing.xl }} />
        ) : (
          <>
            {active.map((m) => (
              <Card key={m.id} style={styles.memberCard} testID={`member-${m.id}`}>
                <Avatar name={m.display_name} color={m.initials_color} size={48} />
                <View style={styles.memberInfo}>
                  <Body style={styles.memberName}>{m.display_name}</Body>
                  <Label style={styles.memberSub}>
                    {(m.relationship_label || "Membre")}{m.role === "owner" ? " · créateur" : ""} · {m.capsule_count ?? 0} souvenir{(m.capsule_count ?? 0) > 1 ? "s" : ""}
                  </Label>
                </View>
              </Card>
            ))}

            {pending.length > 0 ? <Label style={styles.section}>EN ATTENTE</Label> : null}
            {pending.map((m) => {
              const inv = invitesQ.data?.find((i) => i.display_name === m.display_name);
              return (
                <Card key={m.id} style={styles.memberCard} testID={`pending-${m.id}`}>
                  <Avatar name={m.display_name} color={m.initials_color} size={48} />
                  <View style={styles.memberInfo}>
                    <Body style={styles.memberName}>{m.display_name}</Body>
                    <Label style={styles.memberSub}>Invitation en attente{inv ? ` · code ${inv.code}` : ""}</Label>
                  </View>
                  {isOwner && inv ? (
                    <View style={styles.pendingActions}>
                      <Pressable onPress={() => resend(inv)} hitSlop={8} testID={`resend-${m.id}`}>
                        <ArrowsClockwise color={colors.brandPrimary} size={22} />
                      </Pressable>
                      <Pressable onPress={() => revoke(inv)} hitSlop={8} testID={`revoke-${m.id}`}>
                        <XCircle color={colors.error} size={22} />
                      </Pressable>
                    </View>
                  ) : null}
                </Card>
              );
            })}

            {isOwner ? (
              showForm ? (
                <Card style={styles.form}>
                  <Label style={styles.section}>NOUVELLE INVITATION</Label>
                  <TextField label="PRÉNOM" testID="invite-name" value={name} onChangeText={setName} placeholder="Papy Jean" />
                  <TextField label="E-MAIL" testID="invite-email" value={email} onChangeText={setEmail} placeholder="jean@exemple.fr" autoCapitalize="none" keyboardType="email-address" />
                  <TextField label="LIEN DE FAMILLE (OPTIONNEL)" testID="invite-rel" value={rel} onChangeText={setRel} placeholder="Grand-père" />
                  <Button title="Envoyer l’invitation" testID="invite-send" loading={sending} onPress={invite} icon={<PaperPlaneTilt color={colors.onBrandPrimary} size={18} weight="fill" />} />
                  <Pressable onPress={() => setShowForm(false)} testID="invite-cancel" hitSlop={8}>
                    <Label style={styles.cancel}>Annuler</Label>
                  </Pressable>
                </Card>
              ) : (
                <Pressable style={styles.inviteBtn} testID="members-invite-open" onPress={() => setShowForm(true)}>
                  <UserPlus color={colors.brandPrimary} size={22} />
                  <Body style={styles.inviteText}>Inviter un proche</Body>
                </Pressable>
              )
            ) : null}
          </>
        )}
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.xl, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerTitle: { fontSize: 22 },
  content: { padding: spacing.xl, gap: spacing.md },
  memberCard: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  memberInfo: { flex: 1, gap: 2 },
  memberName: { fontSize: 16 },
  memberSub: { color: colors.muted },
  pendingActions: { flexDirection: "row", gap: spacing.md },
  section: { color: colors.brandSecondary, marginTop: spacing.sm },
  form: { gap: spacing.md },
  cancel: { textAlign: "center", color: colors.muted },
  inviteBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    borderWidth: 1.5,
    borderStyle: "dashed",
    borderColor: colors.brandTertiary,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  inviteText: { color: colors.brandPrimary, fontSize: 15 },
}));
