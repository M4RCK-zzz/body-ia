import { useMemo } from "react";
import type { PoseLandmark } from "@/types/pose";

/**
 * Vista ESTIMACIÓN VISUAL del esquema corporal a partir de landmarks del modelo.
 * No calcula ángulos, distancias ni mediciones: es una referencia visual.
 */

// Conexiones del esquema del cuerpo (MediaPipe Pose, 33 landmarks).
const POSE_CONNECTIONS: Array<[number, number]> = [
  [0, 1], [1, 2], [2, 3], [3, 7],
  [0, 9], [9, 10],
  [11, 12], [11, 13], [13, 15], [15, 21],
  [12, 14], [14, 16], [16, 22],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27], [27, 29], [29, 31],
  [24, 26], [26, 28], [28, 30], [30, 32],
  [11, 23], [12, 24],
];

interface Props {
  landmarks: PoseLandmark[] | null | undefined;
  visibilityThreshold?: number;
}

export function SkeletonPreview({ landmarks, visibilityThreshold = 0.5 }: Props) {
  const byIndex = useMemo(() => {
    const map = new Map<number, PoseLandmark>();
    for (const lm of landmarks ?? []) map.set(lm.index, lm);
    return map;
  }, [landmarks]);

  if (!landmarks || landmarks.length === 0) {
    return <p className="pose-skeleton__empty">Sin landmarks disponibles todavía.</p>;
  }

  const vbW = 100;
  const vbH = 120;

  // Landmarks ya son normalizados [0,1] relativos al fotograma.
  const pt = (lm: PoseLandmark) =>
    lm.x === null || lm.y === null ? null : { x: lm.x * vbW, y: lm.y * vbH };

  return (
    <svg
      viewBox={`0 0 ${vbW} ${vbH}`}
      className="pose-skeleton"
      role="img"
      aria-label="Esqueleto de estimación visual del cuerpo"
    >
      {POSE_CONNECTIONS.map(([a, b], idx) => {
        const la = byIndex.get(a);
        const lb = byIndex.get(b);
        if (!la || !lb) return null;
        if ((la.visibility ?? 0) < visibilityThreshold || (lb.visibility ?? 0) < visibilityThreshold) return null;
        const pa = pt(la);
        const pb = pt(lb);
        if (!pa || !pb) return null;
        return (
          <line
            key={`l-${a}-${b}-${idx}`}
            x1={pa.x}
            y1={pa.y}
            x2={pb.x}
            y2={pb.y}
            stroke="#7dd3fc"
            strokeWidth={0.8}
            strokeOpacity={0.9}
            strokeLinecap="round"
          />
        );
      })}
      {landmarks.map((lm) => {
        const p = pt(lm);
        if (!p) return null;
        const visible = (lm.visibility ?? 0) >= visibilityThreshold;
        if (!visible) return null;
        return (
          <circle
            key={`c-${lm.index}`}
            cx={p.x}
            cy={p.y}
            r={1.6}
            fill="#38bdf8"
            stroke="#0c4a6e"
            strokeWidth={0.4}
          />
        );
      })}
    </svg>
  );
}
