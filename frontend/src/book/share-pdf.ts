import * as FileSystem from "expo-file-system/legacy";
import * as Print from "expo-print";

const MAX_PDF_BASE64_LENGTH = 40 * 1024 * 1024;

export async function preparePdfForSharing(html: string) {
  if (!FileSystem.cacheDirectory) {
    throw new Error("Le stockage temporaire est indisponible");
  }

  // Expo Go Android places expo-print files in a native cache that
  // expo-file-system cannot read. Base64 lets us write the PDF directly
  // inside the current experience's readable cache instead.
  const result = await Print.printToFileAsync({ html, base64: true });
  if (!result.base64) {
    throw new Error("La génération du PDF n’a produit aucun fichier");
  }
  if (result.base64.length > MAX_PDF_BASE64_LENGTH) {
    throw new Error("Le livre est trop volumineux pour être partagé sur ce téléphone");
  }

  const destinationUri = `${FileSystem.cacheDirectory}racontelle-livre-${Date.now()}.pdf`;
  await FileSystem.writeAsStringAsync(destinationUri, result.base64, {
    encoding: FileSystem.EncodingType.Base64,
  });
  const info = await FileSystem.getInfoAsync(destinationUri);
  if (!info.exists || !info.size) {
    throw new Error("Le fichier PDF généré est vide");
  }
  return destinationUri;
}