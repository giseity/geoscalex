import { useRef, useState } from "react"
import { FileJson2, FileUp, ShieldCheck } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

const example = `{
  "type": "FeatureCollection",
  "features": []
}`

type ImportViewProps = {
  onImport: (batchName: string, collection: unknown) => Promise<{ imported: number; rejected: Array<{ index: number; reason: string }> }>
}

export function ImportView({ onImport }: ImportViewProps) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [batchName, setBatchName] = useState("GeoJSON import")
  const [content, setContent] = useState(example)
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function importData() {
    try {
      setPending(true)
      setError(null)
      setMessage(null)
      const result = await onImport(batchName, JSON.parse(content))
      setMessage(`Imported ${result.imported} features${result.rejected.length ? `; ${result.rejected.length} rejected` : ""}.`)
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
      <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">The API validates every geometry independently. Valid LineStrings and Polygons are kept even when other records are rejected.</p>
      <div className="mt-6 grid gap-5 md:grid-cols-[1fr_300px]">
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
              <input
                accept=".geojson,.json,application/geo+json,application/json"
                className="hidden"
                onChange={async (event) => {
                  const file = event.target.files?.[0]
                  if (file) setContent(await file.text())
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
          {message && <Alert><AlertTitle>Import complete</AlertTitle><AlertDescription>{message}</AlertDescription></Alert>}
          {error && <Alert variant="destructive"><AlertTitle>Import failed</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
        </div>
      </div>
    </div>
  )
}
