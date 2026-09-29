import React, { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest'
import type { CoordinationRecord, ReviewerSubmissionSnapshot } from '../../types/dashboard'
import InboxDetailPanel from './InboxDetailPanel'

type Deferred<T> = {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (error: unknown) => void
}

function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })

  return { promise, resolve, reject }
}

function createSubmission(
  overrides: Omit<Partial<ReviewerSubmissionSnapshot>, 'raw'> & {
    raw?: Partial<ReviewerSubmissionSnapshot['raw']>
  } = {}
): ReviewerSubmissionSnapshot {
  const { raw: rawOverrides, ...submissionOverrides } = overrides

  return {
    submission_id: overrides.submission_id ?? 'sub_001',
    submission_health_state: overrides.submission_health_state ?? 'complete',
    raw: {
      created_at: '2026-07-01T12:00:00Z',
      full_name: 'Reviewer Candidate',
      email: 'candidate@example.org',
      location_raw: 'New York, NY',
      timezone: 'America/New_York',
      skills_raw: 'React',
      interests: 'Frontend',
      experience_level: 'Intermediate',
      availability: 'Weekends',
      motivation: 'Help',
      linkedin_url: '',
      github_url: '',
      consent_given: 'true',
      resume_filename: 'sub_001_resume.pdf',
      resume_status: 'uploaded',
      ...rawOverrides
    },
    parsed: {
      parser_state: 'complete',
      parser_result_state: 'available',
      parser_run_id: 'parser-run-1',
      created_at: '2026-07-01T12:01:00Z',
      parser_version: 'test',
      parsed_skills_raw: 'React',
      parsed_location_raw: 'New York, NY',
      parser_confidence: 'high',
      parser_confidence_score: 0.9
    },
    resolved: {
      resolver_state: 'resolved',
      resolver_result_state: 'available',
      resolver_version: 'test',
      aliases_version: 'test',
      resolved_skill_ids: 'react',
      unknown_skills: '',
      resolver_coverage: 'complete',
      resolver_coverage_score: 1
    },
    parser_job: null,
    ops: {
      status: 'new',
      notes: '',
      tags: '',
      contact_tracking: '',
      updated_at: '',
      updated_by: ''
    },
    errors: {
      error_state: 'none',
      has_error: false,
      latest_error_summary: '',
      latest_error_stage: '',
      latest_error_code: ''
    },
    ...submissionOverrides
  }
}

function renderPanel(submission: ReviewerSubmissionSnapshot, onCoordinationSaved?: (id: string, record: CoordinationRecord) => void) {
  const container = document.createElement('div')
  document.body.append(container)
  const root = createRoot(container)

  const render = (nextSubmission: ReviewerSubmissionSnapshot) =>
    act(() => {
      root.render(
        <InboxDetailPanel
          submission={nextSubmission}
          statusOptions={['new', 'reviewed']}
          pendingStatus={null}
          statusSaveState={{ status: 'idle' }}
          notesSaveState={{ status: 'idle' }}
          onStatusChange={() => undefined}
          onNotesSave={() => undefined}
          onCoordinationSaved={onCoordinationSaved}
        />
      )
    })

  render(submission)

  return {
    container,
    render,
    unmount: () => {
      act(() => root.unmount())
      container.remove()
    }
  }
}

function getButton(container: HTMLElement, label: string) {
  const buttons = Array.from(container.querySelectorAll('button'))
  return buttons.find((button) => button.textContent?.includes(label)) ?? null
}

function click(element: Element) {
  act(() => {
    element.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  })
}

function createResumeWindow() {
  return {
    opener: window,
    location: { href: '' },
    close: vi.fn()
  }
}

async function flushAsyncWork() {
  await act(async () => {
    await Promise.resolve()
  })
}

