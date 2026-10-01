import { useState } from "react";
import { ActivityIndicator, Alert, Platform, Pressable, View } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useQueryClient } from "@tanstack/react-query";
import { Camera } from "phosphor-react-native";
import { Avatar } from "@/src/components/ui";
import { useToast } from "@/src/components/toast";
import { API_BASE, api, getToken, localFilePart } from "@/src/api/client";
import { useTheme } from "@/src/theme";

type Props = {
  memberId: string;
  name: string;
  color?: string;
  photo?: string | null;
  size?: number;
  editable: boolean;
  onChanged?: () => void;
};

// Avatar that opens "Galerie / Appareil photo / Retirer" when tapped, for members the viewer may edit.
export function AvatarPicker({ memberId, name, color, photo, size = 84, editable, onChanged }: Props) {
  const { colors } = useTheme();
  const toast = useToast();
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["members"] }),
      qc.invalidateQueries({ queryKey: ["circle"] }),
      qc.invalidateQueries({ queryKey: ["capsules"] }),
    ]);
    onChanged?.();
  };

  const upload = async (asset: ImagePicker.ImagePickerAsset) => {
    setBusy(true);
    try {
      const form = new FormData();
      if (Platform.OS === "web") {
        form.append("photo", await (await fetch(asset.uri)).blob(), "photo.jpg");
      } else {
        form.append("photo", localFilePart(asset.uri));
      }
      const res = await fetch(`${API_BASE}/circle/members/${memberId}/photo`, {
        method: "POST",
        headers: { Authorization: `Bearer ${await getToken()}` },
        body: form,
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(payload?.detail || "La photo n’a pas pu être enregistrée");
      }
      await refresh();
      toast.show("Photo de profil mise à jour", "success");
    } catch (e: any) {
      toast.show(e?.message || "La photo n’a pas pu être enregistrée", "error");
    } finally {
      setBusy(false);
    }
  };

  const pick = async (source: "library" | "camera") => {
    const perm = source === "camera"
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (perm.status !== "granted") {
      toast.show(source === "camera" ? "Autorisez l’appareil photo dans les réglages" : "Autorisez l’accès aux photos dans les réglages", "error");
      return;
    }
    const options: ImagePicker.ImagePickerOptions = { mediaTypes: ["images"], allowsEditing: true, aspect: [1, 1], quality: 0.7 };
    const res = source === "camera" ? await ImagePicker.launchCameraAsync(options) : await ImagePicker.launchImageLibraryAsync(options);
    if (!res.canceled && res.assets?.[0]) await upload(res.assets[0]);
  };

  const remove = async () => {
    setBusy(true);
    try {
      await api.del(`/circle/members/${memberId}/photo`);
      await refresh();
      toast.show("Photo retirée", "info");
    } catch (e: any) {
      toast.show(e?.message || "La photo n’a pas pu être retirée", "error");
    } finally {
      setBusy(false);
    }
  };

  const openMenu = () => {
    if (Platform.OS === "web") return pick("library");
    const buttons: { text: string; style?: "cancel" | "destructive"; onPress?: () => void }[] = [
      { text: "Choisir dans la galerie", onPress: () => pick("library") },
      { text: "Prendre une photo", onPress: () => pick("camera") },
    ];
    if (photo) buttons.push({ text: "Retirer la photo", style: "destructive", onPress: remove });
    buttons.push({ text: "Annuler", style: "cancel" });
    Alert.alert(`Photo de ${name}`, undefined, buttons);
  };

  const badge = Math.max(26, Math.round(size * 0.32));
  if (!editable) return <Avatar name={name} color={color} size={size} photo={photo} />;
  return (
    <Pressable
      onPress={openMenu}
      disabled={busy}
      testID={`avatar-picker-${memberId}`}
      accessibilityRole="button"
      accessibilityLabel={photo ? `Changer la photo de ${name}` : `Ajouter une photo pour ${name}`}
      hitSlop={6}
    >
      <Avatar name={name} color={color} size={size} photo={photo} />
      <View
        style={{
          position: "absolute", right: -2, bottom: -2, width: badge, height: badge, borderRadius: badge / 2,
          backgroundColor: colors.brandPrimary, borderWidth: 2, borderColor: colors.surface, alignItems: "center", justifyContent: "center",
        }}
      >
        {busy ? <ActivityIndicator size="small" color={colors.onBrandPrimary} /> : <Camera color={colors.onBrandPrimary} size={badge * 0.55} weight="fill" />}
      </View>
    </Pressable>
  );
}
