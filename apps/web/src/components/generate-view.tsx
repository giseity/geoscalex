import { useEffect, useMemo, useState } from "react"
import { Beaker, CircleStop, Clock3, Play, RefreshCw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { GeneratorDefinition, Job } from "@/lib/api"

type GenerateViewProps = {
  generators: GeneratorDefinition[]
  jobs: Job[]
  onRun: (generatorId: string, batchName: string, count: number, seed: number, parameters: Record<string, number>) => Promise<void>
  onCancel: (jobId: string) => Promise<void>
  onRefresh: () => void
}

export function GenerateView({ generators, jobs, onRun, onCancel, onRefresh }: GenerateViewProps) {
  const [generatorId, setGeneratorId] = useState("")
  const [batchName, setBatchName] = useState("Synthetic study")
  const [count, setCount] = useState(25)
  const [seed, setSeed] = useState(4812)
  const [parameters, setParameters] = useState<Record<string, number>>({})
  const [pending, setPending] = useState(false)
  const selected = generators.find((generator) => generator.id === generatorId) ?? generators[0]
  const fields = useMemo(() => Object.entries(selected?.parameter_schema.properties ?? {}), [selected])

  useEffect(() => {
    if (!generatorId && generators[0]) setGeneratorId(generators[0].id)
  }, [generatorId, generators])

  useEffect(() => {
    if (!selected) return
    setParameters(Object.fromEntries(fields.map(([key, schema]) => [key, schema.default ?? schema.minimum ?? 1])))
    setBatchName(`${selected.name} study`)
  }, [fields, selected])

  async function run() {
    if (!selected) return
    setPending(true)
    try {
      await onRun(selected.id, batchName, count, seed, parameters)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-5 p-4 lg:grid-cols-[1fr_380px] lg:p-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#00796f]">Synthetic data</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Generator registry</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Every run records the generator version, code hash, parameters, and per-sample seed. Forms come from the Python parameter schema.</p>
        <div className="mt-6 grid gap-3 md:grid-cols-2">
          {generators.map((generator) => (
            <button
              className={`rounded-xl border p-4 text-left transition ${selected?.id === generator.id ? "border-[#168c80] bg-[#e8f4f1] shadow-sm" : "bg-card hover:border-slate-400"}`}
              key={generator.id}
              onClick={() => setGeneratorId(generator.id)}
              type="button"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold">{generator.name}</span>
                <Badge variant="outline">{generator.geometry_type}</Badge>
              </div>
              <p className="mt-2 text-sm leading-5 text-muted-foreground">{generator.description}</p>
            </button>
          ))}
        </div>

        <Card className="mt-5">
          <CardHeader>
            <CardTitle className="text-lg">Run history</CardTitle>
            <CardDescription>Queued work is processed by the local Python worker.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-end"><Button onClick={onRefresh} size="sm" variant="ghost"><RefreshCw /> Refresh</Button></div>
            {jobs.map((job) => (
              <div className="rounded-lg border p-3" key={job.id}>
                <div className="flex items-center gap-2">
                  <Badge variant={job.status === "failed" ? "destructive" : "secondary"}>{job.status}</Badge>
                  <span className="truncate text-sm font-medium">{String(job.payload.batch_name ?? "Generator run")}</span>
                  <span className="ml-auto font-mono text-xs text-muted-foreground">{job.id.slice(0, 8)}</span>
                </div>
                <Progress className="mt-3" value={job.progress * 100} />
                <p className="mt-2 truncate text-xs text-muted-foreground">{job.error ?? job.logs.at(-1) ?? "Waiting for worker"}</p>
                {(job.status === "queued" || job.status === "running") && (
                  <Button className="mt-2" onClick={() => onCancel(job.id)} size="sm" variant="outline"><CircleStop /> Cancel</Button>
                )}
              </div>
            ))}
            {!jobs.length && <p className="py-8 text-center text-sm text-muted-foreground">No generator runs yet.</p>}
          </CardContent>
        </Card>
      </div>

      <Card className="h-fit lg:sticky lg:top-20">
        <CardHeader>
          <div className="grid size-10 place-items-center rounded-lg bg-[#e8f4f1] text-[#00796f]"><Beaker className="size-5" /></div>
          <CardTitle className="pt-2">Configure run</CardTitle>
          <CardDescription>{selected?.description ?? "Choose a registered generator."}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Generator</Label>
            <Select onValueChange={setGeneratorId} value={selected?.id ?? ""}>
              <SelectTrigger><SelectValue placeholder="Choose generator" /></SelectTrigger>
              <SelectContent>{generators.map((generator) => <SelectItem key={generator.id} value={generator.id}>{generator.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-2"><Label htmlFor="batch-name">Batch name</Label><Input id="batch-name" onChange={(event) => setBatchName(event.target.value)} value={batchName} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2"><Label htmlFor="sample-count">Samples</Label><Input id="sample-count" min={1} onChange={(event) => setCount(event.target.valueAsNumber)} type="number" value={count} /></div>
            <div className="space-y-2"><Label htmlFor="seed">Seed</Label><Input id="seed" onChange={(event) => setSeed(event.target.valueAsNumber)} type="number" value={seed} /></div>
          </div>
          {fields.map(([key, schema]) => (
            <div className="space-y-2" key={key}>
              <Label htmlFor={`parameter-${key}`}>{schema.title ?? key}</Label>
              <Input
                id={`parameter-${key}`}
                max={schema.maximum}
                min={schema.minimum}
                onChange={(event) => setParameters((current) => ({ ...current, [key]: event.target.valueAsNumber }))}
                step="any"
                type="number"
                value={parameters[key] ?? ""}
              />
            </div>
          ))}
          <Button className="w-full bg-[#006b63] hover:bg-[#005a53]" disabled={!selected || pending} onClick={run} size="lg">
            {pending ? <Clock3 className="animate-pulse" /> : <Play />} Queue generation
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
