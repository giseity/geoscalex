import { Archive, Braces, Copy, Gauge, History, PencilLine, SlidersHorizontal, Sparkles, Waypoints } from "lucide-react"

import { CANDIDATE_A_COLOR, CANDIDATE_B_COLOR } from "@/components/geometry-stage"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { Candidate, Feature, Revision, SimplificationBudget, SimplificationMethod } from "@/lib/api"
import { vertexCount } from "@/lib/geometry"

type InspectorSidebarProps = {
  feature?: Feature
  candidateA?: Candidate
  candidateB?: Candidate
  budget: number
  budgetKind: SimplificationBudget["kind"]
  retentionRatio: number
  busy: boolean
  methods: SimplificationMethod[]
  methodA: string
  methodB: string
  revisions: Revision[]
  onBudgetChange: (budget: number) => void
  onBudgetKindChange: (kind: SimplificationBudget["kind"]) => void
  onRetentionRatioChange: (ratio: number) => void
  onMethodAChange: (method: string) => void
  onMethodBChange: (method: string) => void
  onBuildCandidates: () => void
  onEdit: () => void
  onAddHole: () => void
  onDuplicate: () => void
  onArchive: () => void
  onRestoreRevision: (revisionId: string) => void
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border bg-background/70 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.13em] text-muted-foreground">{label}</p>
      <p className="mt-1 truncate font-mono text-sm font-semibold">{value}</p>
    </div>
  )
}

