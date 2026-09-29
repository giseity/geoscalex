import { useRef, useState } from "react"
import { FileJson2, FileUp, ShieldCheck } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import type { GeoJsonImportOptions, GeoJsonImportResult } from "@/lib/api"

const example = `{
  "type": "FeatureCollection",
  "features": []
}`

type ImportViewProps = {
  onImport: (options: GeoJsonImportOptions, collection: unknown) => Promise<GeoJsonImportResult>
}

export function ImportView({ onImport }: ImportViewProps) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [batchName, setBatchName] = useState("GeoJSON import")
  const [sourceName, setSourceName] = useState("geojson")
  const [sourceUri, setSourceUri] = useState("")
  const [sourceLicense, setSourceLicense] = useState("")
  const [acquiredAt, setAcquiredAt] = useState("")
  const [sourceFileName, setSourceFileName] = useState("")
  const [coordinateSpace, setCoordinateSpace] = useState<"geographic" | "local">("geographic")
  const [crs, setCrs] = useState("EPSG:4326")
  const [sourceIdField, setSourceIdField] = useState("")
  const [splitGroupField, setSplitGroupField] = useState("")
  const [gridSize, setGridSize] = useState(0.25)
  const [maxFeatures, setMaxFeatures] = useState(10_000)
  const [seed, setSeed] = useState(4812)
  const [explodeMulti, setExplodeMulti] = useState(true)
  const [content, setContent] = useState(example)
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState<GeoJsonImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function importData() {
    try {
      setPending(true)
      setError(null)
      setResult(null)
      setResult(await onImport({
        batch_name: batchName,
        coordinate_space: coordinateSpace,
        crs: crs.trim() || null,
        source_name: sourceName,
        source_uri: sourceUri,
        source_license: sourceLicense,
        acquired_at: acquiredAt,
        source_file_name: sourceFileName,
        source_id_field: sourceIdField.trim() || null,
        split_group_field: splitGroupField.trim() || null,
        split_grid_size: gridSize,
        explode_multi: explodeMulti,
        max_features: maxFeatures,
        seed,
      }, JSON.parse(content)))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Import failed")
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-5xl p-4 lg:p-6">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#00796f]">Ingest</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">Import GeoJSON</h1>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">The API validates every geometry independently, records source provenance, and assigns leakage-safe split groups before publication.</p>
      <div className="mt-6 grid gap-5 md:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><FileJson2 className="size-5 text-[#00796f]" /> FeatureCollection</CardTitle>
            <CardDescription>Paste JSON or load a local <code>.geojson</code> file.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea className="min-h-[420px] font-mono text-xs leading-5" onChange={(event) => setContent(event.target.value)} spellCheck={false} value={content} />
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Import settings</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2"><Label htmlFor="import-batch">Batch name</Label><Input id="import-batch" onChange={(event) => setBatchName(event.target.value)} value={batchName} /></div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2"><Label htmlFor="import-source">Source name</Label><Input id="import-source" onChange={(event) => setSourceName(event.target.value)} value={sourceName} /></div>
                <div className="space-y-2"><Label htmlFor="import-date">Acquired</Label><Input id="import-date" onChange={(event) => setAcquiredAt(event.target.value)} type="date" value={acquiredAt} /></div>
              </div>
              <div className="space-y-2"><Label htmlFor="import-uri">Source URI</Label><Input id="import-uri" onChange={(event) => setSourceUri(event.target.value)} placeholder="https://…" value={sourceUri} /></div>
              <div className="space-y-2"><Label htmlFor="import-license">License declaration</Label><Input id="import-license" onChange={(event) => setSourceLicense(event.target.value)} placeholder="Public domain, ODbL…" value={sourceLicense} /></div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2"><Label>Coordinate space</Label><Select onValueChange={(value) => { const space = value as "geographic" | "local"; setCoordinateSpace(space); if (space === "geographic" && !crs) setCrs("EPSG:4326") }} value={coordinateSpace}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="geographic">Geographic</SelectItem><SelectItem value="local">Local</SelectItem></SelectContent></Select></div>
                <div className="space-y-2"><Label htmlFor="import-crs">CRS</Label><Input id="import-crs" onChange={(event) => setCrs(event.target.value)} placeholder="EPSG:4326" value={crs} /></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2"><Label htmlFor="import-id-field">Source ID property</Label><Input id="import-id-field" onChange={(event) => setSourceIdField(event.target.value)} placeholder="Optional" value={sourceIdField} /></div>
                <div className="space-y-2"><Label htmlFor="import-group-field">Split group property</Label><Input id="import-group-field" onChange={(event) => setSplitGroupField(event.target.value)} placeholder="Optional" value={splitGroupField} /></div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-2"><Label htmlFor="import-grid">Grid size</Label><Input id="import-grid" min="0.000001" onChange={(event) => setGridSize(event.target.valueAsNumber || 0.25)} step="any" type="number" value={gridSize} /></div>
                <div className="space-y-2"><Label htmlFor="import-cap">Max features</Label><Input id="import-cap" min="1" onChange={(event) => setMaxFeatures(event.target.valueAsNumber || 1)} type="number" value={maxFeatures} /></div>
                <div className="space-y-2"><Label htmlFor="import-seed">Seed</Label><Input id="import-seed" onChange={(event) => setSeed(event.target.valueAsNumber || 0)} type="number" value={seed} /></div>
              </div>
              <div className="flex items-center justify-between gap-3 rounded-md border p-3"><div><Label htmlFor="explode-multi">Explode multi-geometries</Label><p className="mt-1 text-xs text-muted-foreground">Create one feature per line or polygon part.</p></div><Switch checked={explodeMulti} id="explode-multi" onCheckedChange={setExplodeMulti} /></div>
              <input
                accept=".geojson,.json,application/geo+json,application/json"
                className="hidden"
                onChange={async (event) => {
                  const file = event.target.files?.[0]
                  if (file) { setContent(await file.text()); setSourceFileName(file.name) }
                }}
                ref={fileRef}
                type="file"
              />
              <Button className="w-full" onClick={() => fileRef.current?.click()} variant="outline"><FileUp /> Choose file</Button>
              <Button className="w-full bg-[#006b63] hover:bg-[#005a53]" disabled={pending} onClick={importData}>{pending ? "Validating…" : "Import batch"}</Button>
            </CardContent>
          </Card>
          <Alert className="border-[#acd1c9] bg-[#e8f4f1]">
            <ShieldCheck className="text-[#00796f]" />
            <AlertTitle>Safe by default</AlertTitle>
            <AlertDescription>Multi-geometries and invalid rings are reported, never silently coerced.</AlertDescription>
          </Alert>
          {result && <Alert><AlertTitle>Import complete</AlertTitle><AlertDescription>{result.imported} imported · {result.eligible} eligible · {result.sampled_out} sampled out · {result.rejected.length} rejected</AlertDescription></Alert>}
          {result?.rejected.length ? <Card><CardHeader><CardTitle className="text-sm">Rejected records</CardTitle></CardHeader><CardContent className="max-h-40 space-y-2 overflow-auto text-xs">{result.rejected.slice(0, 25).map((item, index) => <p key={`${item.index}-${item.part_index ?? "all"}-${index}`}><span className="font-medium">#{item.index}{item.part_index === undefined ? "" : ` · part ${item.part_index}`}</span> {item.reason}</p>)}</CardContent></Card> : null}
          {error && <Alert variant="destructive"><AlertTitle>Import failed</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
        </div>
      </div>
    </div>
  )
}
