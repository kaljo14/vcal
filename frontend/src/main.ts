import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { clerkPlugin } from '@clerk/vue'
import App from './App.vue'
import { router } from './router'
import { finishAuthInitialization } from './services/auth'
import './style.css'
const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
let configurationError = !publishableKey ? 'The Clerk publishable key has not been configured.' : ''
const app = createApp(App, { get configurationError() { return configurationError } })
app.use(createPinia())
if (!configurationError) {
  try {
    app.use(clerkPlugin, {
      publishableKey,
      signInForceRedirectUrl: window.location.origin + '/',
      signUpForceRedirectUrl: window.location.origin + '/',
    })
  } catch {
    configurationError = 'The Clerk publishable key is invalid.'
  }
}
if (configurationError) finishAuthInitialization()
app.use(router)
app.mount('#app')
if ('serviceWorker' in navigator && import.meta.env.PROD) navigator.serviceWorker.register('/sw.js').catch(() => {})
