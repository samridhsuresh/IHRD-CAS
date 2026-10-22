export type User={id:number;username:string;full_name:string;role:'admin'|'teacher';must_change_password:boolean;can_manage_students:boolean};
export type Cls={id:number;name:string;department_id:number;course_id:number;semester:number;academic_year:string;start_time:string;grace_minutes:number;active:boolean};
const base=import.meta.env.VITE_API_BASE||'';
let csrfToken='';
export async function api<T=any>(path:string,opts:RequestInit={}):Promise<T>{
 const method=opts.method||'GET';const headers:Record<string,string>={...(opts.headers as Record<string,string>||{})};
 if(opts.body&&!(opts.body instanceof FormData))headers['Content-Type']='application/json';
 if(method!=='GET'&&method!=='HEAD')headers['X-CSRF-Token']=csrfToken;
 let res:Response;
 try{res=await fetch(base+'/api'+path,{...opts,method,headers,credentials:'include',cache:'no-store'})}catch{throw new Error('Cannot reach CampusTrack. Check your connection and retry.')}
 if(!res.ok){let detail='Request failed';try{const data=await res.json();detail=typeof data.detail==='string'?data.detail:JSON.stringify(data.detail)}catch{}throw new Error(detail)}
 const data=await res.json();if((path==='/auth/login'||path==='/auth/me')&&data.csrf)csrfToken=data.csrf;return data;
}
export async function download(path:string,filename:string){const res=await fetch(base+'/api'+path,{credentials:'include'});if(!res.ok)throw new Error('Export failed');const url=URL.createObjectURL(await res.blob());const a=document.createElement('a');a.href=url;a.download=filename;a.click();URL.revokeObjectURL(url)}
