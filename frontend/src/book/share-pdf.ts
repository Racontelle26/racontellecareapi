import * as FileSystem from "expo-file-system/legacy";

export async function preparePdfForSharing(sourceUri: string) {
  if (!sourceUri?.startsWith("file://")) {
    throw new Error("Le fichier PDF généré est inaccessible");
  }
  if (!FileSystem.cacheDirectory) {
    throw new Error("Le stockage temporaire est indisponible");
  }
  const destinationUri = `${FileSystem.cacheDirectory}racontelle-livre-${Date.now()}.pdf`;
  await FileSystem.copyAsync({ from: sourceUri, to: destinationUri });
  const info = await FileSystem.getInfoAsync(destinationUri);
  if (!info.exists || !info.size) {
    throw new Error("La copie du PDF est vide");
  }
  return destinationUri;
}