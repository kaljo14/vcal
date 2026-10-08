<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Bell, Check, Mail } from 'lucide-vue-next'
import { useApi, refreshData } from '../composables/query'
import { post, patch } from '../services/api'
import { useSession } from '../stores/session'
import type { Notification } from '../types'
import AsyncState from '../components/AsyncState.vue'
import EmployeeAvatar from '../components/EmployeeAvatar.vue'
const route=useRoute(), session=useSession(),isNotifications=computed(()=>route.path==='/notifications'), failure=ref(''),busy=ref(false)
const {data,loading,error,refresh}=useApi<Notification[]>('/notifications')
async function mark(id:number){try{await post(`/notifications/${id}/read`);await refreshData()}catch(e){failure.value=(e as Error).message}}
async function preferences(event:Event){busy.value=true;failure.value='';try{await patch('/me/preferences',{email_notifications:(event.target as HTMLInputElement).checked});await session.load();session.message('Notification preference saved.')}catch(e){failure.value=(e as Error).message}finally{busy.value=false}}
</script>
<template><div class="page-heading"><div><div class="eyebrow">{{isNotifications?'YOU’RE IN THE LOOP':'YOUR PLACE IN THE TEAM'}}</div><h1>{{isNotifications?'Notifications':'My profile'}}</h1><p>{{isNotifications?'The latest updates on your requests and your team.':'Your details, preferences, and working life.'}}</p></div></div><p v-if="failure" class="error-box" role="alert">{{failure}}</p><AsyncState v-if="isNotifications" :loading="loading" :error="error" :empty="!data?.length" @retry="refresh"><section class="panel notification-list"><article v-for="item in data" :key="item.id" :class="{unread:!item.read_at}"><span class="icon-tile"><Bell :size="19"/></span><div><strong>{{item.message}}</strong><small>{{new Date(item.created_at).toLocaleString()}}</small></div><button v-if="!item.read_at" class="btn secondary" @click="mark(item.id)"><Check :size="16"/>Mark as read</button></article></section></AsyncState><section v-else class="panel profile-card"><div class="person-line"><EmployeeAvatar :name="`${session.user?.first_name} ${session.user?.last_name}`"/><div><h2>{{session.user?.first_name}} {{session.user?.last_name}}</h2><p>{{session.user?.team}} · {{session.user?.department}}</p></div></div><dl class="profile-details"><div><dt>Email</dt><dd>{{session.user?.email}}</dd></div><div><dt>Employee number</dt><dd>{{session.user?.employee_number}}</dd></div><div><dt>Timezone</dt><dd>{{session.user?.timezone}}</dd></div><div><dt>Roles</dt><dd>{{session.user?.roles.join(', ')}}</dd></div></dl><div class="summary-divider"/><h3>Stay up to date</h3><label class="checkbox-label"><input type="checkbox" :checked="session.user?.email_notifications" :disabled="busy" @change="preferences">Email me about request updates</label><p class="field-hint">To update your employee details, contact your People team.</p></section></template>
