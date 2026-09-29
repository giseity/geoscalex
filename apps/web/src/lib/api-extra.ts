export type { Candidate, Feature } from "./api"
export type AnnotationChoice = "A" | "B" | "equal" | "artifact"
export type ReviewDraft = {
  choice: AnnotationChoice
  acceptability: import("./api").Acceptability
  failureTags: import("./api").FailureTag[]
  comment: string
}
