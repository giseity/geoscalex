import { useEffect, useRef } from "react"
import { Geoman } from "@geoman-io/maplibre-geoman-free"
import * as maplibregl from "maplibre-gl"
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url"

import "maplibre-gl/dist/maplibre-gl.css"
import "@geoman-io/maplibre-geoman-free/dist/maplibre-geoman.css"

import type { Geometry } from "@/lib/api"
import { geometryPositions } from "@/lib/geometry"

maplibregl.setWorkerUrl(workerUrl)

const configuredStyle = import.meta.env.VITE_MAP_STYLE_URL as string | undefined
const blankStyle: maplibregl.StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "paper", type: "background", paint: { "background-color": "#f3f0e7" } }],
}

type MapGeometryEditorProps = {
  geometry?: Geometry
  referenceGeometry?: Geometry
  geometryType: "LineString" | "Polygon"
  onChange: (geometry: Geometry | undefined) => void
}

function fitGeometry(map: maplibregl.Map, geometry: Geometry) {
  const positions = geometryPositions(geometry)
  if (!positions.length) return
  const bounds = positions.reduce(
    (current, position) => current.extend(position),
    new maplibregl.LngLatBounds(positions[0], positions[0]),
  )
  map.fitBounds(bounds, { padding: 72, maxZoom: 15, duration: 0 })
}

export function MapGeometryEditor({ geometry, referenceGeometry, geometryType, onChange }: MapGeometryEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  useEffect(() => {
    if (!containerRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      center: [0, 0],
      zoom: 1,
      attributionControl: false,
      style: configuredStyle || blankStyle,
    })
    const resizeObserver = new ResizeObserver(() => map.resize())
    resizeObserver.observe(containerRef.current)
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right")
    let geoman: Geoman | undefined
    let disposed = false

    map.once("load", async () => {
      if (disposed) return
      if (referenceGeometry) {
        map.addSource("reference-geometry", {
          type: "geojson",
          data: { type: "Feature", properties: {}, geometry: referenceGeometry },
        })
        map.addLayer({
          id: "reference-fill",
          type: "fill",
          source: "reference-geometry",
          filter: ["==", ["geometry-type"], "Polygon"],
          paint: { "fill-color": "#00796f", "fill-opacity": 0.09 },
        })
        map.addLayer({
          id: "reference-line",
          type: "line",
          source: "reference-geometry",
          paint: { "line-color": "#00796f", "line-width": 3, "line-dasharray": [2, 2] },
        })
      }
      const canDraw = !geometry
      geoman = new Geoman(map, {
        settings: { controlsUiEnabledByDefault: false },
        controls: {
          draw: {
            line: { uiEnabled: canDraw && geometryType === "LineString" },
            polygon: { uiEnabled: canDraw && geometryType === "Polygon" },
          },
          edit: {
            drag: { uiEnabled: true },
            change: { uiEnabled: true },
            delete: { uiEnabled: true },
          },
          helper: {
            snapping: { uiEnabled: true },
            zoom_to_features: { uiEnabled: true },
          },
        },
      })
      await geoman.waitForGeomanLoaded()
      if (disposed) return

      const emit = () => {
        const first = geoman?.features.exportGeoJson().features[0]?.geometry
        if (first?.type === "LineString" || first?.type === "Polygon") {
          onChangeRef.current(first as Geometry)
        } else onChangeRef.current(undefined)
      }
      geoman.setGlobalEventsListener(emit)

      if (geometry) {
        await geoman.features.importGeoJson({ type: "Feature", properties: {}, geometry })
        await geoman.enableGlobalEditMode()
        window.requestAnimationFrame(() => {
          map.resize()
          window.requestAnimationFrame(() => fitGeometry(map, geometry))
        })
      } else {
        await geoman.enableDraw(geometryType === "Polygon" ? "polygon" : "line")
        if (referenceGeometry) {
          window.requestAnimationFrame(() => {
            map.resize()
            window.requestAnimationFrame(() => fitGeometry(map, referenceGeometry))
          })
        }
      }
    })

    return () => {
      disposed = true
      resizeObserver.disconnect()
      if (geoman) {
        void geoman.destroy({ removeSources: true }).catch(() => undefined).finally(() => map.remove())
      } else {
        map.remove()
      }
    }
  }, [geometry, geometryType, referenceGeometry])

  return (
    <div className="relative min-h-[430px] overflow-hidden rounded-xl border bg-[#f3f0e7]">
      <div className="min-h-[430px] w-full" ref={containerRef} />
      <div className="pointer-events-none absolute bottom-3 left-3 rounded-md bg-white/90 px-2.5 py-1.5 text-[11px] font-medium text-slate-600 shadow-sm">
        Offline canvas · MapLibre + Geoman
      </div>
    </div>
  )
}
