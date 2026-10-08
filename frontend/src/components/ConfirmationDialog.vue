<script setup lang="ts">
import { Dialog, DialogPanel, DialogTitle, DialogDescription } from '@headlessui/vue'
import { X } from 'lucide-vue-next'
defineProps<{open:boolean;title:string;description?:string}>();defineEmits<{close:[]}>()
</script>
<template><Dialog :open="open" @close="$emit('close')" class="dialog-root"><div class="dialog-backdrop" aria-hidden="true"/><div class="dialog-position"><DialogPanel class="dialog-panel"><div class="section-heading"><DialogTitle as="h2">{{title}}</DialogTitle><button class="icon-btn" aria-label="Close dialog" @click="$emit('close')"><X :size="20"/></button></div><DialogDescription v-if="description" class="muted">{{description}}</DialogDescription><slot/></DialogPanel></div></Dialog></template>
