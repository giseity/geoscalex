// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import { afterEach, expect, test, vi } from "vitest"

import { GeometryStage } from "@/components/geometry-stage"

const geometry = {
  type: "LineString" as const,
  coordinates: [[0, 0], [10, 20], [30, 5]] as Array<[number, number]>,
}

afterEach(cleanup)

test("the visible comparison divider is keyboard adjustable", () => {
  const onSwipeChange = vi.fn()
  render(<GeometryStage left={geometry} mode="swipe" onSwipeChange={onSwipeChange} original={geometry} right={geometry} swipe={50} />)

  const divider = screen.getByRole("slider", { name: "Comparison divider" })
  fireEvent.keyDown(divider, { key: "ArrowRight" })
  fireEvent.keyDown(divider, { key: "Home" })

  expect(onSwipeChange).toHaveBeenNthCalledWith(1, 52)
  expect(onSwipeChange).toHaveBeenNthCalledWith(2, 0)
})

test("viewport controls zoom and reset the geometry", () => {
  render(<GeometryStage mode="overlay" original={geometry} swipe={50} />)

  fireEvent.click(screen.getByRole("button", { name: "Zoom in" }))
  expect(screen.getByText("135%")).toBeInTheDocument()

  fireEvent.click(screen.getByRole("button", { name: "Fit geometry" }))
  expect(screen.getByText("100%")).toBeInTheDocument()
})

test("trackpad pinch is consumed by the geometry viewport", () => {
  render(<GeometryStage mode="overlay" original={geometry} swipe={50} />)
  const pinch = new WheelEvent("wheel", { bubbles: true, cancelable: true, ctrlKey: true, deltaY: -100 })

  expect(fireEvent(screen.getByTestId("geometry-stage"), pinch)).toBe(false)
  expect(pinch.defaultPrevented).toBe(true)
  expect(screen.getByText("118%")).toBeInTheDocument()
})
