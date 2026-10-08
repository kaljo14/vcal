<script setup lang="ts">defineProps<{status:string}>();const labels:Record<string,string>={PENDING:'Pending approval',APPROVED:'Approved',REJECTED:'Declined',CANCELLED:'Cancelled',DRAFT:'Draft',CANCELLATION_REQUESTED:'Cancellation pending'}</script>
<template><span class="status" :class="status.toLowerCase()"><span class="status-dot"></span>{{ labels[status] || status }}</span></template>
