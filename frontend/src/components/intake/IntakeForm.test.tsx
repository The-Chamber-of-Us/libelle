import React, { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it } from 'vitest'
import { IntakeForm } from './IntakeForm'

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

function render() {
  act(() => {
    root.render(<IntakeForm />)
  })
}

it('clarifies the location field with an unambiguous label, placeholder, and helper text', () => {
  render()
  const label = Array.from(container.querySelectorAll('label')).find(
    (el) => el.textContent?.trim().startsWith('Your Location')
  )
  expect(label).toBeTruthy()

  const input = container.querySelector('input[name="location"]') as HTMLInputElement
  expect(input.placeholder).toBe('e.g., Charlotte, NC')
  expect(container.textContent).toContain(
    'Used to understand time zone, local context, and possible project fit.'
  )
})

it('gives the availability field example helper text', () => {
  render()
  expect(container.textContent).toContain(
    'Examples: weekday evenings, Saturday mornings, 5-10 hours/week, project-based.'
  )
})

it('tells volunteers prior nonprofit experience is not required', () => {
  render()
  expect(container.textContent).toContain(
    'Choose the level that best describes your comfort today. Prior nonprofit experience is not required.'
  )
})

it('explains how submissions connect to project matching', () => {
  render()
  expect(container.textContent).toContain(
    'We use your interests, skills, availability, and location to identify possible TCUS project matches.'
  )
})

it('preserves the motivation character counter', () => {
  render()
  expect(container.textContent).toContain('0/280 characters')
})
