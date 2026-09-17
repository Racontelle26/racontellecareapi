import { useState } from "react";
import { View, Pressable } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { X, Star } from "phosphor-react-native";
import { Body, Button, Label, TextField, Title } from "@/src/components/ui";
import { api } from "@/src/api/client";
import { useToast } from "@/src/components/toast";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

const CATEGORIES = [
  { key: "bug", label: "Un souci technique" },
  { key: "idea", label: "Une idée" },
  { key: "content", label: "Les questions" },
  { key: "other", label: "Autre" },
];

export default function Feedback() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const toast = useToast();
  const [category, setCategory] = useState("idea");
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [sending, setSending] = useState(false);

  const submit = async () => {
    if (!comment.trim()) return toast.show("Écrivez un petit mot", "error");
    setSending(true);
    try {
      await api.post("/feedback", { category, rating: rating || null, comment: comment.trim(), page_context: "app" });
      toast.show("Merci pour votre retour 💛", "success");
      router.back();
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    } finally {
      setSending(false);
    }
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top + spacing.md, paddingBottom: insets.bottom + spacing.lg }]}>
      <View style={styles.top}>
        <Pressable onPress={() => router.back()} hitSlop={12} testID="feedback-close">
          <X color={colors.onSurface} size={26} />
        </Pressable>
      </View>
      <KeyboardAwareScrollView contentContainerStyle={styles.content} bottomOffset={20} showsVerticalScrollIndicator={false}>
        <Title style={styles.title}>Votre avis compte</Title>
        <Body muted>Aidez-nous à améliorer Racontelle Family pendant la bêta.</Body>

        <Label style={styles.section}>DE QUOI S’AGIT-IL ?</Label>
        <View style={styles.cats}>
          {CATEGORIES.map((c) => {
            const active = category === c.key;
            return (
              <Pressable key={c.key} testID={`feedback-cat-${c.key}`} onPress={() => setCategory(c.key)} style={[styles.cat, active && styles.catActive]}>
                <Label style={[styles.catText, active && styles.catTextActive]}>{c.label}</Label>
              </Pressable>
            );
          })}
        </View>

        <Label style={styles.section}>VOTRE APPRÉCIATION</Label>
        <View style={styles.stars}>
          {[1, 2, 3, 4, 5].map((n) => (
            <Pressable key={n} testID={`feedback-star-${n}`} onPress={() => setRating(n)} hitSlop={6}>
              <Star color={colors.warning} size={34} weight={n <= rating ? "fill" : "regular"} />
            </Pressable>
          ))}
        </View>

        <TextField
          label="VOTRE MESSAGE"
          testID="feedback-comment"
          value={comment}
          onChangeText={setComment}
          placeholder="Ce qui vous a plu, ce qui pourrait être mieux…"
          multiline
          style={styles.textArea}
        />
        <Button title="Envoyer" testID="feedback-submit" loading={sending} onPress={submit} />
      </KeyboardAwareScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  container: { flex: 1, backgroundColor: colors.surface, paddingHorizontal: spacing.xl },
  top: { flexDirection: "row", marginBottom: spacing.sm },
  content: { gap: spacing.md, paddingBottom: spacing.xxl },
  title: { fontSize: 28 },
  section: { color: colors.brandSecondary, marginTop: spacing.md },
  cats: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  cat: { paddingHorizontal: spacing.lg, paddingVertical: 10, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  catActive: { backgroundColor: colors.brandTertiary, borderColor: colors.brand },
  catText: { color: colors.onSurfaceTertiary },
  catTextActive: { color: colors.onBrandTertiary },
  stars: { flexDirection: "row", gap: spacing.md },
  textArea: { minHeight: 120, textAlignVertical: "top", paddingTop: spacing.md },
}));
