import React, { useMemo } from "react";
import { View } from "react-native";
import Svg, { Circle, Defs, Ellipse, G, LinearGradient, Path, Stop } from "react-native-svg";
import { useTheme } from "@/src/theme";

type Props = {
  count: number;
  level: number;
  maxLevel: number;
  size?: number;
};

/**
 * Symbolic "arbre des souvenirs" — grows with the number of saved memories.
 * At count 0 it is a bare sapling; each recorded memory adds foliage and blossoms.
 */
export function GrowingTree({ count, level, maxLevel, size = 240 }: Props) {
  const { colors } = useTheme();
  const w = size;
  const h = size * 1.15;
  const cx = w / 2;
  const groundY = h * 0.9;

  const growth = Math.min(1, level / maxLevel); // 0..1
  const canopyR = 26 + growth * (w * 0.36);
  const canopyCy = groundY - (70 + growth * (h * 0.34));
  const trunkTop = canopyCy + canopyR * 0.5;
  const trunkW = 8 + growth * 12;

  // Foliage clusters (sage greens) — more clusters as the tree grows.
  const clusters = useMemo(() => {
    const n = Math.min(7, 2 + level);
    const arr: { x: number; y: number; r: number; c: string }[] = [];
    const greens = [colors.brandSecondary, "#8AA487", "#6E8A6B"];
    for (let i = 0; i < n; i++) {
      const angle = (i / n) * Math.PI * 2 + 0.6;
      const rr = canopyR * (0.55 + 0.35 * ((i % 3) / 2));
      arr.push({
        x: cx + Math.cos(angle) * canopyR * 0.5,
        y: canopyCy + Math.sin(angle) * canopyR * 0.42,
        r: rr,
        c: greens[i % greens.length],
      });
    }
    arr.push({ x: cx, y: canopyCy, r: canopyR * 0.85, c: greens[0] });
    return arr;
  }, [canopyR, canopyCy, cx, level, colors.brandSecondary]);

  // Dusty-rose blossoms — one per memory, capped.
  const blossoms = useMemo(() => {
    const n = Math.min(count, 28);
    const arr: { x: number; y: number; r: number }[] = [];
    for (let i = 0; i < n; i++) {
      const angle = i * 2.399963; // golden angle
      const rad = canopyR * 0.85 * Math.sqrt((i + 1) / (n + 1));
      arr.push({
        x: cx + Math.cos(angle) * rad,
        y: canopyCy + Math.sin(angle) * rad * 0.9,
        r: 4.5 + (i % 3),
      });
    }
    return arr;
  }, [count, canopyR, canopyCy, cx]);

  return (
    <View accessibilityLabel={`Arbre des souvenirs, ${count} souvenirs`}>
      <Svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
        <Defs>
          <LinearGradient id="trunk" x1="0" y1="0" x2="1" y2="0">
            <Stop offset="0" stopColor="#9C7A5E" />
            <Stop offset="1" stopColor="#7A5C43" />
          </LinearGradient>
        </Defs>

        {/* ground */}
        <Ellipse cx={cx} cy={groundY + 6} rx={w * 0.34} ry={12} fill={colors.surfaceTertiary} />

        {/* trunk */}
        <Path
          d={`M ${cx - trunkW / 2} ${groundY}
              C ${cx - trunkW / 2 - 4} ${(groundY + trunkTop) / 2}, ${cx - trunkW / 2} ${trunkTop + 10}, ${cx - trunkW / 3} ${trunkTop}
              L ${cx + trunkW / 3} ${trunkTop}
              C ${cx + trunkW / 2} ${trunkTop + 10}, ${cx + trunkW / 2 + 4} ${(groundY + trunkTop) / 2}, ${cx + trunkW / 2} ${groundY}
              Z`}
          fill="url(#trunk)"
        />

        {/* a couple of branches for grown trees */}
        {level >= 3 ? (
          <G stroke="#8A6A4E" strokeWidth={trunkW * 0.4} strokeLinecap="round">
            <Path d={`M ${cx} ${trunkTop + 24} L ${cx - canopyR * 0.4} ${canopyCy + canopyR * 0.3}`} />
            <Path d={`M ${cx} ${trunkTop + 34} L ${cx + canopyR * 0.4} ${canopyCy + canopyR * 0.35}`} />
          </G>
        ) : null}

        {/* foliage */}
        {level === 0 ? (
          // sapling: two small leaves
          <G>
            <Ellipse cx={cx - 10} cy={trunkTop} rx={16} ry={9} fill={colors.brandSecondary} transform={`rotate(-30 ${cx - 10} ${trunkTop})`} />
            <Ellipse cx={cx + 10} cy={trunkTop} rx={16} ry={9} fill="#8AA487" transform={`rotate(30 ${cx + 10} ${trunkTop})`} />
          </G>
        ) : (
          clusters.map((c, i) => <Circle key={`c${i}`} cx={c.x} cy={c.y} r={c.r} fill={c.c} opacity={0.92} />)
        )}

        {/* blossoms */}
        {blossoms.map((b, i) => (
          <G key={`b${i}`}>
            <Circle cx={b.x} cy={b.y} r={b.r} fill={colors.brand} />
            <Circle cx={b.x} cy={b.y} r={b.r * 0.4} fill={colors.brandTertiary} />
          </G>
        ))}
      </Svg>
    </View>
  );
}
