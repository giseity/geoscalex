import { Archive, Braces, Copy, Gauge, PencilLine, Sparkles } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar"
import { Slider } from "@/components/ui/slider"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { Candidate, Feature, Revision } from "@/lib/api"
import { vertexCount } from "@/lib/geometry"

type InspectorSidebarProps = {
  feature?: Feature
  candidateA?: Candidate
  candidateB?: Candidate
  budget: number
  busy: boolean
  revisions: Revision[]
  onBudgetChange: (budget: number) => void
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
      <p className="mt-1 font-mono text-sm font-semibold">{value}</p>
    </div>
  )
}

export function InspectorSidebar({
  feature,
  candidateA,
  candidateB,
  budget,
  busy,
  revisions,
  onBudgetChange,
  onBuildCandidates,
  onEdit,
  onAddHole,
  onDuplicate,
  onArchive,
  onRestoreRevision,
}: InspectorSidebarProps) {
  const sourceCount = vertexCount(feature?.current_revision.geometry)
  const reduction = candidateA ? Math.round(Number(candidateA.metrics.vertex_reduction) * 100) : 0

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
      <SidebarContent>
        {!feature ? (
          <div className="px-6 py-12 text-center text-sm text-muted-foreground">Select a feature to inspect it.</div>
        ) : (
          <>
            <SidebarGroup>
              <SidebarGroupLabel>Geometry</SidebarGroupLabel>
              <SidebarGroupContent className="grid grid-cols-2 gap-2">
                <Metric label="Type" value={feature.current_revision.geometry.type} />
                <Metric label="Vertices" value={sourceCount} />
                <Metric label="Space" value={feature.current_revision.coordinate_space} />
                <Metric label="Source" value={feature.source} />
              </SidebarGroupContent>
            </SidebarGroup>
            <Separator />
            <SidebarGroup>
              <SidebarGroupLabel>Revision history</SidebarGroupLabel>
              <SidebarGroupContent className="px-2">
                <Select
                  onValueChange={(revisionId) => {
                    if (revisionId !== feature.current_revision.id) onRestoreRevision(revisionId)
                  }}
                  value={feature.current_revision.id}
                >
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {revisions.map((revision) => (
                      <SelectItem key={revision.id} value={revision.id}>
                        r{revision.sequence} · {revision.change_kind}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">Choosing an older entry creates a new immutable restore revision.</p>
              </SidebarGroupContent>
            </SidebarGroup>
            <Separator />
            <SidebarGroup>
              <SidebarGroupLabel>Matched budget</SidebarGroupLabel>
              <SidebarGroupContent className="space-y-4 px-2">
                <div className="flex items-end justify-between">
                  <div>
                    <p className="text-2xl font-semibold tabular-nums">{budget}</p>
                    <p className="text-xs text-muted-foreground">target vertices</p>
                  </div>
                  <Gauge className="size-5 text-[#00796f]" />
                </div>
                <Slider
                  max={Math.max(3, sourceCount)}
                  min={feature.current_revision.geometry.type === "Polygon" ? 4 : 2}
                  onValueChange={([value]) => onBudgetChange(value)}
                  step={1}
                  value={[Math.min(budget, Math.max(3, sourceCount))]}
                />
                <Progress value={sourceCount ? (budget / sourceCount) * 100 : 0} />
                <Button className="w-full bg-[#006b63] hover:bg-[#005a53]" disabled={busy || sourceCount <= 2} onClick={onBuildCandidates}>
                  <Sparkles /> {busy ? "Computing…" : "Build comparison"}
                </Button>
                {candidateA && candidateB && (
                  <p className="text-xs leading-5 text-muted-foreground">
                    A and B both target {budget} vertices. A currently removes {reduction}% of source vertices.
                  </p>
                )}
              </SidebarGroupContent>
            </SidebarGroup>
            <Separator />
            <SidebarGroup>
              <SidebarGroupLabel>Feature actions</SidebarGroupLabel>
              <SidebarGroupContent className="grid grid-cols-2 gap-2 px-2">
                <Button onClick={onEdit} size="sm" variant="outline"><PencilLine /> Edit</Button>
                <Button onClick={onDuplicate} size="sm" variant="outline"><Copy /> Duplicate</Button>
                {feature.current_revision.geometry.type === "Polygon" && (
                  <Button onClick={onAddHole} size="sm" variant="outline"><Braces /> Add hole</Button>
                )}
                <Button onClick={onArchive} size="sm" variant="outline"><Archive /> Archive</Button>
              </SidebarGroupContent>
            </SidebarGroup>
          </>
        )}
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
