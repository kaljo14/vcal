<script setup lang="ts">
import { CalendarDays, Laptop, Check, X, ArrowRight } from 'lucide-vue-next'
import type { WorkRequest } from '../types'
import { dateRange } from '../services/dates'
import EmployeeAvatar from './EmployeeAvatar.vue'
import StatusBadge from './StatusBadge.vue'
defineProps<{request:WorkRequest}>();defineEmits<{decide:[WorkRequest,'approve'|'reject'];details:[WorkRequest]}>()
</script>
<template><article class="panel approval-card"><div class="flex-between"><div class="person-line"><EmployeeAvatar :name="request.employee_name"/><div><h3>{{request.employee_name}}</h3><span class="muted">{{request.label}}</span></div></div><StatusBadge :status="request.status"/></div><div class="approval-dates"><CalendarDays v-if="request.kind==='LEAVE'" :size="18"/><Laptop v-else :size="18"/><strong>{{dateRange(request.start_date,request.end_date)}}</strong><span>{{request.days}} days · {{request.portion==='FULL'?'Full day':request.portion}}</span></div><p v-if="request.comment" class="request-comment">{{request.comment}}</p><p v-if="request.exception_flags.length" class="notice">HR review: {{request.exception_flags.join(', ').replaceAll('_',' ')}}</p><div class="flex-between"><button class="text-link" @click="$emit('details',request)">Team availability <ArrowRight :size="15"/></button><div v-if="request.can_approve&&['PENDING','CANCELLATION_REQUESTED'].includes(request.status)" class="button-row"><button class="btn secondary" @click="$emit('decide',request,'reject')"><X :size="16"/>Decline</button><button class="btn primary" @click="$emit('decide',request,'approve')"><Check :size="16"/>Approve</button></div></div></article></template>
