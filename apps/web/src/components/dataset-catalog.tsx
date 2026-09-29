import { ArrowRight, Database, FolderKanban, HardDrive } from "lucide-react"

import type { DatasetGroup } from "@/components/lab-sidebar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { Dataset } from "@/lib/api"

type DatasetCatalogProps = {
  groups: DatasetGroup[]
  selectedDatasetId: string
  onOpen: (dataset: Dataset) => void
}

export function DatasetCatalog({ groups, selectedDatasetId, onOpen }: DatasetCatalogProps) {
  const datasetCount = groups.reduce((count, group) => count + group.datasets.length, 0)

  return (
    <main className="mx-auto w-full max-w-6xl p-4 lg:p-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#00796f]">Dataset library</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Choose the material you want to study</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Workspaces organize related datasets. Opening one keeps its features, contextual scenes, imports, generators, and immutable versions together.</p>
        </div>
        <div className="flex gap-2">
          <Badge className="gap-1.5 px-3 py-1.5" variant="outline"><FolderKanban /> {groups.length} workspaces</Badge>
          <Badge className="gap-1.5 px-3 py-1.5" variant="outline"><Database /> {datasetCount} datasets</Badge>
        </div>
      </div>

      <div className="mt-8 space-y-8">
        {groups.map((group) => (
          <section key={group.workspace.id}>
            <div className="mb-3 flex items-center gap-2">
              <div className="grid size-8 place-items-center rounded-lg bg-[#e4f2ee] text-[#006b63]"><FolderKanban className="size-4" /></div>
              <div><h2 className="font-semibold">{group.workspace.name}</h2><p className="text-xs text-muted-foreground">{group.datasets.length} datasets</p></div>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {group.datasets.map((dataset) => {
                const selected = dataset.id === selectedDatasetId
                return (
                  <Card className={selected ? "border-[#4f9e94] shadow-sm ring-1 ring-[#4f9e94]/25" : "transition hover:border-slate-400 hover:shadow-sm"} key={dataset.id}>
                    <CardHeader>
                      <div className="flex items-start justify-between gap-3">
                        <div className="grid size-10 place-items-center rounded-xl border bg-muted"><Database className="size-5" /></div>
                        {selected && <Badge className="bg-[#e4f2ee] text-[#006b63]" variant="secondary">Current</Badge>}
                      </div>
                      <CardTitle className="pt-2 text-lg">{dataset.name}</CardTitle>
                      <CardDescription className="min-h-10 leading-5">{dataset.description || "No description has been added."}</CardDescription>
                    </CardHeader>
                    <CardContent className="flex items-center justify-between gap-3">
                      <span className="flex items-center gap-1.5 text-xs text-muted-foreground"><HardDrive className="size-3.5" /> Local SQLite</span>
                      <Button onClick={() => onOpen(dataset)} size="sm" variant={selected ? "secondary" : "default"}>Open <ArrowRight /></Button>
                    </CardContent>
                  </Card>
                )
              })}
              {!group.datasets.length && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">No datasets in this workspace.</div>}
            </div>
          </section>
        ))}
      </div>
    </main>
  )
}
