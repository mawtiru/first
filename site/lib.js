export const labels={equipment:'装置メーカー',parts:'部品・コンポーネント',materials:'化学製品・材料',services:'加工・運用サービス'};
export const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function safeUrl(value){try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password}catch{return false}}
export function percentage(part,total,status){if(status==='undisclosed')return '非開示';if(status!=='verified')return '未確認';if(!Number.isFinite(part)||!Number.isFinite(total))return '数値未登録';if(total===0)return '算出不可（全社がゼロ）';if(part<0||total<0)return '赤字のため比率表示なし';return `${(part/total*100).toFixed(1)}%`}
export function matchingCompanies(companies,filters){const q=filters.query.trim().toLowerCase();return companies.filter(c=>(filters.category==='all'||c.category===filters.category)&&[c.name,c.country,c.products,...c.aliases].join(' ').toLowerCase().includes(q))}
export function comparableMarkets(markets,companyId){return markets.filter(m=>['verified','estimated'].includes(m.status)&&m.rows.some(r=>r.companyId===companyId))}
export function formatDate(value){if(!value)return '未実施';const d=new Date(value);if(Number.isNaN(d.getTime()))return '日時不明';return new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',dateStyle:'medium',timeStyle:'short'}).format(d)}
export function formatMarketCap(record){if(!record||!Number.isFinite(record.value)||record.value<=0)return '未取得';const n=record.value;const [scale,unit]=n>=1e12?[1e12,'兆']:n>=1e8?[1e8,'億']:n>=1e4?[1e4,'万']:[1,''];const currency={USD:'米ドル',JPY:'円',EUR:'ユーロ'}[record.currency]||record.currency;return `約${(n/scale).toLocaleString('ja-JP',{maximumFractionDigits:2})}${unit}${currency}`}
export function mapSearchUrl(facility){return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${facility.name} ${facility.location}`)}`}

export function companiesForStage(companies,stageId){return companies.filter(c=>c.stageIds.includes(stageId)).map(c=>({...c,category:c.stageCategories?.[stageId]||c.category}))}
export function parseRoute(hash){
 const value=hash.replace(/^#/,'');
 const [path,query]=value.split('?');
 if(!path||path==='/')return {type:'home'};
 if(path==='/manufacturers')return {type:'manufacturers'};
 const match=path.match(/^\/(stage|infrastructure|company|manufacturer)\/([^/]+)$/);
 if(!match)return {type:'notFound'};
 try{return {type:match[1],id:decodeURIComponent(match[2]),fromStage:new URLSearchParams(query||'').get('stage'),fromInfrastructure:new URLSearchParams(query||'').get('infrastructure')}}catch{return {type:'notFound'}}
}

export function companiesForInfrastructure(companies,id){return companies.filter(c=>(c.infrastructureIds||[]).includes(id)).map(c=>({...c,category:c.infrastructureCategories?.[id]||c.category}))}

export const manufacturerModels={foundry:"ファウンドリー（製造受託）",fabless:"ファブレス（設計）",idm:"IDM（設計・製造）",osat:"OSAT（組立・テスト受託）"};
export function matchingManufacturers(companies,{query,model,type='all'}){const q=query.trim().toLowerCase();return companies.filter(c=>(model==='all'||c.model===model)&&(type==='all'||(c.types||[]).includes(type))&&[c.name,c.country,c.products,c.id].join(' ').toLowerCase().includes(q))}
export const semiconductorTypes={logic:"ロジック",memory:"メモリ",power:"パワー",analog:"アナログ",rf:"通信・RF",sensor:"センサー"};

export function manufacturingPartners(catalog,id){return (catalog.manufacturingRelationships||[]).filter(r=>r.customerId===id||r.foundryId===id).map(r=>({...r,partner:(catalog.manufacturers||[]).find(c=>c.id===(r.customerId===id?r.foundryId:r.customerId))}))}
