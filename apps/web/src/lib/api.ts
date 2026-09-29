export type Position = [number, number]

export type Geometry =
  | { type: "LineString"; coordinates: Position[] }
  | { type: "Polygon"; coordinates: Position[][] }

export type Workspace = { id: string; name: string; created_at: string }
export type Dataset = {
  id: string
  workspace_id: string
  name: string
  description: string
  created_at: string
}
export type Batch = {
  id: string
  dataset_id: string
  name: string
  source: string
  provenance: Record<string, unknown>
  created_at: string
}
export type Revision = {
  id: string
  feature_id: string
  parent_revision_id: string | null
  sequence: number
  geometry: Geometry
  properties: Record<string, unknown>
  coordinate_space: "geographic" | "local"
  crs: string | null
  checksum: string
  change_kind: string
  created_at: string
}
export type Feature = {
  id: string
  dataset_id: string
  batch_id: string | null
  name: string
  source: string
  archived_at: string | null
  current_revision: Revision
  created_at: string
}
export type Candidate = {
  id: string
  revision_id: string
  method: string
  method_version: string
  parameters: { tolerance: number | null; vertex_budget: number | null }
  geometry: Geometry
  vertex_scores: Array<number | null>
  protected_mask: boolean[]
  metrics: Record<string, number | string | boolean | number[]>
  created_at: string
}
export type GeneratorDefinition = {
  id: string
  name: string
  version: string
  description: string
  geometry_type: string
  parameter_schema: {
    properties?: Record<
      string,
      { title?: string; type?: string; default?: number; minimum?: number; maximum?: number }
    >
  }
  code_hash: string
}
export type Job = {
  id: string
  kind: string
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled"
  payload: Record<string, unknown>
  progress: number
  logs: string[]
  result: Record<string, unknown>
  error: string | null
  cancel_requested: boolean
  created_at: string
  started_at: string | null
  finished_at: string | null
}
export type DatasetVersion = {
  id: string
  dataset_id: string
  version: number
  manifest_path: string
  manifest_checksum: string
  split_seed: number
  created_at: string
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  })
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(payload?.detail ?? `${response.status} ${response.statusText}`)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  workspaces: () => request<Workspace[]>("/workspaces"),
  createWorkspace: (name: string) =>
    request<Workspace>("/workspaces", { method: "POST", body: JSON.stringify({ name }) }),
  datasets: (workspaceId: string) =>
    request<Dataset[]>(`/datasets?workspace_id=${workspaceId}`),
  createDataset: (workspaceId: string, name: string, description = "") =>
    request<Dataset>("/datasets", {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, name, description }),
    }),
  batches: (datasetId: string) => request<Batch[]>(`/datasets/${datasetId}/batches`),
  features: (datasetId: string) => request<Feature[]>(`/datasets/${datasetId}/features`),
  createFeature: (body: {
    dataset_id: string
    batch_id?: string | null
    name: string
    geometry: Geometry
    properties?: Record<string, unknown>
    coordinate_space?: "geographic" | "local"
    crs?: string | null
    source?: string
  }) => request<Feature>("/features", { method: "POST", body: JSON.stringify(body) }),
  addRevision: (featureId: string, geometry: Geometry, changeKind = "edit") =>
    request<Feature>(`/features/${featureId}/revisions`, {
      method: "POST",
      body: JSON.stringify({ geometry, change_kind: changeKind }),
    }),
  revisions: (featureId: string) => request<Revision[]>(`/features/${featureId}/revisions`),
  restoreRevision: (featureId: string, revisionId: string) =>
    request<Feature>(`/features/${featureId}/revisions/${revisionId}/restore`, {
      method: "POST",
    }),
  addHole: (featureId: string, geometry: Geometry) =>
    request<Feature>(`/features/${featureId}/holes`, {
      method: "POST",
      body: JSON.stringify({ hole: geometry }),
    }),
  duplicateFeature: (featureId: string) =>
    request<Feature>(`/features/${featureId}/duplicate`, {
      method: "POST",
      body: JSON.stringify({ name: null }),
    }),
  archiveFeature: (featureId: string) =>
    request<Feature>(`/features/${featureId}/archive`, { method: "POST" }),
  candidates: (revisionId: string) =>
    request<Candidate[]>(`/revisions/${revisionId}/candidates`),
  createCandidate: (revisionId: string, method: string, vertexBudget: number) =>
    request<Candidate>("/candidates", {
      method: "POST",
      body: JSON.stringify({
        revision_id: revisionId,
        method,
        vertex_budget: vertexBudget,
      }),
    }),
  annotate: (body: {
    dataset_id: string
    feature_id: string
    revision_id: string
    candidate_a_id: string
    candidate_b_id: string
    choice: "A" | "B" | "equal" | "artifact"
    viewport?: Record<string, unknown>
    comment?: string
  }) => request("/annotations", { method: "POST", body: JSON.stringify(body) }),
  generators: () => request<GeneratorDefinition[]>("/generators"),
  runGenerator: (body: {
    dataset_id: string
    generator_id: string
    batch_name: string
    count: number
    seed: number
    parameters: Record<string, number>
  }) => request<Job>("/generator-runs", { method: "POST", body: JSON.stringify(body) }),
  jobs: () => request<Job[]>("/jobs"),
  cancelJob: (jobId: string) => request<Job>(`/jobs/${jobId}/cancel`, { method: "POST" }),
  importGeoJson: (datasetId: string, batchName: string, featureCollection: unknown) =>
    request<{ imported: number; rejected: Array<{ index: number; reason: string }> }>(
      "/imports/geojson",
      {
        method: "POST",
        body: JSON.stringify({
          dataset_id: datasetId,
          batch_name: batchName,
          feature_collection: featureCollection,
        }),
      },
    ),
  versions: (datasetId: string) =>
    request<DatasetVersion[]>(`/datasets/${datasetId}/versions`),
  publish: (datasetId: string, splitSeed: number) =>
    request<DatasetVersion>(`/datasets/${datasetId}/versions`, {
      method: "POST",
      body: JSON.stringify({ split_seed: splitSeed }),
    }),
}
