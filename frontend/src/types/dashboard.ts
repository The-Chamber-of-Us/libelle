export type ParserState = 'pending' | 'complete'
export type ResolverState = 'not_run' | 'resolved' | 'zero_matches'
export type ParserResultState =
  | 'not_yet_run'
  | 'failed'
  | 'skipped'
  | 'empty_success'
  | 'available'
export type ResolverResultState =
  | 'not_yet_run'
  | 'failed'
  | 'unavailable_upstream'
  | 'empty_success'
  | 'available'
export type SnapshotErrorState = 'none' | 'present' | 'unavailable'
export type OpsStatus =
  | 'new'
  | 'reviewed'
  | 'contacted'
  | 'in_progress'
  | 'paused'
  | 'closed'

export interface SnapshotRawData {
  created_at: string
  full_name: string
  email: string
  location_raw: string
  timezone: string
  skills_raw: string
  interests: string
  experience_level: string
  availability: string
  motivation: string
  linkedin_url: string
  github_url: string
  consent_given: string
  resume_filename: string
  resume_status: string
}

export interface SnapshotParsedData {
  parser_state: ParserState
  parser_result_state: ParserResultState
  parser_run_id: string
  created_at: string
  parser_version: string
  parsed_skills_raw: string
  parsed_location_raw: string
  parser_confidence: string
  parser_confidence_score: number | null
}

export interface SnapshotResolvedData {
  resolver_state: ResolverState
  resolver_result_state: ResolverResultState
  resolver_version: string
  aliases_version: string
  resolved_skill_ids: string
  unknown_skills: string
  resolver_coverage: string
  resolver_coverage_score: number | null
}

export interface SnapshotOpsData {
  status: OpsStatus
  notes: string
  tags: string
  contact_tracking: string
  updated_at: string
  updated_by: string
}

export interface SnapshotErrorsData {
  error_state: SnapshotErrorState
  has_error: boolean
  latest_error_summary: string
  latest_error_stage: string
  latest_error_code: string
}

export interface ReviewerSubmissionSnapshot {
  submission_id: string
  raw: SnapshotRawData
  parsed: SnapshotParsedData
  resolved: SnapshotResolvedData
  ops: SnapshotOpsData
  errors: SnapshotErrorsData
}

export interface OpsStatusListResponse {
  statuses: OpsStatus[]
}

export interface OpsDashboardUpdateResponse {
  status: 'updated'
  submission_id: string
  ops: SnapshotOpsData
}
