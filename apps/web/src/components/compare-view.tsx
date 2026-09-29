import { useEffect, useState } from "react"
import { Check, GitCompareArrows, Layers2, Save, ScanLine, TriangleAlert } from "lucide-react"

import { GeometryStage, type ContextGeometry } from "@/components/geometry-stage"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import type { Acceptability, FailureTag, Scene } from "@/lib/api"
import type { AnnotationChoice, Candidate, Feature, ReviewDraft } from "@/lib/api-extra"

type CompareViewProps = {
  feature?: Feature
  candidateA?: Candidate
  candidateB?: Candidate
  scene?: Scene
  onAnnotate: (review: ReviewDraft) => Promise<void>
}

const failureOptions: Array<{ value: FailureTag; label: string }> = [
  { value: "topology-failure", label: "Topology" },
  { value: "visual-collision", label: "Collision" },
  { value: "excessive-detail-loss", label: "Detail loss" },
  { value: "characteristic-shape-loss", label: "Shape loss" },
  { value: "context-inconsistency", label: "Context" },
  { value: "displacement-needed", label: "Needs displacement" },
]

export function CompareView({ feature, candidateA, candidateB, scene, onAnnotate }: CompareViewProps) {
  const [mode, setMode] = useState<"swipe" | "overlay">("swipe")
  const [swipe, setSwipe] = useState(50)
  const [choice, setChoice] = useState<AnnotationChoice | null>(null)
  const [acceptability, setAcceptability] = useState<Acceptability>("unsure")
  const [failureTags, setFailureTags] = useState<FailureTag[]>([])
  const [comment, setComment] = useState("")
  const [pending, setPending] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)

  useEffect(() => {
    setChoice(null)
    setAcceptability("unsure")
    setFailureTags([])
    setComment("")
    setReviewError(null)
  }, [feature?.current_revision.id, scene?.id])

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
  const context: ContextGeometry[] = (scene?.members ?? [])
    .filter((member) => member.role !== "target")
    .map((member) => ({
      geometry: member.feature.current_revision.geometry,
      role: member.role as ContextGeometry["role"],
      importance: member.importance,
      style: member.style,
    }))

  async function annotate(next: AnnotationChoice) {
    if (scene) {
      setChoice(next)
      return
    }
    try {
      setPending(true)
      setReviewError(null)
      await onAnnotate({ choice: next, acceptability: "unsure", failureTags: [], comment: "" })
      setChoice(next)
    } catch (caught) {
      setReviewError(caught instanceof Error ? caught.message : "Could not save preference")
    } finally {
      setPending(false)
    }
  }

  async function saveSceneReview() {
    if (!choice) return
    try {
      setPending(true)
      setReviewError(null)
      await onAnnotate({ choice, acceptability, failureTags, comment })
    } catch (caught) {
      setReviewError(caught instanceof Error ? caught.message : "Could not save scene review")
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-65px)] flex-col gap-4 p-4 lg:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Badge className="bg-[#e4f2ee] text-[#006b63]" variant="secondary">{feature.current_revision.geometry.type}</Badge>
            <span className="text-xs text-muted-foreground">revision {feature.current_revision.sequence}</span>
            {scene && <Badge variant="outline">{scene.region === "north-america" ? "North America" : scene.region.charAt(0).toUpperCase() + scene.region.slice(1)} scene</Badge>}
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">{feature.name}</h1>
          {scene && <p className="mt-1 text-sm text-muted-foreground">{scene.name} · {scene.locality || "Unspecified locality"} · {context.length} context features</p>}
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
                context={context}
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
        <div className="space-y-3 rounded-xl border bg-card p-3 shadow-sm">
          <div className="flex flex-wrap items-center gap-2">
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
          {scene && (
            <div className="grid gap-3 border-t pt-3 lg:grid-cols-[1fr_1.3fr]">
              <div className="space-y-3">
                <div><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Overall acceptability</p><div className="flex flex-wrap gap-2">{(["acceptable", "unacceptable", "unsure"] as const).map((value) => <Button key={value} onClick={() => setAcceptability(value)} size="sm" variant={acceptability === value ? "secondary" : "outline"}>{value.charAt(0).toUpperCase() + value.slice(1)}</Button>)}</div></div>
                <div><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Observed failures</p><div className="flex flex-wrap gap-2">{failureOptions.map((option) => { const active = failureTags.includes(option.value); return <Button key={option.value} onClick={() => setFailureTags((tags) => active ? tags.filter((tag) => tag !== option.value) : [...tags, option.value])} size="sm" variant={active ? "secondary" : "outline"}>{active && <Check />}{option.label}</Button> })}</div></div>
              </div>
              <div className="flex min-w-0 flex-col gap-2"><Textarea aria-label="Review comment" className="min-h-24 flex-1" onChange={(event) => setComment(event.target.value)} placeholder="Optional note about context, characteristic shape, or required displacement…" value={comment} /><Button className="self-end" disabled={!choice || pending} onClick={saveSceneReview}><Save /> {pending ? "Saving…" : "Save scene review"}</Button></div>
            </div>
          )}
          {reviewError && <p className="text-sm text-destructive">{reviewError}</p>}
        </div>
      )}
    </div>
  )
}
