const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000/api/v1";
export async function api<T=unknown>(path:string,init:RequestInit={}):Promise<T>{
 const multipart=typeof FormData!=="undefined"&&init.body instanceof FormData;const res=await fetch(API+path,{...init,credentials:"include",headers:{...(multipart?{}:{"Content-Type":"application/json"}),...(init.headers||{})}});
 if(!res.ok){let message=`So‘rov xatosi (${res.status})`;try{message=(await res.json()).detail||message}catch{};if(res.status===401&&typeof window!=="undefined"&&!path.startsWith("/auth/"))window.location.href="/login";throw new Error(message)}
 if(res.status===204)return undefined as T;return res.json() as Promise<T>
}
export async function downloadReport(path:string,filename:string){const r=await fetch(API+path,{credentials:"include"});if(!r.ok)throw new Error("Hisobotni yuklab bo‘lmadi");const blob=await r.blob();const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=filename;a.click();URL.revokeObjectURL(url)}
