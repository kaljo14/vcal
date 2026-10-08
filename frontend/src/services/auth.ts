/** The Clerk Vue provider owns session storage and token refresh. No token is persisted here. */
type SessionBridge = {
  sessionId: string
  getToken: () => Promise<string | null>
  signOut: () => Promise<void>
}
let session: SessionBridge | null = null
let openSignIn: (() => void) | null = null
let resolveReady: () => void
const ready = new Promise<void>(resolve => { resolveReady = resolve })
export const auth = {
  get authenticated() { return session !== null },
  get sessionId() { return session?.sessionId ?? null },
}
export function bindClerkSession(value: SessionBridge | null, signIn: () => void) {
  session = value
  openSignIn = signIn
}
export function finishAuthInitialization() { resolveReady() }
export function waitForAuth() { return ready }
export async function getAccessToken() {
  const current = session
  if (!current) return null
  const token = await current.getToken()
  if (current !== session) throw new Error('Your session changed. Please try again.')
  return token
}
export function login() {
  if (!openSignIn) throw new Error('Clerk is still loading. Please try again.')
  openSignIn()
}
export async function logout() { await session?.signOut() }
