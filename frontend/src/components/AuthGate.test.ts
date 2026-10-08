import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
const mocks=vi.hoisted(()=>({api:vi.fn(),cancel:vi.fn(),clear:vi.fn(),replace:vi.fn(),ready:vi.fn(),bind:vi.fn(),finish:vi.fn(),logout:vi.fn()}))
let state: ReturnType<typeof makeState>
function makeState(){return {isLoaded:ref(true),isSignedIn:ref(true),sessionId:ref<string|null>('sess_one'),getToken:ref(async()=> 'token')}}
vi.mock('@clerk/vue',()=>({useAuth:()=>state,useClerk:()=>ref({signOut:vi.fn(),openSignIn:vi.fn()})}))
vi.mock('vue-router',()=>({useRouter:()=>({replace:mocks.replace,isReady:mocks.ready,currentRoute:{value:{path:'/login',meta:{}}}})}))
vi.mock('../services/api',()=>({api:mocks.api}))
vi.mock('../services/auth',()=>({auth:{sessionId:null},bindClerkSession:mocks.bind,finishAuthInitialization:mocks.finish,logout:mocks.logout}))
vi.mock('../composables/query',()=>({queryClient:{cancelQueries:mocks.cancel,clear:mocks.clear}}))
import AuthGate from './AuthGate.vue'
import { useSession } from '../stores/session'
let wrapper:VueWrapper|undefined
beforeEach(()=>{vi.clearAllMocks();state=makeState();setActivePinia(createPinia());mocks.cancel.mockResolvedValue(undefined);mocks.ready.mockResolvedValue(undefined);mocks.replace.mockResolvedValue(undefined);mocks.api.mockResolvedValue({id:2,first_name:'Jamie',roles:['EMPLOYEE']})})
afterEach(()=>wrapper?.unmount())
function render(){wrapper=mount(AuthGate,{global:{plugins:[createPinia()],stubs:{RouterView:{template:'<div>Authorized workspace</div>'}}}});return wrapper}
it('waits for Clerk before rendering the workspace',async()=>{state.isLoaded.value=false;render();expect(wrapper!.text()).toContain('Connecting');expect(mocks.api).not.toHaveBeenCalled();state.isLoaded.value=true;await flushPromises();expect(wrapper!.text()).toContain('Authorized workspace');expect(mocks.finish).toHaveBeenCalled();expect(mocks.replace).toHaveBeenCalledWith('/')})
it('offers sign-out when the Clerk identity has no employee account',async()=>{mocks.api.mockRejectedValue(new Error('No active employee account'));render();await flushPromises();expect(wrapper!.text()).toContain('No active employee account');expect(wrapper!.text()).not.toContain('Authorized workspace');await wrapper!.findAll('button').find(b=>b.text()==='Sign out')!.trigger('click');expect(mocks.logout).toHaveBeenCalled()})
it('clears employee data and query cache when the session ends',async()=>{render();await flushPromises();state.isSignedIn.value=false;state.sessionId.value=null;await flushPromises();expect(useSession().user).toBeNull();expect(mocks.clear).toHaveBeenCalledTimes(2);expect(mocks.replace).toHaveBeenCalledWith('/login')})
it('discards a delayed employee response from an earlier session',async()=>{let resolve:(value:any)=>void=()=>{};mocks.api.mockImplementationOnce(()=>new Promise(r=>resolve=r)).mockResolvedValue({id:5,roles:['EMPLOYEE']});render();await flushPromises();state.sessionId.value='sess_two';await flushPromises();resolve({id:2,roles:['ADMIN']});await flushPromises();expect(useSession().user?.id).toBe(5)})
