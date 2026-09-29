import { useState } from "react"
import { Boxes, CheckCircle2, FileArchive, Fingerprint, PackageCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { DatasetVersion } from "@/lib/api"

type VersionsViewProps = {
  versions: DatasetVersion[]
  featureCount: number
  onPublish: (splitSeed: number) => Promise<void>
}

export function VersionsView({ versions, featureCount, onPublish }: VersionsViewProps) {
  const [seed, setSeed] = useState(4812)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function publish() {
    try {
      setPending(true)
      setError(null)
      await onPublish(seed)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not publish dataset")
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-5xl p-4 lg:p-6">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#00796f]">Immutable exports</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">Dataset versions</h1>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Publishing freezes the current revision of every active feature into checksummed Parquet. Existing versions never change.</p>
      <div className="mt-6 grid min-w-0 gap-5 md:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <div className="grid size-10 place-items-center rounded-lg bg-[#e8f4f1] text-[#00796f]"><PackageCheck className="size-5" /></div>
            <CardTitle className="pt-2">Publish snapshot</CardTitle>
            <CardDescription>{featureCount} active features will be split by batch to avoid train/test leakage.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2"><Label htmlFor="split-seed">Split seed</Label><Input id="split-seed" onChange={(event) => setSeed(event.target.valueAsNumber)} type="number" value={seed} /></div>
            <Button className="w-full bg-[#006b63] hover:bg-[#005a53]" disabled={!featureCount || pending} onClick={publish}><FileArchive /> {pending ? "Publishing…" : "Publish version"}</Button>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </CardContent>
        </Card>
        <div className="min-w-0 space-y-3">
          {versions.map((version) => (
            <Card className="min-w-0" key={version.id}>
              <CardContent className="flex items-start gap-4 p-5">
                <div className="grid size-11 shrink-0 place-items-center rounded-xl border bg-muted"><Boxes className="size-5" /></div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2"><CardTitle className="text-base">Version {version.version}</CardTitle><Badge variant="secondary"><CheckCircle2 /> verified</Badge></div>
                  <p className="mt-2 truncate font-mono text-xs text-muted-foreground">{version.manifest_path}</p>
                  <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
                    <span>seed {version.split_seed}</span>
                    <span className="flex items-center gap-1"><Fingerprint className="size-3" /> {version.manifest_checksum.slice(0, 16)}…</span>
                    <span>{new Date(version.created_at).toLocaleString()}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
          {!versions.length && <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">No published versions yet.</CardContent></Card>}
        </div>
      </div>
    </div>
  )
}
