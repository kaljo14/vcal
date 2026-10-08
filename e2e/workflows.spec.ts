import { test, expect, type Browser, type Page } from '@playwright/test'
import { clerk } from '@clerk/testing/playwright'
async function login(browser:Browser,role:string){
 const email=process.env[`E2E_${role.toUpperCase()}_EMAIL`]
 if(!email)throw new Error(`Set E2E_${role.toUpperCase()}_EMAIL to a linked Clerk test account.`)
 const context=await browser.newContext();const page=await context.newPage()
 await page.goto('/login')
 await clerk.signIn({page,emailAddress:email})
 await page.goto('/')
 await expect(page.getByRole('heading',{name:/Hey/})).toBeVisible()
 return{page,context}
}
async function authHeaders(page:Page){
 const token=await page.evaluate(async()=>await (window as any).Clerk.session.getToken())
 return {Authorization:`Bearer ${token}`}
}
const iso=(date:Date)=>`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`
async function request(page:Page,kind:string,day:string){await page.goto('/request/'+kind);await page.getByLabel('Start date',{exact:true}).fill(day);await page.getByLabel('End date',{exact:true}).fill(day);await expect(page.getByRole('button',{name:'Submit request'})).toBeEnabled();const response=page.waitForResponse(r=>r.url().endsWith('/api/v1/requests')&&r.request().method()==='POST');await page.getByRole('button',{name:'Submit request'}).click();const result=await response;expect(result.status()).toBe(201);return (await result.json()).id as number}

test('real Clerk sessions, vacation accounting, calendar, mobile rejection, policies and authorization',async({browser})=>{
 const employee=await login(browser,'employee'),manager=await login(browser,'manager'),hr=await login(browser,'hr');
 const api=employee.context.request;
 const before=await (await api.get('/api/v1/me/balances',{headers:await authHeaders(employee.page)})).json();
 const holidays=await (await api.get('/api/v1/holidays',{headers:await authHeaders(employee.page)})).json();
 const blocked=new Set(holidays.map((h:any)=>h.date));const days:string[]=[];const day=new Date();day.setDate(day.getDate()+21);while(days.length<3){if(day.getDay()>0&&day.getDay()<6&&!blocked.has(iso(day)))days.push(iso(day));day.setDate(day.getDate()+1)}
 const vacation=await request(employee.page,'vacation',days[0]!);
 const denied=await api.post(`/api/v1/requests/${vacation}/approve`,{headers:await authHeaders(employee.page),data:{}});expect(denied.status()).toBe(403);
 await manager.page.goto('/approvals');const card=manager.page.locator('.approval-card').filter({hasText:'Jamie Parker'}).filter({hasText:'Annual paid leave'}).first();await card.getByRole('button',{name:'Approve',exact:true}).click();await manager.page.getByRole('button',{name:'Confirm approve'}).click();await expect(manager.page.getByRole('dialog')).not.toBeVisible();
 await employee.page.goto('/balances');await expect(employee.page.locator('.balance-card').first()).toContainText(String(Number(before[0].available)-1));
 const calendar=await(await api.get(`/api/v1/calendar?start=${days[0]}&end=${days[0]}`,{headers:await authHeaders(employee.page)})).json();expect(calendar.events.some((e:any)=>e.kind==='LEAVE'&&e.status==='APPROVED'&&e.employee_id===2)).toBe(true);
 await employee.page.goto(`/calendar?date=${days[0]}`);await expect(employee.page.locator('.fc-event').filter({hasText:'Jamie Parker'}).first()).toBeVisible();
 const mobile=await request(employee.page,'mobile',days[1]!);await manager.page.goto('/approvals');const remote=manager.page.locator('.approval-card').filter({hasText:'Jamie Parker'}).filter({hasText:'Mobile work'}).first();await remote.getByRole('button',{name:'Decline'}).click();await manager.page.getByLabel('Reason for declining').fill('Team workshop in the office');await manager.page.getByRole('button',{name:'Confirm reject'}).click();await expect(manager.page.getByRole('dialog')).not.toBeVisible();
 await employee.page.goto(`/requests?selected=${mobile}`);await expect(employee.page.getByRole('dialog')).toContainText('Team workshop in the office');
 await hr.page.goto('/policies');await hr.page.getByRole('button',{name:'Edit Flexible working',exact:true}).click();await hr.page.getByLabel('Monthly limit',{exact:true}).fill('0');await hr.page.getByRole('button',{name:'Save changes'}).click();await expect(hr.page.getByRole('dialog')).not.toBeVisible();
 const blockedRequest=await api.post('/api/v1/requests',{headers:await authHeaders(employee.page),data:{kind:'MOBILE',start_date:days[2],end_date:days[2],location_type:'HOME'}});expect(blockedRequest.status()).toBe(409);
 // Restore policy and reverse the approved leave so this scenario is repeatable.
 await hr.page.getByRole('button',{name:'Edit Flexible working',exact:true}).click();await hr.page.getByLabel('Monthly limit',{exact:true}).fill('8');await hr.page.getByRole('button',{name:'Save changes'}).click();
 expect((await api.post(`/api/v1/requests/${vacation}/cancel`,{headers:await authHeaders(employee.page),data:{}})).status()).toBe(200);
 expect((await manager.context.request.post(`/api/v1/requests/${vacation}/approve`,{headers:await authHeaders(manager.page),data:{}})).status()).toBe(200);
 for(const user of [employee,manager,hr])await user.context.close();
})

test('mobile navigation supports the employee flow',async({browser})=>{const employee=await login(browser,'employee');await employee.page.setViewportSize({width:390,height:844});await employee.page.getByRole('button',{name:'Open navigation'}).click();await employee.page.getByRole('link',{name:'My requests',exact:true}).click();await expect(employee.page.getByRole('heading',{name:'My requests'})).toBeVisible();await expect(employee.page.locator('.sidebar')).not.toHaveClass(/open/);await employee.context.close()})
