// Web storage (Metro picks index.ts on native).
// Helpers never throw: reads return `fallback`, writes return `false`.
// Values supported: string | number | boolean | null (JSON-serialized on disk).
// Usage: import { storage } from "@/src/utils/storage"; await storage.getItem(key, fallback);
// No Keychain on web — secure* helpers reuse AsyncStorage (no expo-secure-store).

import AsyncStorage from "@react-native-async-storage/async-storage";

import { AssertNoExtras, StorageBase, StorageItemValue } from "./storage-base";

export class Storage extends StorageBase {
  private secureMemory = new Map<string, StorageItemValue>();
  // General KV — backed by AsyncStorage (its built-in web shim uses IndexedDB).
  async getItem<Fallback extends StorageItemValue>(
    key: string,
    fallback: Fallback,
  ): Promise<Fallback | null> {
    try {
      const raw = await AsyncStorage.getItem(key);
      return this.retrieve(raw, fallback);
    } catch (e) {
      this.warn("getItem", key, e);
      return fallback;
    }
  }

  async setItem<Value extends StorageItemValue>(
    key: string,
    value: Value,
  ): Promise<boolean> {
    try {
      await AsyncStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (e) {
      this.warn("setItem", key, e);
      return false;
    }
  }

  async removeItem(key: string): Promise<boolean> {
    try {
      await AsyncStorage.removeItem(key);
      return true;
    } catch (e) {
      this.warn("removeItem", key, e);
      return false;
    }
  }

  // Browsers have no Keychain. Sensitive values stay in memory only; the
  // backend's HttpOnly refresh cookie restores the web session after reload.
  async secureGet<Fallback extends StorageItemValue>(
    key: string,
    fallback: Fallback,
  ): Promise<Fallback | null> {
    return (this.secureMemory.has(key) ? this.secureMemory.get(key) : fallback) as Fallback;
  }

  async secureSet<Value extends StorageItemValue>(
    key: string,
    value: Value,
  ): Promise<boolean> {
    this.secureMemory.set(key, value);
    return true;
  }

  async secureRemove(key: string): Promise<boolean> {
    this.secureMemory.delete(key);
    return true;
  }
}

export const storage = new Storage();

// Compile-time guard: any new method must be declared in storage-base.ts first.
// eslint-disable-next-line @typescript-eslint/no-unused-vars -- intentional compile-time-only assertion
type _NoExtras = AssertNoExtras<Exclude<keyof Storage, keyof StorageBase>>;
