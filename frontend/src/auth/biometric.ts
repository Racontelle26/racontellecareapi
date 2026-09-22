import { Platform } from "react-native";
import * as LocalAuthentication from "expo-local-authentication";
import { storage } from "@/src/utils/storage";

const BIOMETRIC_ENABLED_KEY = "racontelle_fingerprint_enabled";

export type FingerprintAvailability = {
  available: boolean;
  hasHardware: boolean;
  enrolled: boolean;
};

export async function getFingerprintAvailability(): Promise<FingerprintAvailability> {
  if (Platform.OS === "web") return { available: false, hasHardware: false, enrolled: false };
  try {
    const [hasHardware, enrolled, types] = await Promise.all([
      LocalAuthentication.hasHardwareAsync(),
      LocalAuthentication.isEnrolledAsync(),
      LocalAuthentication.supportedAuthenticationTypesAsync(),
    ]);
    const hasFingerprint = types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT);
    return { available: hasHardware && enrolled && hasFingerprint, hasHardware, enrolled };
  } catch {
    return { available: false, hasHardware: false, enrolled: false };
  }
}

export async function getFingerprintEnabled() {
  if (Platform.OS === "web") return false;
  return Boolean(await storage.getItem(BIOMETRIC_ENABLED_KEY, false as boolean));
}

export async function saveFingerprintEnabled(enabled: boolean) {
  if (Platform.OS === "web") return false;
  return storage.setItem(BIOMETRIC_ENABLED_KEY, enabled);
}

export async function authenticateFingerprint(pinPrompt = false) {
  if (Platform.OS === "web") return { success: false, error: "not_available" } as const;
  try {
    return await LocalAuthentication.authenticateAsync({
      promptMessage: pinPrompt ? "Déverrouiller Racontelle" : "Posez votre doigt pour ouvrir Racontelle",
      promptDescription: pinPrompt ? "Utilisez votre empreinte ou le code PIN du téléphone" : "Empreinte digitale requise",
      cancelLabel: "Annuler",
      fallbackLabel: "Utiliser le code du téléphone",
      disableDeviceFallback: false,
      biometricsSecurityLevel: "strong",
      requireConfirmation: true,
    });
  } catch {
    return { success: false, error: "not_available" } as const;
  }
}