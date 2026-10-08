import { it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
vi.mock('../services/auth',()=>({logout:vi.fn()}))
import { useSession } from '../stores/session'
import NavigationSidebar from './NavigationSidebar.vue'
it('opens mobile navigation and hides management from an employee',async()=>{const pinia=createPinia();setActivePinia(pinia);const session=useSession();session.user={id:2,first_name:'Jamie',last_name:'Parker',roles:['EMPLOYEE']} as any;session.sidebarOpen=true;const wrapper=mount(NavigationSidebar,{global:{plugins:[pinia],stubs:{RouterLink:{template:'<a><slot/></a>'}}}});expect(wrapper.find('aside').classes()).toContain('open');expect(wrapper.text()).not.toContain('Approval inbox');await wrapper.find('[aria-label="Close navigation"]').trigger('click');expect(session.sidebarOpen).toBe(false)})
