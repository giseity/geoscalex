// @vitest-environment jsdom

import { afterEach, expect, test, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"

import { App } from "./app"

afterEach(() => vi.restoreAllMocks())

test("renders local onboarding when no workspace exists", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
  )
  render(<App />)
  expect(await screen.findByRole("heading", { name: "Create your local Dataset Lab" })).toBeInTheDocument()
})
