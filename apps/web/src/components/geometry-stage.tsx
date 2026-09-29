import { useEffect, useId, useRef, useState, type PointerEvent as ReactPointerEvent } from "react"
import { LocateFixed, Minus, Plus } from "lucide-react"

import type { Geometry } from "@/lib/api"
import { geometryPaths, projectionFor } from "@/lib/geometry"
import { cn } from "@/lib/utils"

export const ORIGINAL_COLOR = "#66736f"
export const CANDIDATE_A_COLOR = "#d85f36"
export const CANDIDATE_B_COLOR = "#2563a8"

const VIEWBOX_WIDTH = 1000
const VIEWBOX_HEIGHT = 620
const MIN_ZOOM = 1
const MAX_ZOOM = 8

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
  onSwipeChange?: (value: number) => void
  className?: string
  comparisonLabels?: boolean
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

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value))
}

export function GeometryStage({
  original,
  left,
  right,
  context = [],
  mode,
  swipe,
  onSwipeChange,
  className,
}: GeometryStageProps) {
  const clipId = useId().replaceAll(":", "")
  const stageRef = useRef<HTMLDivElement>(null)
  const panOrigin = useRef<{ x: number; y: number } | null>(null)
  const zoomRef = useRef(1)
  const viewportRef = useRef({ width: VIEWBOX_WIDTH, height: VIEWBOX_HEIGHT })
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [panning, setPanning] = useState(false)
  const [viewport, setViewport] = useState(viewportRef.current)
  const projection = projectionFor(
    [original, left, right, ...context.map((item) => item.geometry)],
    { ...viewport, padding: Math.min(64, viewport.width * 0.08) },
  )

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

  function viewPoint(clientX: number, clientY: number) {
    const bounds = stageRef.current?.getBoundingClientRect()
    const currentViewport = viewportRef.current
    if (!bounds) return { x: currentViewport.width / 2, y: currentViewport.height / 2 }
    return {
      x: ((clientX - bounds.left) / bounds.width) * currentViewport.width,
      y: ((clientY - bounds.top) / bounds.height) * currentViewport.height,
    }
  }

  function zoomAt(nextZoom: number | ((current: number) => number), point?: { x: number; y: number }) {
    const currentViewport = viewportRef.current
    const zoomPoint = point ?? { x: currentViewport.width / 2, y: currentViewport.height / 2 }
    const currentZoom = zoomRef.current
    const requestedZoom = typeof nextZoom === "function" ? nextZoom(currentZoom) : nextZoom
    const clampedZoom = clamp(requestedZoom, MIN_ZOOM, MAX_ZOOM)
    if (clampedZoom === currentZoom) return
    const ratio = clampedZoom / currentZoom
    zoomRef.current = clampedZoom
    setPan((current) => ({
      x: zoomPoint.x - (zoomPoint.x - current.x) * ratio,
      y: zoomPoint.y - (zoomPoint.y - current.y) * ratio,
    }))
    setZoom(clampedZoom)
  }

  function resetViewport() {
    zoomRef.current = 1
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }

  useEffect(() => {
    const stage = stageRef.current
    if (!stage || typeof ResizeObserver === "undefined") return
    const updateViewport = () => {
      const bounds = stage.getBoundingClientRect()
      if (!bounds.width || !bounds.height) return
      const next = { width: VIEWBOX_HEIGHT * (bounds.width / bounds.height), height: VIEWBOX_HEIGHT }
      viewportRef.current = next
      setViewport((current) => Math.abs(current.width - next.width) < 0.5 ? current : next)
    }
    updateViewport()
    const observer = new ResizeObserver(updateViewport)
    observer.observe(stage)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const stage = stageRef.current
    if (!stage) return
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault()
      const factor = event.deltaY < 0 ? 1.18 : 1 / 1.18
      zoomAt((current) => current * factor, viewPoint(event.clientX, event.clientY))
    }
    stage.addEventListener("wheel", handleWheel, { passive: false })
    return () => stage.removeEventListener("wheel", handleWheel)
  }, [])

  function startPan(event: ReactPointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return
    event.currentTarget.setPointerCapture(event.pointerId)
    panOrigin.current = viewPoint(event.clientX, event.clientY)
    setPanning(true)
  }

  function movePan(event: ReactPointerEvent<SVGSVGElement>) {
    if (!panOrigin.current || !panning) return
    const point = viewPoint(event.clientX, event.clientY)
    const deltaX = point.x - panOrigin.current.x
    const deltaY = point.y - panOrigin.current.y
    panOrigin.current = point
    setPan((current) => ({ x: current.x + deltaX, y: current.y + deltaY }))
  }

  function stopPan() {
    panOrigin.current = null
    setPanning(false)
  }

  function updateSwipe(clientX: number) {
    const bounds = stageRef.current?.getBoundingClientRect()
    if (!bounds || !onSwipeChange) return
    onSwipeChange(clamp(((clientX - bounds.left) / bounds.width) * 100, 0, 100))
  }

  const transform = `translate(${pan.x} ${pan.y}) scale(${zoom})`

  return (
    <div
      className={cn(
        "geometry-stage relative min-h-80 touch-none overflow-hidden rounded-xl border bg-[#f3f0e7] shadow-inner",
        className,
      )}
      data-testid="geometry-stage"
      ref={stageRef}
    >
      <svg
        aria-label="Geometry comparison"
        className={cn("absolute inset-0 h-full w-full", panning ? "cursor-grabbing" : "cursor-grab")}
        onDoubleClick={resetViewport}
        onPointerCancel={stopPan}
        onPointerDown={startPan}
        onPointerMove={movePan}
        onPointerUp={stopPan}
        viewBox={`0 0 ${viewport.width} ${viewport.height}`}
      >
        <defs>
          <pattern id={`${clipId}-grid`} width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#d9d5ca" strokeWidth="1" />
          </pattern>
          <clipPath id={`${clipId}-left`}>
            <rect height={viewport.height} width={(swipe / 100) * viewport.width} x="0" y="0" />
          </clipPath>
        </defs>
        <rect fill={`url(#${clipId}-grid)`} height={viewport.height} width={viewport.width} />
        <g transform={transform}>
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
          <g opacity="0.48">{layer(original, ORIGINAL_COLOR, true)}</g>
        </g>
        {mode === "overlay" ? (
          <g transform={transform}>
            <g>{layer(left, CANDIDATE_A_COLOR)}</g>
            <g>{layer(right, CANDIDATE_B_COLOR)}</g>
          </g>
        ) : (
          <>
            <g transform={transform}>{layer(right, CANDIDATE_B_COLOR)}</g>
            <g clipPath={`url(#${clipId}-left)`}>
              <g transform={transform}>{layer(left, CANDIDATE_A_COLOR)}</g>
            </g>
          </>
        )}
      </svg>

      <div className="absolute right-3 top-3 z-30 flex items-center gap-1 rounded-lg border bg-background/92 p-1 shadow-sm backdrop-blur">
        <button aria-label="Zoom out" className="grid size-8 place-items-center rounded-md text-foreground hover:bg-muted disabled:opacity-40" disabled={zoom <= MIN_ZOOM} onClick={() => zoomAt((current) => current / 1.35)} type="button"><Minus className="size-4" /></button>
        <span className="min-w-12 text-center text-[11px] font-semibold tabular-nums text-muted-foreground">{Math.round(zoom * 100)}%</span>
        <button aria-label="Zoom in" className="grid size-8 place-items-center rounded-md text-foreground hover:bg-muted disabled:opacity-40" disabled={zoom >= MAX_ZOOM} onClick={() => zoomAt((current) => current * 1.35)} type="button"><Plus className="size-4" /></button>
        <button aria-label="Fit geometry" className="grid size-8 place-items-center rounded-md text-foreground hover:bg-muted" onClick={resetViewport} title="Fit geometry" type="button"><LocateFixed className="size-4" /></button>
      </div>

      {mode === "swipe" && onSwipeChange && (
        <div
          aria-label="Comparison divider"
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={Math.round(swipe)}
          className="group absolute inset-y-0 z-20 w-10 -translate-x-1/2 cursor-col-resize touch-none focus:outline-none"
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft") onSwipeChange(clamp(swipe - (event.shiftKey ? 10 : 2), 0, 100))
            if (event.key === "ArrowRight") onSwipeChange(clamp(swipe + (event.shiftKey ? 10 : 2), 0, 100))
            if (event.key === "Home") onSwipeChange(0)
            if (event.key === "End") onSwipeChange(100)
          }}
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId)
            updateSwipe(event.clientX)
          }}
          onPointerMove={(event) => {
            if (event.currentTarget.hasPointerCapture(event.pointerId)) updateSwipe(event.clientX)
          }}
          role="slider"
          style={{ left: `${swipe}%` }}
          tabIndex={0}
        >
          <span className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 bg-slate-800 shadow-[0_0_0_1px_rgba(255,255,255,0.55)] transition group-focus:w-1" />
          <span className="absolute left-1/2 top-1/2 grid h-12 w-7 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-2 border-white bg-slate-800 text-white shadow-lg transition-transform group-hover:scale-105 group-focus:scale-105">
            <span className="flex gap-1"><i className="h-3 w-px bg-white/75" /><i className="h-3 w-px bg-white/75" /></span>
          </span>
        </div>
      )}
      <div className="pointer-events-none absolute bottom-3 left-3 rounded-md bg-background/80 px-2 py-1 text-[10px] font-medium text-muted-foreground shadow-sm backdrop-blur">
        Scroll to zoom · drag to pan · double-click to fit
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
