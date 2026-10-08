<script setup lang="ts">defineProps<{name:string;size?:string}>()</script>
<template><span class="avatar" :class="size" aria-hidden="true">{{ name.split(' ').map(n=>n[0]).slice(0,2).join('') }}</span></template>
