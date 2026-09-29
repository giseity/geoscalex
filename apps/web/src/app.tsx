import { lazy, Suspense, useEffect, useMemo, useState } from "react"
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query"
import { CircleDot, PanelLeft, PanelRight, RefreshCw } from "lucide-react"

import { CompareView } from "@/components/compare-view"
import { GenerateView } from "@/components/generate-view"
import { ImportView } from "@/components/import-view"
import { InspectorSidebar } from "@/components/inspector-sidebar"
import { LabSidebar, type LabView } from "@/components/lab-sidebar"
import { Onboarding } from "@/components/onboarding"
import { VersionsView } from "@/components/versions-view"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { api, type Candidate, type Dataset, type Feature, type Geometry, type Scene, type SimplificationBudget } from "@/lib/api"
import type { ReviewDraft } from "@/lib/api-extra"
import { vertexCount } from "@/lib/geometry"

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
})

const GeometryEditor = lazy(() =>
  import("@/components/geometry-editor").then((module) => ({ default: module.GeometryEditor })),
)

const ScenesView = lazy(() =>
  import("@/components/scenes-view").then((module) => ({ default: module.ScenesView })),
)

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider><DatasetLab /></TooltipProvider>
    </QueryClientProvider>
  )
}

function DatasetLab() {
  const workspacesQuery = useQuery({ queryKey: ["workspaces"], queryFn: api.workspaces })
  const workspace = workspacesQuery.data?.[0]
  const datasetsQuery = useQuery({
    queryKey: ["datasets", workspace?.id],
    queryFn: () => api.datasets(workspace!.id),
    enabled: Boolean(workspace),
  })
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(
    () => localStorage.getItem("geoscalex.dataset"),
  )
  const dataset = datasetsQuery.data?.find((item) => item.id === selectedDatasetId) ?? datasetsQuery.data?.[0]

  useEffect(() => {
    if (!dataset) return
    setSelectedDatasetId(dataset.id)
    localStorage.setItem("geoscalex.dataset", dataset.id)
  }, [dataset])

  if (workspacesQuery.isLoading || (workspace && datasetsQuery.isLoading)) {
    return <main className="grid min-h-screen place-content-center bg-[#e8e4da] text-center"><RefreshCw className="mx-auto size-5 animate-spin text-[#00796f]" /><p className="mt-3 text-sm font-medium">Opening local Dataset Lab…</p></main>
  }
  if (workspacesQuery.error || datasetsQuery.error) {
    const error = workspacesQuery.error ?? datasetsQuery.error
    return <main className="grid min-h-screen place-content-center bg-[#e8e4da] p-6"><Alert variant="destructive"><AlertDescription>{error instanceof Error ? error.message : "The local API is unavailable."}</AlertDescription></Alert></main>
  }
  if (!workspace || !dataset) {
    return (
      <Onboarding
        onCreate={async (workspaceName, datasetName) => {
          const activeWorkspace = workspace ?? (await api.createWorkspace(workspaceName))
          const created = await api.createDataset(activeWorkspace.id, datasetName, "Created in Dataset Lab")
          setSelectedDatasetId(created.id)
          await queryClient.invalidateQueries()
        }}
        workspaceExists={Boolean(workspace)}
      />
    )
  }
  return <WorkspaceShell dataset={dataset} datasets={datasetsQuery.data ?? []} onDatasetChange={(next) => setSelectedDatasetId(next.id)} />
}

type WorkspaceShellProps = {
  dataset: Dataset
  datasets: Dataset[]
  onDatasetChange: (dataset: Dataset) => void
}

