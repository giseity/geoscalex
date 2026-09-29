import { useEffect, useState } from "react"
import { CircleDotDashed, RotateCcw, Trash2 } from "lucide-react"

import { MapGeometryEditor } from "@/components/map-geometry-editor"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { Geometry } from "@/lib/api"
import { vertexCount } from "@/lib/geometry"

type GeometryEditorProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  initialGeometry?: Geometry
  referenceGeometry?: Geometry
  title: string
  submitLabel: string
  onSave: (name: string, geometry: Geometry) => Promise<void>
  geometryTypeLocked?: "Polygon"
}

export function GeometryEditor({
  open,
  onOpenChange,
  initialGeometry,
  referenceGeometry,
  title,
  submitLabel,
  onSave,
  geometryTypeLocked,
}: GeometryEditorProps) {
  const [draft, setDraft] = useState<Geometry | undefined>(initialGeometry)
  const [mapSeed, setMapSeed] = useState<Geometry | undefined>(initialGeometry)
  const [mapKey, setMapKey] = useState(0)
  const [geometryType, setGeometryType] = useState<"LineString" | "Polygon">(
    geometryTypeLocked ?? initialGeometry?.type ?? "LineString",
  )
  const [name, setName] = useState("Untitled geometry")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setDraft(initialGeometry)
    setMapSeed(initialGeometry)
    setMapKey((key) => key + 1)
    setGeometryType(geometryTypeLocked ?? initialGeometry?.type ?? "LineString")
    setError(null)
  }, [geometryTypeLocked, initialGeometry, open])

  async function save() {
    try {
      if (!draft) throw new Error("Finish drawing a geometry before saving")
      setSaving(true)
      setError(null)
      await onSave(name.trim() || "Untitled geometry", draft)
      onOpenChange(false)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save geometry")
    } finally {
      setSaving(false)
    }
  }

  function reload(seed?: Geometry) {
    setDraft(seed)
    setMapSeed(seed)
    setMapKey((key) => key + 1)
  }

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent className="w-full gap-0 overflow-hidden p-0 sm:max-w-4xl">
        <DialogHeader className="border-b px-6 py-5">
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Use the local map canvas to draw or reshape vertices. The background does not require a tile service.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-5 p-6 md:grid-cols-[220px_1fr]">
          <div className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="geometry-name">Name</Label>
              <Input id="geometry-name" onChange={(event) => setName(event.target.value)} value={name} />
            </div>
            <div className="space-y-2">
              <Label>Geometry type</Label>
              <Select
                disabled={Boolean(geometryTypeLocked || initialGeometry)}
                onValueChange={(value: "LineString" | "Polygon") => {
                  setGeometryType(value)
                  reload()
                }}
                value={geometryType}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="LineString">LineString</SelectItem>
                  <SelectItem value="Polygon">Polygon</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">
              <div className="flex items-center gap-2 font-medium text-foreground">
                <CircleDotDashed className="size-4" /> {vertexCount(draft)} vertices
              </div>
              <p className="mt-2">Coordinates stay in the feature's native coordinate space.</p>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Button onClick={() => reload(initialGeometry)} size="sm" variant="outline"><RotateCcw /> Reset</Button>
              <Button onClick={() => reload()} size="sm" variant="outline"><Trash2 /> Clear</Button>
            </div>
          </div>
          <MapGeometryEditor
            geometry={mapSeed}
            geometryType={geometryType}
            key={mapKey}
            onChange={setDraft}
            referenceGeometry={referenceGeometry}
          />
        </div>
        {error && <p className="px-6 pb-2 text-sm text-destructive">{error}</p>}
        <DialogFooter className="border-t px-6 py-4">
          <Button disabled={saving || !draft} onClick={save}>{saving ? "Saving…" : submitLabel}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
