<script setup lang="ts">
import AuthGate from './components/AuthGate.vue'
defineProps<{ configurationError?: string }>()
</script>
<template><a href="#main-content" class="skip-link">Skip to main content</a><div v-if="configurationError" class="startup-error" role="alert"><h1>Connect your Clerk application</h1><p>{{ configurationError }}</p><p>Set VITE_CLERK_PUBLISHABLE_KEY in the frontend environment and rebuild the application.</p></div><AuthGate v-else/></template>
