import { createServer, type IncomingMessage, type ServerResponse } from "node:http"

import type { SimplificationGenerator } from "./service.js"
import { simplify } from "./service.js"

const MAX_BODY_BYTES = 1_000_000

function json(response: ServerResponse, status: number, body: unknown): void {
  response.writeHead(status, { "Content-Type": "application/json" })
  response.end(JSON.stringify(body))
}

async function body(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = []
  let size = 0
  for await (const chunk of request) {
    const value = Buffer.from(chunk)
    size += value.length
    if (size > MAX_BODY_BYTES) throw new Error("Request body is too large")
    chunks.push(value)
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"))
}

export function createGatewayServer(generator: SimplificationGenerator | null) {
  return createServer(async (request, response) => {
    try {
      if (request.method === "GET" && request.url === "/health") {
        json(response, 200, { status: "ok", configured: generator !== null })
        return
      }
      if (request.method === "POST" && request.url === "/v1/simplify") {
        if (!generator) {
          json(response, 503, { error: "DeepSeek is not configured" })
          return
        }
        json(response, 200, await simplify(await body(request), generator))
        return
      }
      json(response, 404, { error: "Not found" })
    } catch (error) {
      json(response, 422, { error: error instanceof Error ? error.message : "Invalid request" })
    }
  })
}
