import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

const backendTarget = 'http://127.0.0.1:8000'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devInternalActorEmail = env.VITE_DEV_INTERNAL_ACTOR_EMAIL?.trim()
  const devInternalActorHeaders = devInternalActorEmail
    ? { 'cf-access-authenticated-user-email': devInternalActorEmail }
    : undefined

  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true
        },
        '/health': {
          target: backendTarget,
          changeOrigin: true
        },
        '/snapshot': {
          target: backendTarget,
          changeOrigin: true
        },
        '/ops': {
          target: backendTarget,
          changeOrigin: true,
          headers: devInternalActorHeaders
        },
        '/submissions': {
          target: backendTarget,
          changeOrigin: true,
          headers: devInternalActorHeaders
        },
        '/resumes': {
          target: backendTarget,
          changeOrigin: true
        }
      }
    }
  }
})