export function InspectorSidebar({
  feature,
  candidateA,
  candidateB,
  budget,
  budgetKind,
  retentionRatio,
  busy,
  methods,
  methodA,
  methodB,
  revisions,
  onBudgetChange,
  onBudgetKindChange,
  onRetentionRatioChange,
  onMethodAChange,
  onMethodBChange,
  onBuildCandidates,
  onEdit,
  onAddHole,
  onDuplicate,
  onArchive,
  onRestoreRevision,
}: InspectorSidebarProps) {
  const sourceCount = vertexCount(feature?.current_revision.geometry)
  const minimum = feature?.current_revision.geometry.type === "Polygon" ? 3 : 2
  const hasHoles = feature?.current_revision.geometry.type === "Polygon" && feature.current_revision.geometry.coordinates.length > 1
  const reductionA = candidateA ? Math.round(Number(candidateA.metrics.vertex_reduction) * 100) : null
  const reductionB = candidateB ? Math.round(Number(candidateB.metrics.vertex_reduction) * 100) : null
  const methodAllowed = (method: SimplificationMethod) => method.available && (!hasHoles || method.supports_holes)

  return (
    <Sidebar className="border-l" collapsible="offcanvas" side="right">
      <SidebarHeader className="h-[65px] justify-center border-b px-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Inspector</p>
            <p className="max-w-48 truncate text-sm font-semibold">{feature?.name ?? "No selection"}</p>
          </div>
          {feature && <Badge variant="outline">r{feature.current_revision.sequence}</Badge>}
        </div>
      </SidebarHeader>
      <SidebarContent className="overflow-hidden">
        {!feature ? (
          <div className="px-6 py-12 text-center text-sm text-muted-foreground">Select a feature to inspect it.</div>
        ) : (
          <Tabs className="flex min-h-0 flex-1 flex-col" defaultValue="setup">
            <div className="border-b p-2">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="setup"><SlidersHorizontal /> Setup</TabsTrigger>
                <TabsTrigger value="metrics"><Waypoints /> Metrics</TabsTrigger>
                <TabsTrigger value="history"><History /> History</TabsTrigger>
              </TabsList>
            </div>

            <TabsContent className="min-h-0 flex-1 overflow-y-auto px-4 py-5" value="setup">
              <div className="space-y-5">
                <div>
                  <p className="text-sm font-semibold">Matched comparison</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">Both candidates receive the same resolved vertex budget.</p>
                </div>

                <div className="space-y-2">
                  <Label className="flex items-center gap-2"><span className="size-2.5 rounded-full" style={{ backgroundColor: CANDIDATE_A_COLOR }} /> Candidate A</Label>
                  <Select onValueChange={onMethodAChange} value={methodA}>
                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>{methods.map((method) => <SelectItem disabled={!methodAllowed(method)} key={method.id} value={method.id}>{method.name}</SelectItem>)}</SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label className="flex items-center gap-2"><span className="size-2.5 rounded-full" style={{ backgroundColor: CANDIDATE_B_COLOR }} /> Candidate B</Label>
                  <Select onValueChange={onMethodBChange} value={methodB}>
                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>{methods.map((method) => <SelectItem disabled={!methodAllowed(method)} key={method.id} value={method.id}>{method.name}</SelectItem>)}</SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Budget input</Label>
                  <Select onValueChange={(value) => onBudgetKindChange(value as SimplificationBudget["kind"])} value={budgetKind}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="vertex-count">Vertex count</SelectItem>
                      <SelectItem value="retention-ratio">Retention ratio</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="rounded-xl border bg-muted/25 p-3">
                  <div className="flex items-end justify-between">
                    <div>
                      <p className="text-2xl font-semibold tabular-nums">{budget}</p>
                      <p className="text-xs text-muted-foreground">resolved vertices{budgetKind === "retention-ratio" ? ` · ${Math.round(retentionRatio * 100)}%` : ""}</p>
                    </div>
                    <Gauge className="size-5 text-[#00796f]" />
                  </div>
                  <div className="mt-4">
                    {budgetKind === "vertex-count" ? (
                      <Slider max={Math.max(minimum, sourceCount)} min={minimum} onValueChange={([value]) => onBudgetChange(value)} step={1} value={[Math.min(budget, Math.max(minimum, sourceCount))]} />
                    ) : (
                      <Slider max={100} min={Math.max(1, Math.ceil((minimum / Math.max(sourceCount, minimum)) * 100))} onValueChange={([value]) => onRetentionRatioChange(value / 100)} step={1} value={[Math.round(retentionRatio * 100)]} />
                    )}
                  </div>
                  <Progress className="mt-4" value={sourceCount ? (budget / sourceCount) * 100 : 0} />
                </div>

                <Button className="w-full bg-[#006b63] hover:bg-[#005a53]" disabled={busy || sourceCount <= 2} onClick={onBuildCandidates}>
                  <Sparkles /> {busy ? "Computing…" : "Build comparison"}
                </Button>
                {hasHoles && <p className="text-xs leading-5 text-amber-700">Learned and DeepSeek methods are currently unavailable for polygons with holes.</p>}
              </div>
            </TabsContent>

            <TabsContent className="min-h-0 flex-1 overflow-y-auto px-4 py-5" value="metrics">
              <div className="space-y-5">
                <div>
                  <p className="text-sm font-semibold">Source geometry</p>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <Metric label="Type" value={feature.current_revision.geometry.type} />
                    <Metric label="Vertices" value={sourceCount} />
                    <Metric label="Space" value={feature.current_revision.coordinate_space} />
                    <Metric label="Source" value={feature.source} />
                  </div>
                </div>
                <div>
                  <p className="text-sm font-semibold">Candidate result</p>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <Metric label="A achieved" value={candidateA ? vertexCount(candidateA.geometry) : "—"} />
                    <Metric label="B achieved" value={candidateB ? vertexCount(candidateB.geometry) : "—"} />
                    <Metric label="A reduction" value={reductionA === null ? "—" : `${reductionA}%`} />
                    <Metric label="B reduction" value={reductionB === null ? "—" : `${reductionB}%`} />
                  </div>
                </div>
                {!candidateA || !candidateB ? <p className="rounded-lg border border-dashed p-4 text-xs leading-5 text-muted-foreground">Build a matched comparison to populate candidate metrics.</p> : null}
              </div>
            </TabsContent>

            <TabsContent className="min-h-0 flex-1 overflow-y-auto px-4 py-5" value="history">
              <div className="space-y-6">
                <div>
                  <Label>Revision history</Label>
                  <Select
                    onValueChange={(revisionId) => {
                      if (revisionId !== feature.current_revision.id) onRestoreRevision(revisionId)
                    }}
                    value={feature.current_revision.id}
                  >
                    <SelectTrigger className="mt-2 w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {revisions.map((revision) => (
                        <SelectItem key={revision.id} value={revision.id}>r{revision.sequence} · {revision.change_kind}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">Choosing an older entry creates a new immutable restore revision.</p>
                </div>
                <div>
                  <p className="text-sm font-semibold">Feature actions</p>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <Button onClick={onEdit} size="sm" variant="outline"><PencilLine /> Edit</Button>
                    <Button onClick={onDuplicate} size="sm" variant="outline"><Copy /> Duplicate</Button>
                    {feature.current_revision.geometry.type === "Polygon" && <Button onClick={onAddHole} size="sm" variant="outline"><Braces /> Add hole</Button>}
                    <Button onClick={onArchive} size="sm" variant="outline"><Archive /> Archive</Button>
                  </div>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        )}
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
