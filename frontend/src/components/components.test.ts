import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { validateDates } from '../services/dates'
import DateRangePicker from './DateRangePicker.vue'
import BalanceCard from './BalanceCard.vue'
import StatusBadge from './StatusBadge.vue'
import ApprovalCard from './ApprovalCard.vue'
import type { WorkRequest } from '../types'

describe('request date validation',()=>{
  it('requires both dates',()=>expect(validateDates('','','FULL')).toContain('Choose'))
  it('rejects reversed dates',()=>expect(validateDates('2027-02-03','2027-02-01','FULL')).toContain('End date'))
  it('rejects a half-day range',()=>expect(validateDates('2027-02-01','2027-02-02','AM')).toContain('single date'))
  it('permits a single afternoon',()=>expect(validateDates('2027-02-01','2027-02-01','PM')).toBe(''))
  it('emits selected dates and constrains end date',async()=>{const wrapper=mount(DateRangePicker,{props:{start:'2027-02-01',end:'2027-02-02'}});await wrapper.findAll('input')[0]!.setValue('2027-02-03');expect(wrapper.emitted('update:start')?.[0]).toEqual(['2027-02-03']);expect(wrapper.findAll('input')[1]!.attributes('min')).toBe('2027-02-01')})
})
it('displays the backend balance without rounding away half days',()=>{const wrapper=mount(BalanceCard,{props:{label:'Vacation balance',value:'12.5',caption:'Available'}});expect(wrapper.text()).toContain('12.5');expect(wrapper.text()).toContain('Vacation balance')})
it('labels cancellation pending clearly',()=>expect(mount(StatusBadge,{props:{status:'CANCELLATION_REQUESTED'}}).text()).toContain('Cancellation pending'))
const request:WorkRequest={id:1,employee_id:2,employee_name:'Jamie Parker',kind:'LEAVE',start_date:'2027-02-01',end_date:'2027-02-01',status:'PENDING',label:'Annual leave',days:1,portion:'FULL',exception_flags:[],can_approve:true,requires_justification:false}
it('emits approval intent for the selected request',async()=>{const wrapper=mount(ApprovalCard,{props:{request}});await wrapper.findAll('button').find(b=>b.text().includes('Approve'))!.trigger('click');expect(wrapper.emitted('decide')?.[0]).toEqual([request,'approve'])})
it('does not present actions to an unauthorized reviewer',()=>{const wrapper=mount(ApprovalCard,{props:{request:{...request,can_approve:false}}});expect(wrapper.findAll('button').some(b=>b.text()==='Approve')).toBe(false)})
