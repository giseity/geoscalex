import { describe, expect, test } from "vitest"

import { simplify, type SimplificationGenerator } from "./service.js"

const fake: SimplificationGenerator = async (request) => ({
  keptIndices: [0, request.coordinates.length - 1],
  offsets: [[0, 0], [0, 0]],
  model: "fake",
  promptVersion: "test",
  promptHash: "hash",
  usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2 },
})

describe("simplification service", () => {
  test("validates and delegates a line request", async () => {
    const result = await simplify({
      geometryType: "LineString",
      coordinates: [[0, 0], [0.5, 0.1], [1, 0]],
      budget: 2,
      maxDisplacement: 0.05,
      previousErrors: [],
    }, fake)
    expect(result.keptIndices).toEqual([0, 2])
  })

  test("rejects an undersized polygon budget", async () => {
    await expect(simplify({
      geometryType: "Polygon",
      coordinates: [[0, 0], [1, 0], [0, 1]],
      budget: 2,
      maxDisplacement: 0.05,
      previousErrors: [],
    }, fake)).rejects.toThrow("at least three")
  })
})
