import { defineConfig } from '@playwright/test'
export default defineConfig({testDir:'.',globalSetup:'./global.setup.ts',testMatch:'*.spec.ts',workers:1,timeout:120000,expect:{timeout:15000},use:{baseURL:process.env.APP_URL||'http://localhost:3000',trace:'retain-on-failure',screenshot:'only-on-failure'},reporter:[['list'],['html',{open:'never'}]]})
