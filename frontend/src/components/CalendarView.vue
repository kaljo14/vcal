<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { Calendar } from '@fullcalendar/core'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import type { CalendarEvent } from '../types'
const props=defineProps<{events:CalendarEvent[];initialDate?:string}>()
const emit=defineEmits<{range:[string,string];select:[CalendarEvent]}>()
const element=ref<HTMLElement>(), instance=ref<Calendar>()
const palette:Record<string,string>={OFFICE:'#e9f0ec',MOBILE:'#e5edfc',LEAVE:'#fff0dc',HOLIDAY:'#f0eafa'}
function events(){return props.events.map(e=>({...e,allDay:true,backgroundColor:palette[e.kind],borderColor:e.status==='PENDING'?'#cb9a3c':palette[e.kind],textColor:e.kind==='MOBILE'?'#365998':e.kind==='LEAVE'?'#956125':'#426254',extendedProps:{...e}}))}
onMounted(()=>{instance.value=new Calendar(element.value!,{plugins:[dayGridPlugin,timeGridPlugin,interactionPlugin],initialView:'dayGridMonth',initialDate:props.initialDate,height:'auto',firstDay:1,dayMaxEvents:3,headerToolbar:{left:'prev,next today',center:'title',right:'dayGridMonth,timeGridWeek,timeGridDay'},buttonText:{today:'Today',month:'Month',week:'Week',day:'Day'},events:events(),datesSet:arg=>{const end=new Date(arg.end);end.setDate(end.getDate()-1);emit('range',arg.startStr.slice(0,10),`${end.getFullYear()}-${String(end.getMonth()+1).padStart(2,'0')}-${String(end.getDate()).padStart(2,'0')}`)},eventClick:arg=>emit('select',arg.event.extendedProps as CalendarEvent)});instance.value.render()})
watch(()=>props.events,()=>instance.value?.setOption('events',events()))
onBeforeUnmount(()=>instance.value?.destroy())
</script>
<template><div ref="element" class="workleave-calendar"/></template>
