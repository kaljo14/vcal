import { clerkSetup } from '@clerk/testing/playwright'
export default async function globalSetup() {
  const required=['CLERK_PUBLISHABLE_KEY','CLERK_SECRET_KEY','E2E_EMPLOYEE_EMAIL','E2E_MANAGER_EMAIL','E2E_HR_EMAIL']
  for(const key of required)if(!process.env[key])throw new Error(`Missing ${key}: Clerk E2E requires an isolated development instance and linked test users.`)
  if(!process.env.CLERK_PUBLISHABLE_KEY!.startsWith('pk_test_')||!process.env.CLERK_SECRET_KEY!.startsWith('sk_test_'))throw new Error('Use a Clerk development instance for E2E, never production keys.')
  await clerkSetup()
}
