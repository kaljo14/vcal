<script setup lang="ts">defineProps<{headers:string[]}>()</script>
<template><div class="table-scroll"><table><thead><tr><th v-for="header in headers" :key="header" scope="col">{{header}}</th></tr></thead><tbody><slot/></tbody></table></div></template>
