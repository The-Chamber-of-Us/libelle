// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest'
import { type ConfigEnv, type UserConfig } from 'vite'
import config from './vite.config'

const resolve = config as (env: ConfigEnv) => UserConfig

afterEach(() => vi.unstubAllEnvs())

describe('local actor simulation', () => {
  it.each([
    ['serve', 'development', false, true],
    ['serve', 'production', false, false],
    ['serve', 'development', true, false],
    ['build', 'development', false, false],
    ['build', 'production', false, false],
  ] as const)('%s %s preview=%s', (command, mode, isPreview, enabled) => {
    vi.stubEnv('VITE_DEV_INTERNAL_ACTOR_EMAIL', ' local@example.org ')
    const result = resolve({ command, mode, isPreview })
    for (const route of ['/ops', '/submissions', '/resumes']) {
      const proxy = result.server?.proxy?.[route]
      expect(typeof proxy === 'object' ? proxy.headers : undefined).toEqual(
        enabled ? { 'cf-access-authenticated-user-email': 'local@example.org' } : undefined,
      )
    }
  })

  it('does not simulate an actor when unset', () => {
    vi.stubEnv('VITE_DEV_INTERNAL_ACTOR_EMAIL', '')
    const result = resolve({ command: 'serve', mode: 'development' })
    const proxy = result.server?.proxy?.['/ops']
    expect(typeof proxy === 'object' ? proxy.headers : undefined).toBeUndefined()
  })
})
