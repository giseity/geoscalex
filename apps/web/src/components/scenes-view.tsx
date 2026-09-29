import { useEffect, useMemo, useState } from "react"
import { Archive, ArrowRight, Globe2, Layers3, MapPinned, Plus, Route } from "lucide-react"

import { GeometryStage, type ContextGeometry } from "@/components/geometry-stage"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { api, type Feature, type Scene, type SceneRegion, type SceneRole } from "@/lib/api"

type ContextRole = Exclude<SceneRole, "target">

const contextRoles: Array<{ value: ContextRole; label: string }> = [
  { value: "sibling", label: "Sibling" },
  { value: "parent", label: "Parent" },
  { value: "child", label: "Child" },
  { value: "background", label: "Background" },
  { value: "obstacle", label: "Obstacle" },
]

const stylePresets = {
  atlas: { name: "General atlas", target: "#006b63", context: "role-based" },
  hydrography: { name: "Hydrography", target: "#1677a6", context: "water-network" },
  roads: { name: "Road network", target: "#b65f3d", context: "transport-network" },
  boundaries: { name: "Administrative", target: "#76578f", context: "boundaries" },
} as const

type StylePreset = keyof typeof stylePresets

type SceneCreateInput = Parameters<typeof api.createScene>[0]

type ScenesViewProps = {
  datasetId: string
  features: Feature[]
  scenes: Scene[]
  selectedSceneId: string | null
  onSelect: (scene: Scene) => void
  onCreate: (input: SceneCreateInput) => Promise<Scene>
  onReview: (scene: Scene) => void
  onArchive: (scene: Scene) => Promise<void>
}

function contextFor(scene: Scene): ContextGeometry[] {
  return scene.members
    .filter((member) => member.role !== "target")
    .map((member) => ({
      geometry: member.feature.current_revision.geometry,
      role: member.role as ContextRole,
      importance: member.importance,
      style: member.style,
    }))
}

function regionLabel(region: SceneRegion) {
  if (region === "north-america") return "North America"
  return region.charAt(0).toUpperCase() + region.slice(1)
}

