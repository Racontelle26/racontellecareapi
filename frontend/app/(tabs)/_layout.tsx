import React from "react";
import { Platform, View, ActivityIndicator } from "react-native";
import { Tabs } from "expo-router";
import { House, MicrophoneStage, BookOpen, User } from "phosphor-react-native";
import { usesNativeTabs } from "@/src/navigation";
import { useAuth } from "@/src/auth/auth-context";
import { fonts, useTheme } from "@/src/theme";

export default function TabsLayout() {
  const { colors } = useTheme();
  const { user, hasCircle } = useAuth();

  if (!user || !hasCircle) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.brandPrimary} size="large" />
      </View>
    );
  }

  if (usesNativeTabs) {
    const { NativeTabs } = require("expo-router/unstable-native-tabs");
    return (
      <NativeTabs>
        <NativeTabs.Trigger name="index">
          <NativeTabs.Trigger.Icon sf="house.fill" />
          <NativeTabs.Trigger.Label>Accueil</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="questions">
          <NativeTabs.Trigger.Icon sf="mic.fill" />
          <NativeTabs.Trigger.Label>Raconter</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="album">
          <NativeTabs.Trigger.Icon sf="book.fill" />
          <NativeTabs.Trigger.Label>Album</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="profile">
          <NativeTabs.Trigger.Icon sf="person.fill" />
          <NativeTabs.Trigger.Label>Profil</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
      </NativeTabs>
    );
  }

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.brandPrimary,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          ...(Platform.OS === "web" ? { height: 64 } : {}),
        },
        tabBarItemStyle: { alignSelf: "center" },
        tabBarLabelStyle: { fontFamily: fonts.bodyMedium, fontSize: 11 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Accueil",
          tabBarIcon: ({ color, focused }) => <House color={color} size={24} weight={focused ? "fill" : "regular"} />,
        }}
      />
      <Tabs.Screen
        name="questions"
        options={{
          title: "Raconter",
          tabBarIcon: ({ color, focused }) => <MicrophoneStage color={color} size={24} weight={focused ? "fill" : "regular"} />,
        }}
      />
      <Tabs.Screen
        name="album"
        options={{
          title: "Album",
          tabBarIcon: ({ color, focused }) => <BookOpen color={color} size={24} weight={focused ? "fill" : "regular"} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profil",
          tabBarIcon: ({ color, focused }) => <User color={color} size={24} weight={focused ? "fill" : "regular"} />,
        }}
      />
    </Tabs>
  );
}
