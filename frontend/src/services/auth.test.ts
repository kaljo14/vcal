import { afterEach, expect, it, vi } from 'vitest'
import { auth, bindClerkSession, getAccessToken, login, logout } from './auth'
afterEach(()=>bindClerkSession(null,()=>{}))
it('gets a current Clerk token for every API call',async()=>{
  const getToken=vi.fn().mockResolvedValueOnce('first').mockResolvedValueOnce('refreshed')
  bindClerkSession({sessionId:'sess_one',getToken,signOut:vi.fn()},()=>{})
  expect(auth.authenticated).toBe(true)
  expect(await getAccessToken()).toBe('first')
  expect(await getAccessToken()).toBe('refreshed')
  expect(getToken).toHaveBeenCalledTimes(2)
})
it('clears the session on sign-out and delegates to Clerk',async()=>{
  const signOut=vi.fn().mockResolvedValue(undefined),signIn=vi.fn()
  bindClerkSession({sessionId:'sess_one',getToken:async()=> 'token',signOut},signIn)
  login();expect(signIn).toHaveBeenCalledOnce()
  await logout();expect(signOut).toHaveBeenCalledOnce()
  bindClerkSession(null,signIn)
  expect(auth.authenticated).toBe(false);expect(await getAccessToken()).toBeNull()
})
it('rejects a token obtained while the active account changed',async()=>{
  let resolve:(value:string)=>void=()=>{}
  bindClerkSession({sessionId:'sess_old',getToken:()=>new Promise(r=>resolve=r),signOut:vi.fn()},()=>{})
  const pending=getAccessToken()
  bindClerkSession({sessionId:'sess_new',getToken:async()=> 'new',signOut:vi.fn()},()=>{})
  resolve('old')
  await expect(pending).rejects.toThrow('session changed')
  expect(await getAccessToken()).toBe('new')
})
