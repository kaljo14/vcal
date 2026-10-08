<script setup lang="ts">
import { ref } from 'vue'
import { useApi } from '../composables/query'
import type { Balance } from '../types'
import AsyncState from '../components/AsyncState.vue'
import BalanceCard from '../components/BalanceCard.vue'
import DataTable from '../components/DataTable.vue'
const year=ref(new Date().getFullYear())
const {data,loading,error,refresh}=useApi<Balance[]>(()=>`/me/balances?year=${year.value}`)
const ledger=useApi<{id:number;effective_date:string;transaction_type:string;amount:string;reason:string;year:number;expires_on:string|null}[]>('/me/ledger')
</script>
<template><div class="page-heading"><div><div class="eyebrow">TIME THAT’S YOURS</div><h1>Leave balances</h1><p>Every day accounted for, with a clear record of every change.</p></div><label>Balance year<input v-model.number="year" type="number" min="2000" max="2200"></label></div><AsyncState :loading="loading" :error="error" @retry="refresh"><div v-for="balance in data" :key="balance.leave_type_id"><h2 class="mb-4">{{balance.name}}</h2><div class="stats-grid"><BalanceCard label="Available balance" :value="balance.available" caption="Approved requests are already deducted" accent/><BalanceCard label="Approved leave" :value="balance.used" caption="Including upcoming approved days"/><BalanceCard label="Pending requests" :value="balance.pending" caption="Not yet deducted from your balance"/><BalanceCard label="After pending leave" :value="balance.projected" caption="Estimate if all pending requests are approved"/></div></div></AsyncState><section class="panel"><div class="section-heading"><h2>Your balance history</h2><span class="muted">Most recent 50 entries</span></div><AsyncState :loading="ledger.loading.value" :error="ledger.error.value" :empty="!ledger.data.value?.length" @retry="ledger.refresh"><DataTable :headers="['Effective date','Type','Year','Days','Reason','Expires']"><tr v-for="entry in ledger.data.value" :key="entry.id"><td>{{entry.effective_date}}</td><td>{{entry.transaction_type.replaceAll('_',' ')}}</td><td>{{entry.year}}</td><td :class="Number(entry.amount)>0?'positive':''">{{Number(entry.amount)>0?'+':''}}{{entry.amount}}</td><td>{{entry.reason}}</td><td>{{entry.expires_on||'—'}}</td></tr></DataTable></AsyncState></section></template>
