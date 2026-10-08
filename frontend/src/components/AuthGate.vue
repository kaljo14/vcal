<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useAuth, useClerk } from '@clerk/vue'
import { useRouter } from 'vue-router'
import { bindClerkSession, finishAuthInitialization, logout } from '../services/auth'
import { api } from '../services/api'
import { queryClient } from '../composables/query'
import { useSession } from '../stores/session'
import type { Employee } from '../types'
const clerk = useClerk(), { isLoaded, isSignedIn, sessionId, getToken } = useAuth()
const session = useSession(), router = useRouter(), loading = ref(true), failure = ref('')
let generation = 0
const timeout = setTimeout(() => {
  if (!isLoaded.value) {
    failure.value = 'Clerk could not be loaded. Check your connection and Clerk publishable key.'
    loading.value = false
    finishAuthInitialization()
  }
}, 30000)
onBeforeUnmount(() => clearTimeout(timeout))
watch([isLoaded, isSignedIn, sessionId], async ([loaded, signedIn, id]) => {
  if (!loaded) return
  clearTimeout(timeout)
  const version = ++generation
  loading.value = true
  failure.value = ''
  session.user = null
  session.sidebarOpen = false
  bindClerkSession(signedIn && id ? {
    sessionId: id,
    getToken: () => getToken.value(),
    signOut: async () => { await clerk.value?.signOut({ redirectUrl: window.location.origin + '/login' }) },
  } : null, () => clerk.value?.openSignIn({ forceRedirectUrl: window.location.origin + '/' }))
  await queryClient.cancelQueries()
  queryClient.clear()
  try {
    if (signedIn) {
      const employee = await api<Employee>('/me')
      if (version !== generation) return
      session.user = employee
    }
  } catch (error) {
    if (version === generation) failure.value = (error as Error).message
  } finally {
    if (version === generation) {
      loading.value = false
      finishAuthInitialization()
    }
  }
  await router.isReady()
  if (version !== generation) return
  if (!signedIn) await router.replace('/login')
  else if (!failure.value) {
    const allowed = router.currentRoute.value.meta.roles as string[] | undefined
    if (router.currentRoute.value.path === '/login' || (allowed && !session.has(...allowed))) await router.replace('/')
  }
}, { immediate: true })
function reload() { window.location.reload() }
</script>
<template>
  <div v-if="loading" class="loading-state" role="status">Connecting to your workspace…</div>
  <div v-else-if="failure" class="startup-error" role="alert">
    <h1>We couldn’t open your workspace</h1><p>{{ failure }}</p>
    <p>Your Clerk account must be linked to an active employee by an administrator.</p>
    <div class="button-row"><button class="btn primary" @click="reload">Try again</button><button v-if="isSignedIn" class="btn secondary" @click="logout">Sign out</button></div>
  </div>
  <RouterView v-else/>
</template>
