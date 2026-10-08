import { createRouter, createWebHistory } from 'vue-router'
import { useSession } from '../stores/session'
import { auth, waitForAuth } from '../services/auth'
import AppShell from '../layouts/AppShell.vue'
export const router=createRouter({history:createWebHistory(),routes:[
  {path:'/login',component:()=>import('../views/LoginView.vue')},
  {path:'/',component:AppShell,children:[
    {path:'',component:()=>import('../views/DashboardView.vue'),meta:{title:'Overview'}},
    {path:'request/:kind(vacation|mobile)',component:()=>import('../views/RequestView.vue'),meta:{title:'New request'}},
    {path:'requests',component:()=>import('../views/RequestsView.vue'),meta:{title:'My requests'}},
    {path:'balances',component:()=>import('../views/BalancesView.vue'),meta:{title:'Leave balances'}},
    {path:'calendar',component:()=>import('../views/CalendarPage.vue'),meta:{title:'Team calendar'}},
    {path:'approvals',component:()=>import('../views/RequestsView.vue'),meta:{title:'Approval inbox',roles:['MANAGER','HR']}},
    {path:'team',component:()=>import('../views/PeopleView.vue'),meta:{title:'My team',roles:['MANAGER']}},
    {path:'employees',component:()=>import('../views/PeopleView.vue'),meta:{title:'Employees',roles:['HR','ADMIN']}},
    {path:'policies',component:()=>import('../views/PoliciesView.vue'),meta:{title:'Policies & holidays',roles:['HR','ADMIN']}},
    {path:'reports',component:()=>import('../views/ReportsView.vue'),meta:{title:'Reports',roles:['HR','MANAGER']}},
    {path:'settings',component:()=>import('../views/SettingsView.vue'),meta:{title:'Settings',roles:['ADMIN']}},
    {path:'notifications',component:()=>import('../views/AccountView.vue'),meta:{title:'Notifications'}},
    {path:'profile',component:()=>import('../views/AccountView.vue'),meta:{title:'My profile'}},
  ]},{path:'/:pathMatch(.*)*',redirect:'/'}]})
router.beforeEach(async to=>{await waitForAuth();if(to.path==='/login')return; if(!auth.authenticated)return '/login';const roles=to.meta.roles as string[]|undefined;if(roles&&!useSession().has(...roles))return '/'})
router.afterEach(to=>{document.title=`${String(to.meta.title||'Welcome')} · Workleave`})
