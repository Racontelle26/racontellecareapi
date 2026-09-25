import { useMemo, useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";

import type { CapsuleActions } from "../components/capsule-row";
import { CapsuleRow } from "../components/capsule-row";
import type { Capsule, Resident } from "../types";
import { Icon, residentLabel } from "../ui/primitives";
import type { ScreenProps } from "../ui/types";

/** "all", "unclassified" (rubrique « À classer ») ou l'id d'un résident. */
export type LibraryFilter = string;

type Props = ScreenProps & {
  residents: Resident[];
  capsules: Capsule[];
  filter: LibraryFilter;
  busyCapsuleId: string | null;
  playingCapsuleId: string | null;
  speakingCapsuleId: string | null;
  capsuleActions: (capsule: Capsule) => CapsuleActions;
  onFilter: (filter: LibraryFilter) => void;
  onBack: () => void;
};

export function LibraryScreen(props: Props) {
  const { styles, colors, insets, residents, capsules, filter } = props;
  const [query, setQuery] = useState("");
  const [newestFirst, setNewestFirst] = useState(true);
  const unclassifiedCount = capsules.filter((capsule) => !capsule.resident_id).length;

  const visible = useMemo(() => {
    let list = filter === "unclassified"
      ? capsules.filter((capsule) => !capsule.resident_id)
      : filter === "all" ? capsules : capsules.filter((capsule) => capsule.resident_id === filter);
    const text = query.trim().toLowerCase();
    if (text) {
      list = list.filter((capsule) => {
        const name = residents.find((resident) => resident.id === capsule.resident_id)?.display_name ?? "";
        return [capsule.title, capsule.transcription, capsule.theme, name].some((field) => field?.toLowerCase().includes(text));
      });
    }
    return [...list].sort((a, b) => (newestFirst ? b.recorded_at.localeCompare(a.recorded_at) : a.recorded_at.localeCompare(b.recorded_at)));
  }, [capsules, filter, newestFirst, query, residents]);

  const chip = (id: LibraryFilter, label: string, testID: string) => <Pressable testID={testID} key={id} accessibilityRole="button" accessibilityState={{ selected: filter === id }} onPress={() => props.onFilter(id)} style={[styles.filter, filter === id && styles.filterActive]}>
    <Text style={[styles.filterText, filter === id && styles.filterTextActive]}>{label}</Text>
  </Pressable>;

  return <ScrollView testID={filter === "unclassified" ? "to-classify-screen" : "archive-screen"} keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.screen, { paddingTop: insets.top + 18, paddingBottom: insets.bottom + 32 }]}>
    <View style={styles.header}>
      <Pressable testID="archive-back" accessibilityRole="button" accessibilityLabel="Retour" onPress={props.onBack} style={styles.backButton}><Icon name="arrow-back" color={colors.onSurface} /></Pressable>
      <Text style={styles.eyebrow}>Bibliothèque vocale</Text>
      <View style={{ width: 48 }} />
    </View>
    <View>
      <Text style={styles.title}>{filter === "unclassified" ? "À classer" : "Les souvenirs"}</Text>
      <Text style={styles.body}>{filter === "unclassified" ? "Écoutez chaque souvenir spontané, puis choisissez la personne qui raconte. Il gardera sa date d’origine." : "Les souvenirs restent disponibles sur cet appareil, même sans réseau."}</Text>
    </View>
    <TextInput testID="archive-search" value={query} onChangeText={setQuery} placeholder="Rechercher un mot, un thème, un prénom…" placeholderTextColor={colors.muted} style={styles.input} returnKeyType="search" autoCorrect={false} />
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.archiveFilter}>
      {chip("all", "Tous", "archive-filter-all")}
      {chip("unclassified", `À classer (${unclassifiedCount})`, "archive-filter-unclassified")}
      {residents.map((resident) => chip(resident.id, residentLabel(resident), `archive-filter-${resident.id}`))}
    </ScrollView>
    <View style={styles.sectionHeader}>
      <Text style={styles.small}>{visible.length} souvenir{visible.length > 1 ? "s" : ""}</Text>
      <Pressable testID="archive-sort" accessibilityRole="button" onPress={() => setNewestFirst((value) => !value)} style={styles.textButton}><Text style={styles.textButtonLabel}>{newestFirst ? "Plus récents d’abord" : "Plus anciens d’abord"}</Text></Pressable>
    </View>
    {visible.length ? visible.map((capsule) => <CapsuleRow key={capsule.id} styles={styles} colors={colors} capsule={capsule} resident={residents.find((resident) => resident.id === capsule.resident_id)} busy={props.busyCapsuleId === capsule.id} playing={props.playingCapsuleId === capsule.id} speaking={props.speakingCapsuleId === `t-${capsule.id}`} actions={props.capsuleActions(capsule)} />)
      : <View style={styles.empty}>
        <Icon name={filter === "unclassified" ? "checkmark-done-outline" : "albums-outline"} color={colors.brandPrimary} size={30} />
        <Text style={styles.heading}>{query.trim() ? "Aucun souvenir trouvé" : filter === "unclassified" ? "Tout est classé" : "La bibliothèque est vide"}</Text>
        <Text style={[styles.body, { textAlign: "center" }]}>{query.trim() ? `Aucun souvenir ne contient « ${query.trim()} ».` : filter === "unclassified" ? "Les souvenirs du mode spontané apparaîtront ici." : "Les souvenirs sauvegardés pendant l’atelier apparaîtront ici."}</Text>
      </View>}
  </ScrollView>;
}
