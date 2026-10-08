export function isoDate(date=new Date()) { return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}` }
export function shortDate(value:string) { return new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short'}).format(new Date(value+'T12:00:00')) }
export function dateRange(start:string,end:string){ return start===end?shortDate(start):`${shortDate(start)} – ${shortDate(end)}` }
export function validateDates(start:string,end:string,portion:string) { if(!start||!end)return 'Choose a start and end date.';if(end<start)return 'End date must be on or after the start date.';if(portion!=='FULL'&&start!==end)return 'Half-day requests must be for a single date.';return '' }
