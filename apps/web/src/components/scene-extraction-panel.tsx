import { useMemo, useState } from "react"
import { CircleStop, Eye, Network, Play, RefreshCw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import {
  api,
  type Batch,
  type Job,
  type SceneExtractionInput,
  type SceneExtractionPreview,
  type SceneRegion,
} from "@/lib/api"

type GeometryType = SceneExtractionInput["geometry_types"][number]

type SceneExtractionPanelProps = {
  datasetId: string
  batches: Batch[]
  jobs: Job[]
  onCancel: (jobId: string) => Promise<void>
  onQueued: () => Promise<void>
  onRefresh: () => void
}

const roleOrder = ["parent", "child", "obstacle", "sibling", "background"] as const

export function SceneExtractionPanel({
  datasetId,
  batches,
  jobs,
  onCancel,
  onQueued,
  onRefresh,
}: SceneExtractionPanelProps) {
  const [batchId, setBatchId] = useState("all")
  const [region, setRegion] = useState<SceneRegion>("europe")
  const [locality, setLocality] = useState("")
  const [groupPrefix, setGroupPrefix] = useState("auto")
  const [radius, setRadius] = useState(1000)
  const [maxContext, setMaxContext] = useState(12)
  const [maxScenes, setMaxScenes] = useState(500)
  const [scale, setScale] = useState(50_000)
  const [stylePreset, setStylePreset] = useState("atlas")
  const [geometryTypes, setGeometryTypes] = useState<GeometryType[]>(["LineString", "Polygon"])
  const [skipExisting, setSkipExisting] = useState(true)
  const [preview, setPreview] = useState<SceneExtractionPreview | null>(null)
  const [pending, setPending] = useState<"preview" | "queue" | null>(null)
  const [error, setError] = useState<string | null>(null)

  const extractionJobs = useMemo(
    () => jobs.filter((job) => job.kind === "scene-extraction" && job.payload.dataset_id === datasetId),
    [datasetId, jobs],
  )

  function input(): SceneExtractionInput {
    return {
      dataset_id: datasetId,
      target_batch_id: batchId === "all" ? null : batchId,
      region,
      locality: locality.trim(),
      location_group_prefix: groupPrefix.trim() || "auto",
      scale_denominator: scale,
      style_preset: stylePreset,
      radius,
      max_context: maxContext,
      geometry_types: geometryTypes,
      max_scenes: maxScenes,
      skip_existing_targets: skipExisting,
    }
  }

  async function loadPreview() {
    try {
      if (!geometryTypes.length) throw new Error("Select at least one target geometry type")
      setPending("preview")
      setError(null)
      setPreview(await api.previewSceneExtraction(input()))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not preview extraction")
    } finally {
      setPending(null)
    }
  }

  async function queue() {
    try {
      if (!geometryTypes.length) throw new Error("Select at least one target geometry type")
      setPending("queue")
      setError(null)
      await api.runSceneExtraction(input())
      setPreview(null)
      await onQueued()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not queue extraction")
    } finally {
      setPending(null)
    }
  }

  function toggleGeometryType(value: GeometryType) {
    setGeometryTypes((current) =>
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    )
    setPreview(null)
  }

  return (
    <div className="space-y-5">
      <div>
        <div className="grid size-10 place-items-center rounded-lg bg-[#e8f4f1] text-[#00796f]"><Network className="size-5" /></div>
        <h2 className="pt-3 text-lg font-semibold">Extract spatial scenes</h2>
        <CardDescription className="mt-1">Build deterministic neighborhoods from the features already in this dataset.</CardDescription>
      </div>

      <div className="space-y-2">
        <Label>Target batch</Label>
        <Select onValueChange={(value) => { setBatchId(value); setPreview(null) }} value={batchId}>
          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All active features</SelectItem>
            {batches.map((batch) => <SelectItem key={batch.id} value={batch.id}>{batch.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Target geometry</Label>
        <div className="grid grid-cols-2 gap-2">
          {(["LineString", "Polygon"] as GeometryType[]).map((type) => (
            <Button key={type} onClick={() => toggleGeometryType(type)} size="sm" variant={geometryTypes.includes(type) ? "secondary" : "outline"}>{type === "LineString" ? "Lines" : "Polygons"}</Button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2"><Label>Region</Label><Select onValueChange={(value) => { setRegion(value as SceneRegion); setPreview(null) }} value={region}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="europe">Europe</SelectItem><SelectItem value="north-america">North America</SelectItem><SelectItem value="other">Other</SelectItem></SelectContent></Select></div>
        <div className="space-y-2"><Label htmlFor="extract-scale">Scale</Label><Input id="extract-scale" min={1} onChange={(event) => { setScale(event.target.valueAsNumber || 1); setPreview(null) }} type="number" value={scale} /></div>
      </div>
      <div className="space-y-2"><Label htmlFor="extract-locality">Locality</Label><Input id="extract-locality" onChange={(event) => { setLocality(event.target.value); setPreview(null) }} placeholder="Rhine basin, Chicago…" value={locality} /></div>
      <div className="space-y-2"><Label htmlFor="extract-group">Location prefix</Label><Input id="extract-group" onChange={(event) => { setGroupPrefix(event.target.value); setPreview(null) }} value={groupPrefix} /><p className="text-xs leading-5 text-muted-foreground">Nearby targets are assigned to the same leakage-safe grid group.</p></div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2"><Label htmlFor="extract-radius">Radius</Label><Input id="extract-radius" min={0.000001} onChange={(event) => { setRadius(event.target.valueAsNumber || 1); setPreview(null) }} type="number" value={radius} /><p className="text-[11px] text-muted-foreground">Metres for geographic data</p></div>
        <div className="space-y-2"><Label htmlFor="extract-context">Max context</Label><Input id="extract-context" max={100} min={1} onChange={(event) => { setMaxContext(event.target.valueAsNumber || 1); setPreview(null) }} type="number" value={maxContext} /></div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2"><Label htmlFor="extract-limit">Scene limit</Label><Input id="extract-limit" max={10000} min={1} onChange={(event) => { setMaxScenes(event.target.valueAsNumber || 1); setPreview(null) }} type="number" value={maxScenes} /></div>
        <div className="space-y-2"><Label>Style</Label><Select onValueChange={(value) => { setStylePreset(value); setPreview(null) }} value={stylePreset}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="atlas">General atlas</SelectItem><SelectItem value="hydrography">Hydrography</SelectItem><SelectItem value="roads">Road network</SelectItem><SelectItem value="boundaries">Administrative</SelectItem></SelectContent></Select></div>
      </div>
      <div className="flex items-center justify-between gap-4 rounded-lg border p-3"><div><Label htmlFor="skip-existing">Skip existing targets</Label><p className="mt-1 text-xs text-muted-foreground">Recommended for safe repeat runs.</p></div><Switch checked={skipExisting} id="skip-existing" onCheckedChange={(checked) => { setSkipExisting(checked); setPreview(null) }} /></div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="grid grid-cols-2 gap-2">
        <Button disabled={Boolean(pending)} onClick={loadPreview} variant="outline"><Eye /> {pending === "preview" ? "Analyzing…" : "Preview"}</Button>
        <Button className="bg-[#006b63] hover:bg-[#005a53]" disabled={Boolean(pending) || !preview || preview.proposed_scenes === 0} onClick={queue}><Play /> {pending === "queue" ? "Queueing…" : "Queue run"}</Button>
      </div>

      {preview && (
        <div className="space-y-3 rounded-xl border bg-[#f7f8f5] p-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg bg-white p-3"><p className="text-2xl font-semibold">{preview.proposed_scenes}</p><p className="text-xs text-muted-foreground">Scenes proposed</p></div>
            <div className="rounded-lg bg-white p-3"><p className="text-2xl font-semibold">{preview.isolated_targets}</p><p className="text-xs text-muted-foreground">Isolated targets</p></div>
          </div>
          <p className="text-xs text-muted-foreground">{preview.eligible_targets} eligible · {preview.existing_targets} existing skipped · {preview.incompatible_features} incompatible</p>
          <div className="flex flex-wrap gap-1.5">{roleOrder.map((role) => preview.role_counts[role] ? <Badge key={role} variant="outline">{role} {preview.role_counts[role]}</Badge> : null)}</div>
          {preview.samples.slice(0, 4).map((sample) => <div className="rounded-lg border bg-white p-2.5" key={sample.target_feature_id}><p className="truncate text-sm font-medium">{sample.target_name}</p><p className="mt-1 text-xs text-muted-foreground">{sample.context_count} context · {sample.location_group}</p></div>)}
        </div>
      )}

      {extractionJobs.length > 0 && (
        <div className="space-y-2 border-t pt-4">
          <div className="flex items-center justify-between"><Label>Extraction runs</Label><Button aria-label="Refresh extraction runs" onClick={onRefresh} size="icon-sm" variant="ghost"><RefreshCw /></Button></div>
          {extractionJobs.slice(0, 3).map((job) => (
            <div className="rounded-lg border p-3" key={job.id}>
              <div className="flex items-center gap-2"><Badge variant={job.status === "failed" ? "destructive" : "secondary"}>{job.status}</Badge><span className="ml-auto font-mono text-xs text-muted-foreground">{job.id.slice(0, 8)}</span></div>
              <Progress className="mt-2" value={job.progress * 100} />
              <p className="mt-2 text-xs text-muted-foreground">{job.status === "succeeded" ? `${String(job.result.created ?? 0)} scenes created` : job.error ?? job.logs.at(-1) ?? "Waiting for worker"}</p>
              {(job.status === "queued" || job.status === "running") && <Button className="mt-2" onClick={() => onCancel(job.id)} size="sm" variant="outline"><CircleStop /> Cancel</Button>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
