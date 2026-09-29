import { createHash } from "node:crypto"

import { deepseek, type DeepSeekLanguageModelOptions } from "@ai-sdk/deepseek"
import { generateText, Output } from "ai"
import { z } from "zod"

const positionSchema = z.tuple([z.number().finite(), z.number().finite()])

export const simplifyRequestSchema = z.object({
  geometryType: z.enum(["LineString", "Polygon"]),
  coordinates: z.array(positionSchema).min(2).max(256),
  budget: z.number().int().min(2).max(64),
  maxDisplacement: z.number().positive().max(0.05),
  previousErrors: z.array(z.string()).max(10).default([]),
})

export type SimplifyRequest = z.infer<typeof simplifyRequestSchema>

export type SimplifyResult = {
  keptIndices: number[]
  offsets: Array<[number, number]>
  model: string
  promptVersion: string
  promptHash: string
  usage: Record<string, number | undefined>
}

export type SimplificationGenerator = (request: SimplifyRequest) => Promise<SimplifyResult>

const PROMPT_VERSION = "keep-move-v1"

function promptFor(request: SimplifyRequest): string {
  const closureRule = request.geometryType === "Polygon"
    ? "Indices must remain in cyclic source order. Do not repeat the first index; closure is added by the geometry engine."
    : "You must retain indices 0 and the last source index, with zero offsets for both endpoints."
  const retry = request.previousErrors.length
    ? `The previous proposal failed validation: ${request.previousErrors.join("; ")}. Correct those failures.`
    : ""
  return [
    "You are proposing a cartographic simplification of a normalized vector geometry.",
    `Select exactly ${request.budget} source vertices and optionally move them slightly.`,
    "Preserve the characteristic shape, source order, and topology.",
    `Every dx and dy must be between -${request.maxDisplacement} and ${request.maxDisplacement}.`,
    closureRule,
    retry,
    `Geometry type: ${request.geometryType}`,
    `Coordinates: ${JSON.stringify(request.coordinates)}`,
  ].filter(Boolean).join("\n")
}

export function createDeepSeekGenerator(): SimplificationGenerator {
  const modelId = process.env.DEEPSEEK_MODEL ?? "deepseek-flash"
  return async (request) => {
    const responseSchema = z.object({
      keptIndices: z.array(z.number().int().nonnegative()).length(request.budget)
        .describe("Distinct source indices in source traversal order"),
      offsets: z.array(positionSchema).length(request.budget)
        .describe("Coordinate offsets corresponding one-to-one with keptIndices"),
    })
    const prompt = promptFor(request)
    const result = await generateText({
      model: deepseek(modelId),
      output: Output.object({
        name: "geometry_simplification",
        description: "An exact-budget keep-and-move geometry proposal",
        schema: responseSchema,
      }),
      prompt,
      temperature: 0,
      providerOptions: {
        deepseek: {
          thinking: { type: "disabled" },
        } satisfies DeepSeekLanguageModelOptions,
      },
      abortSignal: AbortSignal.timeout(60_000),
    })
    return {
      keptIndices: result.output.keptIndices,
      offsets: result.output.offsets,
      model: modelId,
      promptVersion: PROMPT_VERSION,
      promptHash: createHash("sha256").update(prompt).digest("hex"),
      usage: {
        inputTokens: result.usage.inputTokens,
        outputTokens: result.usage.outputTokens,
        totalTokens: result.usage.totalTokens,
      },
    }
  }
}

export async function simplify(
  input: unknown,
  generator: SimplificationGenerator,
): Promise<SimplifyResult> {
  const request = simplifyRequestSchema.parse(input)
  if (request.geometryType === "Polygon" && request.budget < 3) {
    throw new Error("Polygon simplification requires at least three vertices")
  }
  if (request.budget > request.coordinates.length) {
    throw new Error("Budget cannot exceed source vertex count")
  }
  return generator(request)
}
