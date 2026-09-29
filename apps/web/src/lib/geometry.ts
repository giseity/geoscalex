import type { Geometry, Position } from "./api"

export type Projection = {
  point: (position: Position) => Position
  inverse: (position: Position) => Position
}

const WIDTH = 1000
const HEIGHT = 620
const PADDING = 64

export function geometryPositions(geometry?: Geometry): Position[] {
  if (!geometry) return []
  if (geometry.type === "LineString") return geometry.coordinates
  return geometry.coordinates.flat()
}

export function vertexCount(geometry?: Geometry): number {
  if (!geometry) return 0
  if (geometry.type === "LineString") return geometry.coordinates.length
  return geometry.coordinates.reduce((count, ring) => count + Math.max(0, ring.length - 1), 0)
}

export function projectionFor(geometries: Array<Geometry | undefined>): Projection {
  const positions = geometries.flatMap(geometryPositions)
  if (!positions.length) {
    return {
      point: ([x, y]) => [PADDING + (x / 100) * (WIDTH - PADDING * 2), HEIGHT - PADDING - (y / 100) * (HEIGHT - PADDING * 2)],
      inverse: ([x, y]) => [((x - PADDING) / (WIDTH - PADDING * 2)) * 100, ((HEIGHT - PADDING - y) / (HEIGHT - PADDING * 2)) * 100],
    }
  }
  const xs = positions.map(([x]) => x)
  const ys = positions.map(([, y]) => y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const spanX = Math.max(maxX - minX, 1e-6)
  const spanY = Math.max(maxY - minY, 1e-6)
  const scale = Math.min((WIDTH - PADDING * 2) / spanX, (HEIGHT - PADDING * 2) / spanY)
  const offsetX = (WIDTH - spanX * scale) / 2
  const offsetY = (HEIGHT - spanY * scale) / 2
  return {
    point: ([x, y]) => [offsetX + (x - minX) * scale, HEIGHT - offsetY - (y - minY) * scale],
    inverse: ([x, y]) => [(x - offsetX) / scale + minX, (HEIGHT - offsetY - y) / scale + minY],
  }
}

export function geometryPaths(geometry: Geometry, projection: Projection): string[] {
  const rings = geometry.type === "LineString" ? [geometry.coordinates] : geometry.coordinates
  return rings.map((positions) =>
    positions
      .map((position, index) => {
        const [x, y] = projection.point(position)
        return `${index ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`
      })
      .join(" "),
  )
}
