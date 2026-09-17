import { useEffect } from "react";
import { View } from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withTiming,
} from "react-native-reanimated";

import { useTheme } from "@/src/theme";

const BAR_COUNT = 7;
const IDLE_SCALE = 0.28;

function WaveBar({ index, active, color }: { index: number; active: boolean; color: string }) {
  const scale = useSharedValue(IDLE_SCALE);

  useEffect(() => {
    if (active) {
      scale.value = withDelay(
        index * 90,
        withRepeat(withTiming(1, { duration: 420, easing: Easing.inOut(Easing.ease) }), -1, true),
      );
    } else {
      scale.value = withTiming(IDLE_SCALE, { duration: 220 });
    }
  }, [active, index, scale]);

  const animatedStyle = useAnimatedStyle(() => ({ transform: [{ scaleY: scale.value }] }));

  return (
    <Animated.View
      style={[{ width: 6, height: 36, borderRadius: 3, backgroundColor: color }, animatedStyle]}
    />
  );
}

// Onde sonore animée : rassure la personne que sa voix est bien captée.
export function Waveform({ active }: { active: boolean }) {
  const { colors } = useTheme();
  const color = active ? colors.error : colors.borderStrong;
  return (
    <View
      testID="workshop-waveform"
      style={{ flexDirection: "row", alignItems: "center", gap: 6, height: 44 }}
    >
      {Array.from({ length: BAR_COUNT }).map((_, index) => (
        <WaveBar key={index} index={index} active={active} color={color} />
      ))}
    </View>
  );
}
