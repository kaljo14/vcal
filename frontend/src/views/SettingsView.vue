<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useApi, refreshData } from '../composables/query'
import { api, patch, post } from '../services/api'
import { useSession } from '../stores/session'
import type { Lookup } from '../types'
import AsyncState from '../components/AsyncState.vue'
import ConfirmationDialog from '../components/ConfirmationDialog.vue'
import DataTable from '../components/DataTable.vue'

const session = useSession()
const { data, loading, error, refresh } = useApi<{id:number;name:string;timezone:string;retention_years:number}>('/settings')
const departments = useApi<Lookup[]>('/departments')
const audit = useApi<Record<string,unknown>[]>('/audit')
const form = reactive({name:'',timezone:'',retention_years:5})
const dept = reactive({name:'',description:''})
const team = reactive({name:'',department_id:1})
const failure = ref('')
const busy = ref(false)
const deleteTarget = ref<Lookup|null>(null)

watch(data, value => {
  if (value) Object.assign(form, {name:value.name,timezone:value.timezone,retention_years:value.retention_years})
}, {immediate:true})
watch(departments.data, value => {
  if (value?.length && !value.some(department => department.id === team.department_id)) team.department_id = value[0].id
}, {immediate:true})

async function save(path:string, body:unknown, method='POST') {
  busy.value = true
  failure.value = ''
  try {
    await (method === 'PATCH' ? patch(path, body) : post(path, body))
    await refreshData()
    session.message('Settings saved.')
    dept.name = ''
    team.name = ''
  } catch (e) {
    failure.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

async function removeDepartment() {
  if (!deleteTarget.value) return
  busy.value = true
  failure.value = ''
  try {
    await api<void>(`/departments/${deleteTarget.value.id}`, {method:'DELETE'})
    deleteTarget.value = null
    await refreshData()
    session.message('Department deleted.')
  } catch (e) {
    failure.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page-heading"><div><div class="eyebrow">YOUR ORGANIZATION</div><h1>Workspace settings</h1><p>A solid foundation for your people.</p></div></div>
  <p v-if="failure && !deleteTarget" class="error-box" role="alert">{{failure}}</p>
  <AsyncState :loading="loading" :error="error" @retry="refresh">
    <div class="policy-columns">
      <form class="panel form-panel" @submit.prevent="save('/settings',form,'PATCH')">
        <h2>Organization</h2>
        <label>Organization name<input v-model="form.name" required></label>
        <label>Default timezone<input v-model="form.timezone" required></label>
        <label>Retention policy (years)<input v-model.number="form.retention_years" type="number" min="1" max="50" required></label>
        <p class="field-hint">This records the organization’s retention policy. Follow the documented retention procedure before deleting records.</p>
        <button class="btn primary" :disabled="busy">Save settings</button>
      </form>
      <div class="panel form-panel">
        <h2>Departments</h2>
        <ul class="department-list">
          <li v-for="department in departments.data.value" :key="department.id" class="department-item">
            <span>{{department.name}}</span>
            <button type="button" class="text-link" :disabled="busy" :aria-label="`Delete ${department.name} department`" @click="failure='';deleteTarget=department">Delete</button>
          </li>
        </ul>
        <form @submit.prevent="save('/departments',dept)">
          <label>New department<input v-model="dept.name" required></label>
          <button class="btn secondary" :disabled="busy">Add department</button>
        </form>
        <div class="summary-divider"/>
        <form @submit.prevent="save('/teams',team)">
          <h2>Teams</h2>
          <label>New team<input v-model="team.name" required></label>
          <label>Department<select v-model.number="team.department_id"><option v-for="department in departments.data.value" :key="department.id" :value="department.id">{{department.name}}</option></select></label>
          <button class="btn secondary" :disabled="busy">Add team</button>
        </form>
      </div>
    </div>
  </AsyncState>
  <section class="panel"><div class="section-heading"><h2>Operational audit trail</h2><span class="muted">Most recent 50 events</span></div><AsyncState :loading="audit.loading.value" :error="audit.error.value" @retry="audit.refresh"><DataTable :headers="['Time','Actor ID','Action','Entity']"><tr v-for="entry in audit.data.value" :key="String(entry.id)"><td>{{new Date(String(entry.timestamp)).toLocaleString()}}</td><td>{{entry.actor_id||'System'}}</td><td>{{entry.action}}</td><td>{{entry.entity_type}} #{{entry.entity_id}}</td></tr></DataTable></AsyncState></section>
  <ConfirmationDialog :open="!!deleteTarget" title="Delete department" :description="deleteTarget?`Delete ${deleteTarget.name}? Any empty teams in this department will also be deleted. Move its employees first.`:undefined" @close="deleteTarget=null;failure=''">
    <p v-if="failure" class="error-box" role="alert">{{failure}}</p>
    <div class="form-actions"><button type="button" class="btn secondary" @click="deleteTarget=null;failure=''">Keep department</button><button type="button" class="btn primary" :disabled="busy" @click="removeDepartment">{{busy?'Deleting…':'Delete department'}}</button></div>
  </ConfirmationDialog>
</template>
