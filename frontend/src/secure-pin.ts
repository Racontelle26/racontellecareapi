import { Platform } from "react-native";

import { storage } from "./utils/storage";

let webPin: string | null = null;

function key(tenantId: string | null) {
  return `racontelle.professional-pin.${tenantId ?? "guest"}`;
}

export async function readProfessionalPin(tenantId: string | null) {
  if (Platform.OS === "web") return webPin;
  return storage.secureGet<string | null>(key(tenantId), null);
}

export async function writeProfessionalPin(tenantId: string | null, pin: string) {
  if (Platform.OS === "web") {
    webPin = pin;
    return true;
  }
  return storage.secureSet(key(tenantId), pin);
}