function WorkspaceShell({ dataset, datasets, onDatasetChange }: WorkspaceShellProps) {
  const [view, setView] = useState<LabView>("compare")
  const [selectedFeatureId, setSelectedFeatureId] = useState<string | null>(null)
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null)
  const [budget, setBudget] = useState(12)
  const [budgetKind, setBudgetKind] = useState<SimplificationBudget["kind"]>("vertex-count")
  const [retentionRatio, setRetentionRatio] = useState(0.5)
  const [methodA, setMethodA] = useState("douglas-peucker")
  const [methodB, setMethodB] = useState("visvalingam-whyatt")
  const [candidateBusy, setCandidateBusy] = useState(false)
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)
  const [editor, setEditor] = useState<"new" | "edit" | "hole" | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const featuresQuery = useQuery({ queryKey: ["features", dataset.id], queryFn: () => api.features(dataset.id) })
  const batchesQuery = useQuery({ queryKey: ["batches", dataset.id], queryFn: () => api.batches(dataset.id) })
  const generatorsQuery = useQuery({ queryKey: ["generators"], queryFn: api.generators })
  const methodsQuery = useQuery({ queryKey: ["simplification-methods"], queryFn: api.simplificationMethods })
  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs,
    refetchInterval: (query) => query.state.data?.some((job) => job.status === "queued" || job.status === "running") ? 1000 : false,
  })
  const versionsQuery = useQuery({ queryKey: ["versions", dataset.id], queryFn: () => api.versions(dataset.id) })
  const scenesQuery = useQuery({ queryKey: ["scenes", dataset.id], queryFn: () => api.scenes(dataset.id) })
  const jobStateFingerprint = (jobsQuery.data ?? []).map((job) => `${job.id}:${job.status}`).join("|")
  const features = featuresQuery.data ?? []
  const selectedFeature = features.find((feature) => feature.id === selectedFeatureId) ?? features[0]
  const sourceVertexCount = vertexCount(selectedFeature?.current_revision.geometry)
  const minimumBudget = selectedFeature?.current_revision.geometry.type === "Polygon" ? 3 : 2
  const resolvedBudget = budgetKind === "vertex-count"
    ? Math.max(minimumBudget, Math.min(budget, sourceVertexCount || minimumBudget))
    : Math.max(minimumBudget, Math.min(sourceVertexCount, Math.floor(sourceVertexCount * retentionRatio + 0.5)))
  const scenes = scenesQuery.data ?? []
  const selectedScene = scenes.find((scene) => scene.id === selectedSceneId)
  const activeScene = selectedScene?.target_feature_id === selectedFeature?.id ? selectedScene : undefined
  const candidatesQuery = useQuery({
    queryKey: ["candidates", selectedFeature?.current_revision.id],
    queryFn: () => api.candidates(selectedFeature!.current_revision.id),
    enabled: Boolean(selectedFeature),
  })
  const revisionsQuery = useQuery({
    queryKey: ["revisions", selectedFeature?.id],
    queryFn: () => api.revisions(selectedFeature!.id),
    enabled: Boolean(selectedFeature),
  })

  useEffect(() => {
    if (!jobStateFingerprint) return
    void queryClient.invalidateQueries({ queryKey: ["features", dataset.id] })
    void queryClient.invalidateQueries({ queryKey: ["batches", dataset.id] })
    void queryClient.invalidateQueries({ queryKey: ["scenes", dataset.id] })
    void queryClient.invalidateQueries({ queryKey: ["candidates"] })
  }, [dataset.id, jobStateFingerprint])

  useEffect(() => {
    if (selectedFeature) {
      setSelectedFeatureId(selectedFeature.id)
      const minimum = selectedFeature.current_revision.geometry.type === "Polygon" ? 3 : 2
      setBudget(Math.min(12, Math.max(minimum, vertexCount(selectedFeature.current_revision.geometry))))
    } else setSelectedFeatureId(null)
  }, [selectedFeature?.id])

  const [candidateA, candidateB] = useMemo(() => {
    const candidates = candidatesQuery.data ?? []
    const matching = (method: string) => [...candidates].reverse().find((candidate) => candidate.method === method && candidate.resolved_vertex_budget === resolvedBudget)
    return [matching(methodA), matching(methodB)]
  }, [resolvedBudget, candidatesQuery.data, methodA, methodB])

  async function refreshFeatures(message?: string) {
    await queryClient.invalidateQueries({ queryKey: ["features", dataset.id] })
    await queryClient.invalidateQueries({ queryKey: ["batches", dataset.id] })
    await queryClient.invalidateQueries({ queryKey: ["revisions"] })
    await queryClient.invalidateQueries({ queryKey: ["scenes", dataset.id] })
    if (message) {
      setNotice(message)
      window.setTimeout(() => setNotice(null), 2600)
    }
  }

  async function buildCandidates() {
    if (!selectedFeature) return
    setCandidateBusy(true)
    try {
      const requestedBudget: SimplificationBudget = budgetKind === "vertex-count"
        ? { kind: "vertex-count", value: resolvedBudget }
        : { kind: "retention-ratio", value: retentionRatio }
      await Promise.all([...new Set([methodA, methodB])].map((method) =>
        api.runSimplification(selectedFeature.current_revision.id, method, requestedBudget),
      ))
      await jobsQuery.refetch()
      setNotice("Matched simplification queued")
    } finally { setCandidateBusy(false) }
  }

  async function saveGeometry(name: string, geometry: Geometry) {
    if (editor === "new") {
      const feature = await api.createFeature({ dataset_id: dataset.id, name, geometry, coordinate_space: "local", crs: null })
      await refreshFeatures("Geometry created")
      setSelectedFeatureId(feature.id)
    } else if (editor === "edit" && selectedFeature) {
      await api.addRevision(selectedFeature.id, geometry)
      await refreshFeatures("New immutable revision saved")
    } else if (editor === "hole" && selectedFeature) {
      await api.addHole(selectedFeature.id, geometry)
      await refreshFeatures("Interior ring added")
    }
  }

  const annotationCandidateA = candidateA as Candidate | undefined
  const annotationCandidateB = candidateB as Candidate | undefined

  return (
    <SidebarProvider onOpenChange={setLeftOpen} open={leftOpen}>
      <LabSidebar batches={batchesQuery.data ?? []} dataset={dataset} datasets={datasets} features={features} onDatasetChange={onDatasetChange} onFeatureChange={(feature: Feature) => { setSelectedSceneId(null); setSelectedFeatureId(feature.id) }} onNewFeature={() => setEditor("new")} onViewChange={setView} selectedFeatureId={selectedFeature?.id ?? null} view={view} />
      <SidebarProvider className="min-w-0 flex-1" onOpenChange={setRightOpen} open={rightOpen}>
        <SidebarInset className="min-w-0 bg-[#f4f2ec]">
          <header className="sticky top-0 z-20 flex h-[65px] items-center gap-3 border-b bg-background/90 px-3 backdrop-blur lg:px-5">
            <Button aria-label="Toggle dataset sidebar" onClick={() => setLeftOpen((open) => !open)} size="icon-sm" variant="ghost"><PanelLeft /></Button>
            <div className="h-5 w-px bg-border" />
            <div className="min-w-0"><p className="truncate text-sm font-semibold">{dataset.name}</p><p className="truncate text-[11px] text-muted-foreground">{view === "compare" ? activeScene?.name ?? selectedFeature?.name ?? "Workbench" : view}</p></div>
            <div className="ml-auto flex items-center gap-2">
              <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex"><CircleDot className="size-3 fill-emerald-500 text-emerald-600" /> localhost</span>
              <Button aria-label="Toggle inspector" onClick={() => setRightOpen((open) => !open)} size="icon-sm" variant="ghost"><PanelRight /></Button>
            </div>
          </header>
          {notice && <div className="fixed right-5 top-20 z-50 rounded-lg bg-slate-950 px-4 py-2 text-sm text-white shadow-xl">{notice}</div>}
          {view === "compare" && <CompareView candidateA={candidateA} candidateB={candidateB} feature={selectedFeature} labelA={methodsQuery.data?.find((method) => method.id === methodA)?.name} labelB={methodsQuery.data?.find((method) => method.id === methodB)?.name} scene={activeScene} onAnnotate={async (review: ReviewDraft) => {
            if (!selectedFeature || !annotationCandidateA || !annotationCandidateB) return
            if (activeScene) {
              await api.createSceneReview({ scene_id: activeScene.id, revision_id: selectedFeature.current_revision.id, candidate_a_id: annotationCandidateA.id, candidate_b_id: annotationCandidateB.id, choice: review.choice, acceptability: review.acceptability, failure_tags: review.failureTags, comment: review.comment, viewport: { ...activeScene.viewport, vertex_budget: resolvedBudget } })
              setNotice("Contextual review recorded")
            } else {
              await api.annotate({ dataset_id: dataset.id, feature_id: selectedFeature.id, revision_id: selectedFeature.current_revision.id, candidate_a_id: annotationCandidateA.id, candidate_b_id: annotationCandidateB.id, choice: review.choice, viewport: { mode: "workbench", vertex_budget: resolvedBudget } })
              setNotice("Preference recorded")
            }
          }} />}
          {view === "scenes" && <Suspense fallback={<div className="grid min-h-[calc(100vh-65px)] place-content-center text-sm text-muted-foreground">Opening scene builder…</div>}><ScenesView batches={batchesQuery.data ?? []} datasetId={dataset.id} features={features} jobs={jobsQuery.data ?? []} onArchive={async (scene: Scene) => { await api.archiveScene(scene.id); if (selectedSceneId === scene.id) setSelectedSceneId(null); await scenesQuery.refetch(); setNotice("Scene archived") }} onCancelExtraction={async (jobId) => { await api.cancelJob(jobId); await jobsQuery.refetch() }} onCreate={async (input) => { const scene = await api.createScene(input); await scenesQuery.refetch(); return scene }} onExtractionQueued={async () => { await jobsQuery.refetch(); setNotice("Scene extraction queued") }} onRefreshJobs={() => { void jobsQuery.refetch(); void scenesQuery.refetch() }} onReview={(scene: Scene) => { setSelectedSceneId(scene.id); setSelectedFeatureId(scene.target_feature_id); setView("compare") }} onSelect={(scene: Scene) => setSelectedSceneId(scene.id)} scenes={scenes} selectedSceneId={selectedSceneId} /></Suspense>}
          {view === "generate" && <GenerateView generators={generatorsQuery.data ?? []} jobs={jobsQuery.data ?? []} onCancel={async (jobId) => { await api.cancelJob(jobId); await jobsQuery.refetch() }} onRefresh={() => { void jobsQuery.refetch(); void featuresQuery.refetch() }} onRun={async (generatorId, batchName, count, seed, parameters) => {
            await api.runGenerator({ dataset_id: dataset.id, generator_id: generatorId, batch_name: batchName, count, seed, parameters })
            await jobsQuery.refetch(); setNotice("Generator run queued")
          }} />}
          {view === "import" && <ImportView onImport={async (batchName, collection) => { const result = await api.importGeoJson(dataset.id, batchName, collection); await refreshFeatures(); return result }} />}
          {view === "versions" && <VersionsView featureCount={features.length} onPublish={async (splitSeed) => { await api.publish(dataset.id, splitSeed); await versionsQuery.refetch() }} sceneCount={scenes.length} versions={versionsQuery.data ?? []} />}
        </SidebarInset>
        {view === "compare" && <InspectorSidebar budget={resolvedBudget} budgetKind={budgetKind} busy={candidateBusy} candidateA={candidateA} candidateB={candidateB} feature={selectedFeature} methodA={methodA} methodB={methodB} methods={methodsQuery.data ?? []} onAddHole={() => setEditor("hole")} onArchive={async () => { if (selectedFeature) { await api.archiveFeature(selectedFeature.id); await refreshFeatures("Feature archived") } }} onBudgetChange={setBudget} onBudgetKindChange={setBudgetKind} onBuildCandidates={() => { void buildCandidates() }} onDuplicate={async () => { if (selectedFeature) { const copy = await api.duplicateFeature(selectedFeature.id); await refreshFeatures("Feature duplicated"); setSelectedFeatureId(copy.id) } }} onEdit={() => setEditor("edit")} onMethodAChange={setMethodA} onMethodBChange={setMethodB} onRestoreRevision={async (revisionId) => { if (selectedFeature) { await api.restoreRevision(selectedFeature.id, revisionId); await refreshFeatures("Revision restored"); await revisionsQuery.refetch() } }} onRetentionRatioChange={setRetentionRatio} retentionRatio={retentionRatio} revisions={revisionsQuery.data ?? []} />}
      </SidebarProvider>
      {editor && (
        <Suspense fallback={null}>
          <GeometryEditor geometryTypeLocked={editor === "hole" ? "Polygon" : undefined} initialGeometry={editor === "edit" ? selectedFeature?.current_revision.geometry : undefined} onOpenChange={(open) => { if (!open) setEditor(null) }} onSave={saveGeometry} open referenceGeometry={editor === "hole" ? selectedFeature?.current_revision.geometry : undefined} submitLabel={editor === "new" ? "Create feature" : editor === "hole" ? "Add interior ring" : "Save revision"} title={editor === "new" ? "Draw a new geometry" : editor === "hole" ? "Draw a polygon hole" : "Edit feature geometry"} />
        </Suspense>
      )}
    </SidebarProvider>
  )
}