describe('InboxDetailPanel resume access', () => {
  let rendered: { container: HTMLElement; unmount: () => void } | null = null
  let openSpy: MockInstance<typeof window.open>

  beforeEach(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
      .IS_REACT_ACT_ENVIRONMENT = true
    vi.stubGlobal('fetch', vi.fn())
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:resume-url'),
      revokeObjectURL: vi.fn()
    })
    openSpy = vi.spyOn(window, 'open')
  })

  afterEach(() => {
    rendered?.unmount()
    rendered = null
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('shows and fetches the proxy action for an uploaded resume', async () => {
    const resumeWindow = createResumeWindow()
    vi.mocked(openSpy).mockReturnValue(resumeWindow as unknown as Window)
    vi.mocked(fetch).mockResolvedValue(
      new Response(new Blob(['%PDF test'], { type: 'application/pdf' }), {
        status: 200
      })
    )

    rendered = renderPanel(createSubmission())
    const button = getButton(rendered.container, 'Open Resume')

    expect(button).not.toBeNull()
    click(button!)
    await flushAsyncWork()

    expect(fetch).toHaveBeenCalledWith('/resumes/sub_001', {
      signal: expect.any(AbortSignal)
    })
    expect(resumeWindow.location.href).toBe('blob:resume-url')
    expect(rendered.container.textContent).toContain('Resume opened in a new tab.')
  })

  it('shows the proxy action for an uploaded resume with a blank display filename', () => {
    rendered = renderPanel(
      createSubmission({
        raw: {
          resume_filename: '',
          resume_status: 'uploaded'
        }
      })
    )

    expect(getButton(rendered.container, 'Open Resume')).not.toBeNull()
    expect(rendered.container.textContent).toContain('Uploaded resume: Filename unavailable')
  })

  it('uses a fallback download filename when an uploaded resume filename is blank', async () => {
    let clickedDownload = ''
    vi.mocked(openSpy).mockReturnValue(null)
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function click(
      this: HTMLAnchorElement
    ) {
      clickedDownload = this.download
    })
    vi.mocked(fetch).mockResolvedValue(
      new Response(new Blob(['%PDF test'], { type: 'application/pdf' }), {
        status: 200
      })
    )

    rendered = renderPanel(
      createSubmission({
        raw: {
          resume_filename: '',
          resume_status: 'uploaded'
        }
      })
    )

    click(getButton(rendered.container, 'Open Resume')!)
    await flushAsyncWork()

    expect(clickedDownload).toBe('sub_001-resume.pdf')
    expect(rendered.container.textContent).toContain('Resume download started.')
  })

  it('shows a distinct missing resume state without an open action', () => {
    rendered = renderPanel(
      createSubmission({
        raw: {
          resume_filename: '',
          resume_status: 'missing'
        }
      })
    )

    expect(getButton(rendered.container, 'Open Resume')).toBeNull()
    expect(rendered.container.textContent).toContain('No resume was provided.')
  })

  it('treats a blank resume status as no resume provided', () => {
    rendered = renderPanel(
      createSubmission({
        raw: {
          resume_filename: '',
          resume_status: ''
        }
      })
    )

    expect(getButton(rendered.container, 'Open Resume')).toBeNull()
    expect(rendered.container.textContent).toContain('No resume was provided.')
  })

  it('shows a distinct failed resume state without an open action', () => {
    rendered = renderPanel(
      createSubmission({
        raw: {
          resume_filename: '',
          resume_status: 'failed'
        }
      })
    )

    expect(getButton(rendered.container, 'Open Resume')).toBeNull()
    expect(rendered.container.textContent).toContain(
      'A resume was provided, but Libelle failed to store it.'
    )
  })

  it('shows an unknown-state warning for unexpected resume status values', () => {
    rendered = renderPanel(
      createSubmission({
        raw: {
          resume_filename: '',
          resume_status: 'archived'
        }
      })
    )

    expect(getButton(rendered.container, 'Open Resume')).toBeNull()
    expect(rendered.container.textContent).toContain(
      'Resume availability is unknown for this submission.'
    )
  })

  it('surfaces backend resume access errors without hiding the dashboard', async () => {
    const resumeWindow = createResumeWindow()
    vi.mocked(openSpy).mockReturnValue(resumeWindow as unknown as Window)
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: {
            message: 'Resume metadata exists, but the file is unavailable.'
          }
        }),
        {
          status: 404,
          headers: { 'Content-Type': 'application/json' }
        }
      )
    )

    rendered = renderPanel(createSubmission())
    click(getButton(rendered.container, 'Open Resume')!)
    await flushAsyncWork()

    expect(rendered.container.textContent).toContain(
      'Resume metadata exists, but the file is unavailable.'
    )
    expect(rendered.container.textContent).toContain('Selected Submission')
    expect(resumeWindow.close).toHaveBeenCalled()
  })

  it('ignores an in-flight resume response after switching submissions', async () => {
    const delayedResponse = createDeferred<Response>()
    const firstWindow = createResumeWindow()
    vi.mocked(openSpy).mockReturnValue(firstWindow as unknown as Window)
    vi.mocked(fetch).mockReturnValue(delayedResponse.promise)

    const initialSubmission = createSubmission({ submission_id: 'sub_001' })
    const nextSubmission = createSubmission({
      submission_id: 'sub_002',
      raw: {
        full_name: 'Second Candidate',
        resume_filename: '',
        resume_status: 'missing'
      }
    })

    const panel = renderPanel(initialSubmission)
    rendered = panel
    click(getButton(panel.container, 'Open Resume')!)

    panel.render(nextSubmission)
    delayedResponse.resolve(
      new Response(new Blob(['%PDF stale'], { type: 'application/pdf' }), {
        status: 200
      })
    )
    await flushAsyncWork()

    expect(firstWindow.close).toHaveBeenCalled()
    expect(firstWindow.location.href).toBe('')
    expect(panel.container.textContent).not.toContain('Resume opened in a new tab.')
    expect(panel.container.textContent).toContain('Second Candidate')
    expect(panel.container.textContent).toContain('No resume was provided.')
  })

  it('keeps coordination visible and hides source controls when intake is absent', () => {
    rendered = renderPanel(createSubmission({
      source_state: 'unavailable', submission_health_state: 'coordination_only',
      coordination_state: 'active', raw: { full_name: '' },
      coordination: {
        state: 'active', purpose: 'Ongoing project', takeaway: 'Follow up next week',
        why: 'Continue the project', next_action: 'Arrange a call', revisit: '2026-10-01',
        display_name: 'Retained contact', contact: 'coordination@example.org',
        purpose_started_at: '2026-09-28T00:00:00Z', purpose_ended_at: null,
        decided_by: 'reviewer@example.org'
      }
    }))
    expect(rendered.container.textContent).toContain('Retained contact')
    expect(rendered.container.textContent).toContain('Source evidence is unavailable')
    expect(getButton(rendered.container, 'Open Resume')).toBeNull()
    expect(getButton(rendered.container, 'Save Notes')).not.toBeNull()
    expect(getButton(rendered.container, 'Preserve purpose')?.disabled).toBe(true)
  })

  it('requires review before an explicit lifecycle write and sends no client timestamps', async () => {
    const coordination = {
      state: 'active' as const, purpose: 'Ongoing project', takeaway: '', why: '',
      next_action: '', revisit: null, display_name: '', contact: '',
      purpose_started_at: '2026-09-28T00:00:00Z', purpose_ended_at: null,
      decided_by: 'reviewer@example.org'
    }
    const onSaved = vi.fn()
    rendered = renderPanel(createSubmission({ coordination_state: 'active', coordination }), onSaved)
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(coordination), { status: 200 }))
    expect(getButton(rendered.container, 'Preserve purpose')?.disabled).toBe(true)
    click(rendered.container.querySelector('input[type="checkbox"]')!)
    click(getButton(rendered.container, 'Preserve purpose')!)
    await flushAsyncWork()
    expect(fetch).toHaveBeenCalledWith('/submissions/sub_001/coordination', expect.objectContaining({ method: 'POST' }))
    const payload = JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string)
    expect(onSaved).toHaveBeenCalledWith('sub_001', coordination)
    expect(payload.action).toBe('preserve')
    expect(payload.context_reviewed).toBe(true)
    expect(payload.purpose_started_at).toBeUndefined()
    expect(payload.decided_by).toBeUndefined()
    expect(rendered.container.textContent).toContain('Coordination purpose preserved.')
    expect(getButton(rendered.container, 'Preserve purpose')?.disabled).toBe(true)
  })

  it('refreshes coordination content and purpose state for the same selected submission', () => {
    const coordination: CoordinationRecord = {
      state: 'active', purpose: 'Project', takeaway: 'Old takeaway', why: '', next_action: '',
      revisit: null, display_name: '', contact: '', purpose_started_at: '2026-09-28T00:00:00Z',
      purpose_ended_at: null, decided_by: 'reviewer@example.org'
    }
    const initial = createSubmission({ coordination_state: 'active', coordination })
    const panel = renderPanel(initial)
    rendered = panel
    click(rendered.container.querySelector('input[type="checkbox"]')!)
    panel.render({ ...initial, coordination_state: 'ended', coordination: {
      ...coordination, state: 'ended', takeaway: 'New takeaway',
      purpose_ended_at: '2026-09-29T00:00:00Z'
    } })
    expect(Array.from(rendered.container.querySelectorAll('textarea')).map(e => e.value)).toContain('New takeaway')
    expect(rendered.container.textContent).toContain('Purpose: ended')
    expect(getButton(rendered.container, 'Start new purpose')?.disabled).toBe(true)
    expect(rendered.container.textContent).toContain('2026-09-29T00:00:00Z')
  })

})
