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
  method_kind: "classical" | "llm" | "neural"
  job_id: string | null
  parameters: { tolerance: number | null; vertex_budget: number | null }
  requested_budget: SimplificationBudget | Record<string, never>
  resolved_vertex_budget: number | null
  geometry: Geometry
  vertex_scores: Array<number | null>
  protected_mask: boolean[]
  source_mapping: number[]
  provenance: Record<string, unknown>
  diagnostics: Record<string, unknown>
  metrics: Record<string, number | string | boolean | number[]>
  created_at: string
}
export type SimplificationBudget =
  | { kind: "vertex-count"; value: number }
  | { kind: "retention-ratio"; value: number }
export type SimplificationMethod = {
  id: string
  name: string
  version: string
  kind: "classical" | "llm" | "neural"
  geometry_types: Array<Geometry["type"]>
  supports_holes: boolean
  available: boolean
  unavailable_reason: string | null
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
export type SceneRole = "target" | "sibling" | "parent" | "child" | "background" | "obstacle"
export type SceneRegion = "europe" | "north-america" | "other"
export type SceneMember = {
  feature_id: string
  role: SceneRole
  importance: number
  z_order: number
  style: Record<string, unknown>
  feature: Feature
}
export type Scene = {
  id: string
  dataset_id: string
  name: string
  target_feature_id: string
  region: SceneRegion
  locality: string
  crs: string | null
  viewport: Record<string, unknown>
  style: Record<string, unknown>
  scale_denominator: number | null
  zoom: number | null
  provenance: Record<string, unknown>
  archived_at: string | null
  members: SceneMember[]
  created_at: string
}
export type Acceptability = "acceptable" | "unacceptable" | "unsure"
export type FailureTag =
  | "topology-failure"
  | "visual-collision"
  | "excessive-detail-loss"
  | "characteristic-shape-loss"
  | "context-inconsistency"
  | "displacement-needed"
export type SceneReview = {
  id: string
  scene_id: string
  revision_id: string
  candidate_a_id: string | null
  candidate_b_id: string | null
  choice: "A" | "B" | "equal" | "artifact"
  acceptability: Acceptability
  failure_tags: FailureTag[]
  viewport: Record<string, unknown>
  comment: string
  created_at: string
}
export type SceneExtractionInput = {
  dataset_id: string
  target_batch_id: string | null
  region: SceneRegion
  locality: string
  location_group_prefix: string
  scale_denominator: number
  style_preset: string
  radius: number
  max_context: number
  geometry_types: Array<"LineString" | "Polygon">
  max_scenes: number
  skip_existing_targets: boolean
}
export type SceneExtractionProposal = {
  target_feature_id: string
  target_name: string
  context_count: number
  roles: Partial<Record<SceneRole, number>>
  viewport: Record<string, unknown>
  location_group: string
}
export type SceneExtractionPreview = {
  eligible_targets: number
  proposed_scenes: number
  isolated_targets: number
  existing_targets: number
  incompatible_features: number
  role_counts: Partial<Record<SceneRole, number>>
  samples: SceneExtractionProposal[]
}

export type GeoJsonImportOptions = {
  batch_name: string
  coordinate_space: "geographic" | "local"
  crs: string | null
  source_name: string
  source_uri: string
  source_license: string
  acquired_at: string
  source_file_name: string
  source_id_field: string | null
  split_group_field: string | null
  split_grid_size: number
  explode_multi: boolean
  max_features: number
  seed: number
}

export type GeoJsonImportResult = {
  submitted: number
  eligible: number
  imported: number
  sampled_out: number
  rejected: Array<{ index: number; part_index?: number; reason: string }>
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
  simplificationMethods: () =>
    request<SimplificationMethod[]>("/simplification-methods"),
  runSimplification: (revisionId: string, method: string, budget: SimplificationBudget) =>
    request<Job>("/simplification-runs", {
      method: "POST",
      body: JSON.stringify({ revision_id: revisionId, method, budget }),
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
  importGeoJson: (datasetId: string, options: GeoJsonImportOptions, featureCollection: unknown) =>
    request<GeoJsonImportResult>(
      "/imports/geojson",
      {
        method: "POST",
        body: JSON.stringify({
          dataset_id: datasetId,
          ...options,
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
  scenes: (datasetId: string) => request<Scene[]>(`/datasets/${datasetId}/scenes`),
  createScene: (body: {
    dataset_id: string
    name: string
    target_feature_id: string
    region: SceneRegion
    locality: string
    crs?: string | null
    viewport?: Record<string, unknown>
    style?: Record<string, unknown>
    scale_denominator?: number | null
    zoom?: number | null
    provenance?: Record<string, unknown>
    members: Array<{
      feature_id: string
      role: Exclude<SceneRole, "target">
      importance?: number
      z_order?: number
      style?: Record<string, unknown>
    }>
  }) => request<Scene>("/scenes", { method: "POST", body: JSON.stringify(body) }),
  archiveScene: (sceneId: string) =>
    request<Scene>(`/scenes/${sceneId}/archive`, { method: "POST" }),
  sceneReviews: (sceneId: string) => request<SceneReview[]>(`/scenes/${sceneId}/reviews`),
  createSceneReview: (body: {
    scene_id: string
    revision_id: string
    candidate_a_id: string
    candidate_b_id: string
    choice: "A" | "B" | "equal" | "artifact"
    acceptability: Acceptability
    failure_tags: FailureTag[]
    viewport?: Record<string, unknown>
    comment?: string
  }) => request<SceneReview>("/scene-reviews", { method: "POST", body: JSON.stringify(body) }),
  previewSceneExtraction: (body: SceneExtractionInput) =>
    request<SceneExtractionPreview>("/scene-extractions/preview", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runSceneExtraction: (body: SceneExtractionInput) =>
    request<Job>("/scene-extractions", { method: "POST", body: JSON.stringify(body) }),
}
