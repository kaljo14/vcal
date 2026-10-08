<script setup lang="ts">
import { ref } from 'vue'
import { Download } from 'lucide-vue-next'
import { useApi } from '../composables/query'
import { downloadReport } from '../services/api'
import { useSession } from '../stores/session'
import AsyncState from '../components/AsyncState.vue'
import DataTable from '../components/DataTable.vue'
const session=useSession(),report=ref(session.has('HR')?'leave':'mobile-work'),start=ref(new Date().toISOString().slice(0,7)+'-01'),end=ref(new Date().toISOString().slice(0,10)),failure=ref('')
const path=()=>`/reports/${report.value}?start=${start.value}&end=${end.value}`
const {data,loading,error,refresh}=useApi<Record<string,unknown>[]>(path)
async function download(){failure.value='';try{await downloadReport(path()+'&format=csv')}catch(e){failure.value=(e as Error).message}}
</script>
<template><div class="page-heading"><div><div class="eyebrow">THE BIGGER PICTURE</div><h1>People reports</h1><p>A clear view of time away and flexible working.</p></div><button class="btn secondary" :disabled="!!error||loading" @click="download"><Download :size="17"/>Export CSV</button></div><div class="panel report-filters"><label>Report<select v-model="report"><option v-if="session.has('HR')" value="leave">Vacation usage</option><option v-if="session.has('HR')" value="balances">Leave balances</option><option value="mobile-work">Mobile-work usage</option><option value="pending">Pending requests</option><option value="team-availability">Team availability</option></select></label><label>From<input v-model="start" type="date"></label><label>To<input v-model="end" type="date" :min="start"></label></div><p v-if="failure" class="error-box" role="alert">{{failure}}</p><AsyncState :loading="loading" :error="error" :empty="!data?.length" @retry="refresh"><section class="panel"><DataTable :headers="Object.keys(data?.[0]||{}).map(k=>k.replaceAll('_',' '))"><tr v-for="(row,index) in data" :key="index"><td v-for="(value,key) in row" :key="key">{{value}}</td></tr></DataTable></section></AsyncState></template>
