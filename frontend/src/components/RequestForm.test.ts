import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { ref } from 'vue'
const mocks=vi.hoisted(()=>({post:vi.fn(),push:vi.fn()}))
vi.mock('vue-router',()=>({useRouter:()=>({push:mocks.push})}))
vi.mock('../services/api',()=>({post:mocks.post}))
vi.mock('../composables/query',()=>({useApi:()=>({data:ref([{id:1,name:'Annual leave'}]),loading:ref(false),error:ref(null)}),refreshData:vi.fn()}))
import RequestForm from './RequestForm.vue'
describe('request submission',()=>{
  it('previews dates and sends the real form contract',async()=>{mocks.post.mockImplementation((path:string)=>Promise.resolve(path.endsWith('preview')?{days:'1',exceptions:[],years:[{year:2027,days:'1',available:'25'}]}:{id:1}));const wrapper=mount(RequestForm,{props:{kind:'LEAVE'},global:{plugins:[createPinia()]}});const dates=wrapper.findAll('input[type="date"]');await dates[0]!.setValue('2027-02-01');await dates[1]!.setValue('2027-02-01');await flushPromises();expect(wrapper.text()).toContain('1 working days');await wrapper.find('form').trigger('submit');await flushPromises();expect(mocks.post).toHaveBeenCalledWith('/requests',expect.objectContaining({kind:'LEAVE',start_date:'2027-02-01',end_date:'2027-02-01',submit:true}));expect(mocks.push).toHaveBeenCalledWith('/requests')})
})