export function ScenesView({
  datasetId,
  features,
  scenes,
  selectedSceneId,
  onSelect,
  onCreate,
  onReview,
  onArchive,
}: ScenesViewProps) {
  const [name, setName] = useState("Context pilot scene")
  const [targetId, setTargetId] = useState(features[0]?.id ?? "")
  const [region, setRegion] = useState<SceneRegion>("europe")
  const [locality, setLocality] = useState("")
  const [locationGroup, setLocationGroup] = useState("")
  const [scale, setScale] = useState(50_000)
  const [stylePreset, setStylePreset] = useState<StylePreset>("atlas")
  const [memberRoles, setMemberRoles] = useState<Record<string, ContextRole>>({})
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!features.some((feature) => feature.id === targetId)) setTargetId(features[0]?.id ?? "")
  }, [features, targetId])

  useEffect(() => {
    if (!memberRoles[targetId]) return
    setMemberRoles((roles) => {
      const next = { ...roles }
      delete next[targetId]
      return next
    })
  }, [targetId])

  const selectedScene = scenes.find((scene) => scene.id === selectedSceneId) ?? scenes[0]
  const target = selectedScene?.members.find((member) => member.role === "target")?.feature
  const selectableContext = useMemo(
    () => features.filter((feature) => feature.id !== targetId),
    [features, targetId],
  )

  async function create() {
    try {
      if (!targetId) throw new Error("Choose a target feature")
      setPending(true)
      setError(null)
      const created = await onCreate({
        dataset_id: datasetId,
        name: name.trim() || "Context pilot scene",
        target_feature_id: targetId,
        region,
        locality: locality.trim(),
        crs: features.find((feature) => feature.id === targetId)?.current_revision.crs ?? null,
        scale_denominator: scale,
        viewport: { mode: "scene", width: 1000, height: 620 },
        style: { preset: stylePreset, ...stylePresets[stylePreset] },
        provenance: {
          location_group: locationGroup.trim() || undefined,
          pilot_region: region,
          source: "manual-scene-builder",
        },
        members: Object.entries(memberRoles).map(([featureId, role], index) => ({
          feature_id: featureId,
          role,
          importance: role === "background" ? 0.35 : 0.7,
          z_order: index,
        })),
      })
      onSelect(created)
      setName("Context pilot scene")
      setMemberRoles({})
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create scene")
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-7xl p-4 lg:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#00796f]">Context corpus</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Contextual scenes</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Compose a target with the surrounding features that determine whether its generalization is acceptable.
          </p>
        </div>
        <div className="flex gap-2">
          <Badge variant="outline"><Globe2 /> Europe primary</Badge>
          <Badge variant="outline"><Route /> North America validation</Badge>
        </div>
      </div>

      <div className="mt-6 grid min-w-0 gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Card className="h-fit min-w-0">
          <CardHeader>
            <div className="grid size-10 place-items-center rounded-lg bg-[#e8f4f1] text-[#00796f]"><Plus className="size-5" /></div>
            <CardTitle className="pt-2">Build a scene</CardTitle>
            <CardDescription>The target is included automatically. Select only the context that affects the decision.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2"><Label htmlFor="scene-name">Scene name</Label><Input id="scene-name" onChange={(event) => setName(event.target.value)} value={name} /></div>
            <div className="space-y-2">
              <Label>Target feature</Label>
              <Select onValueChange={setTargetId} value={targetId}>
                <SelectTrigger className="w-full"><SelectValue placeholder="Choose a target" /></SelectTrigger>
                <SelectContent>{features.map((feature) => <SelectItem key={feature.id} value={feature.id}>{feature.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2"><Label>Region</Label><Select onValueChange={(value) => setRegion(value as SceneRegion)} value={region}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="europe">Europe</SelectItem><SelectItem value="north-america">North America</SelectItem><SelectItem value="other">Other</SelectItem></SelectContent></Select></div>
              <div className="space-y-2"><Label htmlFor="scene-scale">Scale</Label><Input id="scene-scale" min={1} onChange={(event) => setScale(event.target.valueAsNumber || 1)} type="number" value={scale} /></div>
            </div>
            <div className="space-y-2"><Label htmlFor="scene-locality">Locality</Label><Input id="scene-locality" onChange={(event) => setLocality(event.target.value)} placeholder="Rhine basin, Great Lakes…" value={locality} /></div>
            <div className="space-y-2"><Label htmlFor="location-group">Location group</Label><Input id="location-group" onChange={(event) => setLocationGroup(event.target.value)} placeholder="rhine-001" value={locationGroup} /><p className="text-xs leading-5 text-muted-foreground">Shared groups stay in the same train, validation, or test split.</p></div>
            <div className="space-y-2"><Label>Style preset</Label><Select onValueChange={(value) => setStylePreset(value as StylePreset)} value={stylePreset}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(stylePresets).map(([id, preset]) => <SelectItem key={id} value={id}>{preset.name}</SelectItem>)}</SelectContent></Select></div>
            <div className="space-y-2">
              <div className="flex items-center justify-between"><Label>Context features</Label><span className="text-xs text-muted-foreground">{Object.keys(memberRoles).length} selected</span></div>
              <ScrollArea className="h-52 rounded-lg border">
                <div className="space-y-1 p-2">
                  {selectableContext.map((feature) => {
                    const role = memberRoles[feature.id]
                    return (
                      <div className="rounded-md border bg-background p-2" key={feature.id}>
                        <div className="flex items-center gap-2">
                          <Button onClick={() => setMemberRoles((roles) => {
                            const next = { ...roles }
                            if (next[feature.id]) delete next[feature.id]
                            else next[feature.id] = "sibling"
                            return next
                          })} size="sm" variant={role ? "secondary" : "ghost"}>{role ? "Added" : "Add"}</Button>
                          <span className="min-w-0 flex-1 truncate text-sm">{feature.name}</span>
                        </div>
                        {role && <Select onValueChange={(value) => setMemberRoles((roles) => ({ ...roles, [feature.id]: value as ContextRole }))} value={role}><SelectTrigger className="mt-2 w-full"><SelectValue /></SelectTrigger><SelectContent>{contextRoles.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent></Select>}
                      </div>
                    )
                  })}
                  {!selectableContext.length && <p className="p-4 text-center text-xs text-muted-foreground">Add more features before composing context.</p>}
                </div>
              </ScrollArea>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button className="w-full bg-[#006b63] hover:bg-[#005a53]" disabled={!targetId || pending} onClick={create}><Layers3 /> {pending ? "Creating…" : "Create contextual scene"}</Button>
          </CardContent>
        </Card>

        <div className="min-w-0 space-y-5">
          {selectedScene && target ? (
            <Card className="min-w-0 overflow-hidden p-0">
              <CardHeader className="border-b">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><div className="flex items-center gap-2"><Badge>{regionLabel(selectedScene.region)}</Badge><span className="text-xs text-muted-foreground">1:{selectedScene.scale_denominator?.toLocaleString() ?? "—"}</span></div><CardTitle className="mt-3">{selectedScene.name}</CardTitle><CardDescription className="mt-1">{selectedScene.locality || "No locality recorded"} · {selectedScene.members.length - 1} context features</CardDescription></div>
                  <div className="flex gap-2"><Button onClick={() => onReview(selectedScene)}><ArrowRight /> Review comparison</Button><Button aria-label="Archive scene" onClick={() => { if (window.confirm(`Archive ${selectedScene.name}?`)) void onArchive(selectedScene) }} size="icon" variant="outline"><Archive /></Button></div>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <GeometryStage className="min-h-[420px] rounded-none border-0" comparisonLabels={false} context={contextFor(selectedScene)} mode="overlay" original={target.current_revision.geometry} swipe={50} />
                <div className="flex flex-wrap gap-2 border-t p-4">{selectedScene.members.map((member) => <Badge key={member.feature_id} variant={member.role === "target" ? "default" : "outline"}>{member.role} · {member.feature.name}</Badge>)}</div>
              </CardContent>
            </Card>
          ) : (
            <Card><CardContent className="grid min-h-[360px] place-content-center text-center"><MapPinned className="mx-auto size-8 text-muted-foreground" /><p className="mt-3 font-medium">No contextual scenes yet</p><p className="mt-1 text-sm text-muted-foreground">Compose the first scene from your existing features.</p></CardContent></Card>
          )}

          {scenes.length > 1 && <div className="grid gap-3 md:grid-cols-2">{scenes.map((scene) => <button className="rounded-xl border bg-card p-4 text-left shadow-sm transition hover:border-[#00796f]/50" key={scene.id} onClick={() => onSelect(scene)}><div className="flex items-center justify-between gap-3"><span className="truncate font-medium">{scene.name}</span><Badge variant="outline">{regionLabel(scene.region)}</Badge></div><p className="mt-2 text-xs text-muted-foreground">{scene.locality || "Unspecified locality"} · {scene.members.length - 1} context</p></button>)}</div>}
        </div>
      </div>
    </div>
  )
}
