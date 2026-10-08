import { getAccessToken } from './auth'
export class ApiError extends Error { constructor(message:string, public status:number, public code:string) { super(message) } }
export async function api<T>(path:string, options:RequestInit = {}):Promise<T> {
  const token = await getAccessToken()
  const response = await fetch('/api/v1'+path, { ...options, headers: { 'Content-Type':'application/json', ...(token ? {Authorization:`Bearer ${token}`} : {}), ...options.headers } })
  if (!response.ok) { const body = await response.json().catch(()=>({})); throw new ApiError(body.error?.message || 'Something went wrong. Please try again.', response.status, body.error?.code || 'unknown') }
  if(response.status===204) return undefined as T
  return response.json()
}
export function post<T>(path:string, data:unknown = {}) { return api<T>(path,{method:'POST',body:JSON.stringify(data)}) }
export function patch<T>(path:string, data:unknown) { return api<T>(path,{method:'PATCH',body:JSON.stringify(data)}) }
export async function downloadReport(path:string) {
  const token = await getAccessToken()
  if (!token) throw new ApiError("Sign in to export reports.", 401, "unauthorized")
  const response = await fetch('/api/v1'+path,{headers:{Authorization:`Bearer ${token}`}})
  if(!response.ok) throw new Error('The report could not be exported.')
  const url=URL.createObjectURL(await response.blob()); const link=document.createElement('a'); link.href=url; link.download='workleave-report.csv'; link.click(); URL.revokeObjectURL(url)
}
