import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../services/api'
import { auth } from '../services/auth'
import type { Employee } from '../types'
export const useSession = defineStore('session',()=>{
  const user=ref<Employee|null>(null), sidebarOpen=ref(false), toast=ref('')
  let timer:ReturnType<typeof setTimeout>
  async function load(){ const identity=auth.sessionId; const employee=await api<Employee>('/me'); if(identity===auth.sessionId)user.value=employee }
  function has(...roles:string[]){return !!user.value?.roles.some(r=>roles.includes(r))}
  function message(text:string){toast.value=text;clearTimeout(timer);timer=setTimeout(()=>toast.value='',5000)}
  return {user,sidebarOpen,toast,load,has,message}
})
