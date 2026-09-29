import { useState } from "react"
import { Check, GitCompareArrows, Layers2, ScanLine, TriangleAlert } from "lucide-react"

import { GeometryStage } from "@/components/geometry-stage"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { AnnotationChoice, Candidate, Feature } from "@/lib/api-extra"

type CompareViewProps = {
  feature?: Feature
  candidateA?: Candidate
  candidateB?: Candidate
  onAnnotate: (choice: AnnotationChoice) => Promise<void>
}

export function CompareView({ feature, candidateA, candidateB, onAnnotate }: CompareViewProps) {
  const [mode, setMode] = useState<"swipe" | "overlay">("swipe")
  const [swipe, setSwipe] = useState(50)
  const [choice, setChoice] = useState<AnnotationChoice | null>(null)
  const [pending, setPending] = useState(false)

  if (!feature) {
    return (
      <div className="grid min-h-[calc(100vh-65px)] place-content-center px-6 text-center">
        <div className="mx-auto grid size-14 place-items-center rounded-2xl border bg-card shadow-sm"><GitCompareArrows /></div>
        <h2 className="mt-5 text-xl font-semibold">No feature selected</h2>
        <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">Draw a geometry, import GeoJSON, or run a deterministic generator to begin comparing simplifications.</p>
      </div>
    )
  }

  const ready = Boolean(candidateA && candidateB)

  async function annotate(next: AnnotationChoice) {
    setPending(true)
    await onAnnotate(next)
    setChoice(next)
    setPending(false)
  }

  return (
    <div className="flex min-h-[calc(100vh-65px)] flex-col gap-4 p-4 lg:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Badge className="bg-[#e4f2ee] text-[#006b63]" variant="secondary">{feature.current_revision.geometry.type}</Badge>
            <span className="text-xs text-muted-foreground">revision {feature.current_revision.sequence}</span>
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">{feature.name}</h1>
        </div>
        <Tabs onValueChange={(value) => setMode(value as "swipe" | "overlay")} value={mode}>
          <TabsList>
            <TabsTrigger value="swipe"><ScanLine /> Swipe</TabsTrigger>
            <TabsTrigger value="overlay"><Layers2 /> Overlay</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <Card className="flex-1 overflow-hidden p-0">
        <CardContent className="flex h-full min-h-[470px] flex-col p-0">
          {ready ? (
            <>
              <GeometryStage
                className="min-h-[430px] flex-1 rounded-none border-0"
                left={candidateA?.geometry}
                mode={mode}
                original={feature.current_revision.geometry}
                right={candidateB?.geometry}
                swipe={swipe}
              />
              {mode === "swipe" && (
                <div className="border-t bg-card px-6 py-4">
                  <Slider aria-label="Swipe position" max={100} min={0} onValueChange={([value]) => setSwipe(value)} value={[swipe]} />
                </div>
              )}
            </>
          ) : (
            <div className="grid min-h-[470px] flex-1 place-content-center bg-[#f3f0e7] px-6 text-center">
              <div className="mx-auto grid size-12 place-items-center rounded-full bg-white shadow-sm"><TriangleAlert className="size-5 text-[#db5e37]" /></div>
              <h2 className="mt-4 font-semibold text-slate-900">No matched candidates yet</h2>
              <p className="mt-2 max-w-sm text-sm leading-6 text-slate-600">Choose a vertex budget in the inspector, then build a Douglas–Peucker and Visvalingam–Whyatt comparison.</p>
            </div>
          )}
        </CardContent>
      </Card>

      {ready && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border bg-card p-3 shadow-sm">
          <span className="mr-auto pl-1 text-sm font-medium">Which result is more acceptable?</span>
          {(["A", "B", "equal", "artifact"] as const).map((item) => (
            <Button
              disabled={pending}
              key={item}
              onClick={() => annotate(item)}
              size="sm"
              variant={choice === item ? "default" : "outline"}
            >
              {choice === item && <Check />}
              {item === "equal" ? "Equal" : item === "artifact" ? "Artifact" : `Prefer ${item}`}
            </Button>
          ))}
        </div>
      )}
    </div>
  )
}
