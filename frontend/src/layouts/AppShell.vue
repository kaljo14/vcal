<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Bell, Menu, ChevronRight } from 'lucide-vue-next'
import NavigationSidebar from '../components/NavigationSidebar.vue'
import EmployeeAvatar from '../components/EmployeeAvatar.vue'
import { useSession } from '../stores/session'
const route=useRoute(), session=useSession()
const title=computed(()=>route.meta.title||'Overview')
</script>
<template><NavigationSidebar/><div class="app-content"><header class="topbar"><div class="breadcrumb"><button class="icon-btn mobile-menu" aria-label="Open navigation" :aria-expanded="session.sidebarOpen" @click="session.sidebarOpen=true"><Menu :size="22"/></button><span>Workspace</span><ChevronRight :size="14"/><strong>{{title}}</strong></div><div class="topbar-actions"><span class="today-label">{{new Intl.DateTimeFormat('en-GB',{weekday:'short',day:'numeric',month:'short'}).format(new Date())}}</span><RouterLink to="/notifications" class="icon-btn" aria-label="Notifications"><Bell :size="19"/></RouterLink><RouterLink to="/profile" aria-label="My profile"><EmployeeAvatar :name="`${session.user?.first_name} ${session.user?.last_name}`" size="small"/></RouterLink></div></header><main id="main-content"><RouterView/></main><footer class="app-footer"><span>Made for a better work–life balance.</span><span>Workleave · Your people, in sync</span></footer></div><div v-if="session.toast" class="toast" role="status">{{session.toast}}</div></template>
