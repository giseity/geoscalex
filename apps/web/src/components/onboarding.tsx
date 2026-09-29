import { useState } from "react"
import { Database, LoaderCircle, MapPinned } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

type OnboardingProps = {
  workspaceExists: boolean
  onCreate: (workspaceName: string, datasetName: string) => Promise<void>
}

export function Onboarding({ workspaceExists, onCreate }: OnboardingProps) {
  const [workspaceName, setWorkspaceName] = useState("Local workspace")
  const [datasetName, setDatasetName] = useState("Generalization study")
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function create() {
    try {
      setPending(true)
      setError(null)
      await onCreate(workspaceName, datasetName)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create the dataset")
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[#e8e4da] p-5 text-slate-950">
      <div className="absolute inset-0 opacity-40 [background-image:linear-gradient(#8c9a9320_1px,transparent_1px),linear-gradient(90deg,#8c9a9320_1px,transparent_1px)] [background-size:40px_40px]" />
      <Card className="relative w-full max-w-xl overflow-hidden border-slate-300 bg-[#f8f6ef] shadow-2xl shadow-slate-900/10">
        <div className="h-1.5 bg-gradient-to-r from-[#006b63] via-[#15a291] to-[#e1643f]" />
        <CardHeader className="space-y-4 px-8 pt-8">
          <div className="flex size-11 items-center justify-center rounded-xl bg-[#006b63] text-white">
            <MapPinned className="size-5" />
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-[#00796f]">GeoScaleX</p>
            <h1 className="text-3xl font-semibold tracking-tight">Create your local Dataset Lab</h1>
            <CardDescription className="mt-2 max-w-md text-sm leading-6">
              Geometry, revisions, annotations, and exports stay on this machine. No account or cloud storage is required.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 px-8 pb-8">
          {!workspaceExists && (
            <div className="space-y-2">
              <Label htmlFor="workspace-name">Workspace</Label>
              <Input id="workspace-name" onChange={(event) => setWorkspaceName(event.target.value)} value={workspaceName} />
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="dataset-name">First dataset</Label>
            <Input id="dataset-name" onChange={(event) => setDatasetName(event.target.value)} value={datasetName} />
          </div>
          <div className="flex items-start gap-3 rounded-lg border border-[#acd1c9] bg-[#e5f4f0] p-3 text-sm text-[#285c53]">
            <Database className="mt-0.5 size-4 shrink-0" />
            <span>SQLite metadata and versioned Parquet exports will be written to <code>.geoscalex/</code>.</span>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button className="w-full bg-[#006b63] hover:bg-[#005a53]" disabled={pending} onClick={create} size="lg">
            {pending && <LoaderCircle className="animate-spin" />}
            Open Dataset Lab
          </Button>
        </CardContent>
      </Card>
    </main>
  )
}
