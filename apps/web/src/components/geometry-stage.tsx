import { useId } from "react"

import type { Geometry } from "@/lib/api"
import { geometryPaths, projectionFor } from "@/lib/geometry"
import { cn } from "@/lib/utils"

type GeometryLayerProps = {
  geometry?: Geometry
  color: string
  className?: string
  dotted?: boolean
}

function GeometryLayer({ geometry, color, className, dotted }: GeometryLayerProps) {
  if (!geometry) return null
  const projection = projectionFor([geometry])
  return (
    <g className={className}>
      {geometryPaths(geometry, projection).map((path, index) => (
        <path
          key={`${path}-${index}`}
          d={path}
          fill={geometry.type === "Polygon" ? color : "none"}
          fillOpacity={geometry.type === "Polygon" ? 0.09 : 0}
          fillRule="evenodd"
          stroke={color}
          strokeDasharray={dotted ? "9 9" : undefined}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={geometry.type === "Polygon" ? 4 : 5}
          vectorEffect="non-scaling-stroke"
        />
      ))}
    </g>
  )
}

type GeometryStageProps = {
  original: Geometry
  left?: Geometry
  right?: Geometry
  context?: ContextGeometry[]
  mode: "swipe" | "overlay"
  swipe: number
  className?: string
  comparisonLabels?: boolean
  leftLabel?: string
  rightLabel?: string
}

export type ContextGeometry = {
  geometry: Geometry
  role: "sibling" | "parent" | "child" | "background" | "obstacle"
  importance: number
  style?: Record<string, unknown>
}

const roleColors: Record<ContextGeometry["role"], string> = {
  sibling: "#6f8f88",
  parent: "#76578f",
  child: "#5084a5",
  background: "#9a9b94",
  obstacle: "#b45f48",
}

export function GeometryStage({
  original,
  left,
  right,
  context = [],
  mode,
  swipe,
  className,
  comparisonLabels = true,
  leftLabel = "Candidate A",
  rightLabel = "Candidate B",
}: GeometryStageProps) {
  const clipId = useId().replaceAll(":", "")
  const projection = projectionFor([original, left, right, ...context.map((item) => item.geometry)])

  const layer = (geometry: Geometry | undefined, color: string, dotted = false) => {
    if (!geometry) return null
    return geometryPaths(geometry, projection).map((path, index) => (
      <path
        key={`${color}-${index}`}
        d={path}
        fill={geometry.type === "Polygon" ? color : "none"}
        fillOpacity={geometry.type === "Polygon" ? 0.1 : 0}
        fillRule="evenodd"
        stroke={color}
        strokeDasharray={dotted ? "10 10" : undefined}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={geometry.type === "Polygon" ? 4 : 5}
        vectorEffect="non-scaling-stroke"
      />
    ))
  }

  return (
    <div
      className={cn(
        "geometry-stage relative min-h-80 overflow-hidden rounded-xl border bg-[#f3f0e7] shadow-inner",
        className,
      )}
      data-testid="geometry-stage"
    >
      <svg aria-label="Geometry comparison" className="absolute inset-0 h-full w-full" viewBox="0 0 1000 620">
        <defs>
          <pattern id={`${clipId}-grid`} width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#d9d5ca" strokeWidth="1" />
          </pattern>
          <clipPath id={`${clipId}-left`}>
            <rect height="620" width={swipe * 10} x="0" y="0" />
          </clipPath>
        </defs>
        <rect fill={`url(#${clipId}-grid)`} height="620" width="1000" />
        <g>
          {context.map((item, contextIndex) => {
            const configuredColor = item.style?.color
            const color = typeof configuredColor === "string" ? configuredColor : roleColors[item.role]
            return geometryPaths(item.geometry, projection).map((path, pathIndex) => (
              <path
                d={path}
                fill={item.geometry.type === "Polygon" ? color : "none"}
                fillOpacity={item.geometry.type === "Polygon" ? 0.06 + item.importance * 0.08 : 0}
                fillRule="evenodd"
                key={`${contextIndex}-${pathIndex}`}
                opacity={0.35 + item.importance * 0.5}
                stroke={color}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5 + item.importance * 2.5}
                vectorEffect="non-scaling-stroke"
              />
            ))
          })}
        </g>
        <g opacity="0.45">{layer(original, "#59635f", true)}</g>
        {mode === "overlay" ? (
          <>
            <g>{layer(left, "#db5e37")}</g>
            <g>{layer(right, "#007f75")}</g>
          </>
        ) : (
          <>
            <g>{layer(right, "#007f75")}</g>
            <g clipPath={`url(#${clipId}-left)`}>{layer(left, "#db5e37")}</g>
            <line
              stroke="#26322e"
              strokeWidth="3"
              vectorEffect="non-scaling-stroke"
              x1={swipe * 10}
              x2={swipe * 10}
              y1="0"
              y2="620"
            />
            <circle cx={swipe * 10} cy="310" fill="#26322e" r="18" />
            <path
              d={`M${swipe * 10 - 7},310 l6,-6 v12 z M${swipe * 10 + 7},310 l-6,-6 v12 z`}
              fill="white"
            />
          </>
        )}
      </svg>
      {comparisonLabels && (
        <div className="pointer-events-none absolute inset-x-4 top-4 flex justify-between text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700">
          <span className="rounded-full bg-white/85 px-3 py-1.5 shadow-sm">A · {leftLabel}</span>
          <span className="rounded-full bg-white/85 px-3 py-1.5 shadow-sm">B · {rightLabel}</span>
        </div>
      )}
    </div>
  )
}

export function GeometryThumbnail({ geometry }: { geometry: Geometry }) {
  return (
    <svg aria-hidden className="h-9 w-14 rounded-md bg-[#efede6] p-1" viewBox="0 0 1000 620">
      <GeometryLayer color="#3d6d63" geometry={geometry} />
    </svg>
  )
}
