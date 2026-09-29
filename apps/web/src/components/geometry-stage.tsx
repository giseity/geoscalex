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
  mode: "swipe" | "overlay"
  swipe: number
  className?: string
}

export function GeometryStage({
  original,
  left,
  right,
  mode,
  swipe,
  className,
}: GeometryStageProps) {
  const clipId = useId().replaceAll(":", "")
  const projection = projectionFor([original, left, right])

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
      <div className="pointer-events-none absolute inset-x-4 top-4 flex justify-between text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700">
        <span className="rounded-full bg-white/85 px-3 py-1.5 shadow-sm">A · Douglas–Peucker</span>
        <span className="rounded-full bg-white/85 px-3 py-1.5 shadow-sm">B · Visvalingam–Whyatt</span>
      </div>
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
