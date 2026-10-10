import React, { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ParserResults from './ParserResults'
import type { ReviewerSubmissionSnapshot } from '../types/dashboard'
import { getSubmissionHealthTone } from '../components/inbox/detailUtils'

function snapshot(overrides: Partial<ReviewerSubmissionSnapshot> = {}): ReviewerSubmissionSnapshot {
  return {
    submission_id: 'intake', source_state: 'present', coordination_state: 'unassessed', coordination: null,
    submission_health_state: 'pending_processing',
    raw: {
      full_name: 'Intake candidate', email: '', created_at: '', location_raw: '', timezone: '', skills_raw: '',
      interests: '', experience_level: '', availability: '', motivation: '', linkedin_url: '', github_url: '',
      consent_given: '', resume_filename: '', resume_status: 'uploaded'
    },
    parsed: {
      parser_state: 'pending', parser_result_state: 'not_yet_run', parser_run_id: '', created_at: '',
      parser_version: '', parsed_skills_raw: '', parsed_location_raw: '', parser_confidence: '', parser_confidence_score: null
    },
    resolved: {
      resolver_state: 'not_run', resolver_result_state: 'not_yet_run', resolver_version: '', aliases_version: '',
      resolved_skill_ids: '', unknown_skills: '', resolver_coverage: '', resolver_coverage_score: null
    },
    parser_job: null,
    ops: { status: 'paused', notes: '', tags: '', contact_tracking: '', updated_at: '', updated_by: '' },
    errors: { error_state: 'none', has_error: false, latest_error_summary: '', latest_error_stage: '', latest_error_code: '' },
    ...overrides
  }
}

function retained(): ReviewerSubmissionSnapshot {
  const base = snapshot()
  return snapshot({
    submission_id: 'retained', source_state: 'unavailable', submission_health_state: 'coordination_only',
    raw: { ...base.raw, full_name: '', resume_status: '' },
    parsed: { ...base.parsed, parser_result_state: 'source_unavailable' },
    resolved: { ...base.resolved, resolver_result_state: 'source_unavailable' }
  })
}

let container: HTMLDivElement
let root: Root
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  vi.stubGlobal('fetch', vi.fn())
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

async function render(records: ReviewerSubmissionSnapshot[]) {
  vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(records)))
  await act(async () => { root.render(<MemoryRouter><ParserResults /></MemoryRouter>) })
}

it('excludes retained coordination from rows, counts and pending filters while keeping real pending intake', async () => {
  await render([retained(), snapshot()])
  expect(container.textContent).toContain('Showing 1 of 1 submissions')
  expect(container.textContent).toContain('Intake candidate')
  expect(container.textContent).not.toContain('Unnamed submission')
  expect(container.textContent).not.toContain('retained')
  const select = container.querySelectorAll('select')[0]
  act(() => { select.value = 'pending'; select.dispatchEvent(new Event('change', { bubbles: true })) })
  expect(container.textContent).toContain('Showing 1 of 1 submissions')
  expect(container.querySelectorAll('tbody tr')).toHaveLength(1)
})

it('shows an explicit empty inspection view when only coordination survives', async () => {
  await render([retained()])
  expect(container.textContent).toContain('No intake records available for parser inspection.')
  expect(container.textContent).not.toContain('No parser result yet')
  expect(container.querySelector('tbody')).toBeNull()
  expect(getSubmissionHealthTone('coordination_only')).toBe('neutral')
  expect(getSubmissionHealthTone('pending_processing')).toBe('warning')
  expect(getSubmissionHealthTone('parser_failed')).toBe('danger')
})

it.each(['source', 'health', 'parser', 'resolver'])('honors the explicit %s unavailability signal instead of legacy pending fields', async signal => {
  const base = snapshot()
  const record = snapshot({
    ...(signal === 'source' ? { source_state: 'unavailable' } : {}),
    ...(signal === 'health' ? { submission_health_state: 'coordination_only' } : {}),
    ...(signal === 'parser' ? { parsed: { ...base.parsed, parser_result_state: 'source_unavailable' } } : {}),
    ...(signal === 'resolver' ? { resolved: { ...base.resolved, resolver_result_state: 'source_unavailable' } } : {})
  })
  await render([record])
  expect(container.textContent).toContain('Showing 0 of 0 submissions')
})

it('removes an intake row when a refresh reports source expiry', async () => {
  await render([snapshot()])
  vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify([retained()])))
  const refresh = container.querySelector('button[title="Refresh parser results"]')!
  await act(async () => { refresh.dispatchEvent(new MouseEvent('click', { bubbles: true })) })
  expect(container.textContent).toContain('Showing 0 of 0 submissions')
  expect(container.textContent).not.toContain('Intake candidate')
})

it('keeps legacy intake records and completed parser output visible', async () => {
  const base = snapshot()
  const completed = snapshot({
    source_state: undefined, coordination_state: undefined, submission_health_state: 'complete',
    parsed: { ...base.parsed, parser_state: 'complete', parser_result_state: 'available', parsed_skills_raw: '["Python"]' }
  })
  await render([completed, retained()])
  expect(container.textContent).toContain('Showing 1 of 1 submissions')
  expect(container.textContent).toContain('Python')
})
