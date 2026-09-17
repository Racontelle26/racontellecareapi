import { Platform } from "react-native";

// iOS 26+ gets native liquid-glass tabs; everything else uses the JS Tabs.
export const usesNativeTabs =
  Platform.OS === "ios" && parseInt(String(Platform.Version), 10) >= 26;
