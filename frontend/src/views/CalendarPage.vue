<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { CalendarDays, Users } from 'lucide-vue-next'
import CalendarView from '../components/CalendarView.vue'
import AsyncState from '../components/AsyncState.vue'
import ConfirmationDialog from '../components/ConfirmationDialog.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { useApi } from '../composables/query'
import type { CalendarData, CalendarEvent, Lookup } from '../types'
import { isoDate, shortDate } from '../services/dates'
const route=useRoute(),initial=typeof route.query.date==='string'?route.query.date:isoDate()
const start=ref(initial),end=ref(initial),team=ref(''),department=ref(''),employee=ref(''),showOffice=ref(false),selected=ref<CalendarEvent|null>(null)
const {data,loading,error,refresh}=useApi<CalendarData>(()=>`/calendar?start=${start.value}&end=${end.value}${team.value?'&team_id='+team.value:''}${department.value?'&department_id='+department.value:''}${employee.value?'&employee_id='+employee.value:''}`)
const teams=useApi<Lookup[]>('/teams'),departments=useApi<Lookup[]>('/departments')
const events=computed(()=>data.value?.events.filter(e=>showOffice.value||e.kind!=='OFFICE')||[])
function range(a:string,b:string){start.value=a;end.value=b}
</script>
<template><div class="page-heading"><div><div class="eyebrow">YOUR PEOPLE, IN SYNC</div><h1>Team calendar</h1><p>A shared view of who’s around, wherever they’re working.</p></div><RouterLink to="/request/mobile" class="btn secondary"><CalendarDays :size="17"/>Plan a mobile day</RouterLink></div><section class="panel calendar-panel"><div class="calendar-filters"><label><span class="sr-only">Department</span><select v-model="department"><option value="">All departments</option><option v-for="d in departments.data.value" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label><span class="sr-only">Team</span><select v-model="team"><option value="">All permitted teams</option><option v-for="t in teams.data.value" :key="t.id" :value="t.id">{{t.name}}</option></select></label><label><span class="sr-only">Employee</span><select v-model="employee"><option value="">All teammates</option><option v-for="p in data?.employees" :key="p.id" :value="p.id">{{p.name}}</option></select></label><label class="checkbox-label"><input v-model="showOffice" type="checkbox">Show office days</label></div><p v-if="error" class="error-box" role="alert">{{error.message}} <button class="text-link" @click="refresh">Retry</button></p><div v-if="loading" class="calendar-loading" role="status">Updating calendar…</div><CalendarView :events="events" :initial-date="initial" @range="range" @select="selected=$event"/><div class="calendar-legend"><span><i class="dot office"/>Office</span><span><i class="dot mobile"/>Mobile work</span><span><i class="dot leave"/>Vacation / leave</span><span><i class="dot holiday"/>Public holiday</span><span><i class="dot pending"/>Pending approval</span></div></section><ConfirmationDialog :open="!!selected" title="Team availability" @close="selected=null"><template v-if="selected"><h3>{{selected.title}}</h3><p>{{shortDate(selected.start)}} · {{selected.portion||'Full day'}}</p><StatusBadge :status="selected.status"/><div v-if="data?.statistics[selected.start]" class="summary-line"><Users :size="18"/><span>{{data.statistics[selected.start]?.office}} office · {{data.statistics[selected.start]?.remote}} remote · {{data.statistics[selected.start]?.leave}} away</span></div><p class="field-hint">This shared view shows availability only. Personal leave details stay private.</p></template></ConfirmationDialog></template>
