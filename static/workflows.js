// Development workflows and browser-local reusable setup recipes.
const workflowSpecs={
 invoke:['Invoke Lambda',[['event','JSON event','{}']]],
 upload:['Upload S3 object',[['key','Object key',''],['file','File (maximum 750 KB)','','file']]],
 download:['Download / preview object',[['key','Object key','']]],
 delete_object:['Delete object',[['key','Object key','']]],
 browse:['Browse prefix',[['prefix','Key prefix','']]],
 ack:['Acknowledge message',[['receipt','Receipt handle from Receive','']]],
 visibility:['Change message visibility',[['receipt','Receipt handle',''],['seconds','Visibility seconds','30']]],
 purge:['Purge queue',[]],
 subscribe:['Connect SQS queue',[['queueUrl','Queue URL',''],['raw','Raw message delivery',false,'checkbox']]],
 unsubscribe:['Remove subscription',[['subscription','Subscription ARN','']]],
 put:['Add / replace item',[['item','Item (DynamoDB attribute-value JSON)','{"id":{"S":"example"}}']]],
 delete_item:['Delete item',[['key','Key (include partition and sort keys)','{"id":{"S":"example"}}']]],
 query:['Query items',[['expression','Key condition expression','#pk = :value'],['names','Attribute names JSON','{"#pk":"id"}'],['values','Attribute values JSON','{":value":{"S":"example"}}']]],
 delete:['Delete resource',[]]
};
function readStore(key,fallback){try{return JSON.parse(localStorage.getItem(key))||fallback;}catch{return fallback;}}
function writeStore(key,value){localStorage.setItem(key,JSON.stringify(value));}
function output(data,title){$('detailPanel').hidden=false;$('detailTitle').textContent=title;$('detail').textContent=JSON.stringify(data,null,2);}
function downloadFile(bytes,name,type){const url=URL.createObjectURL(new Blob([bytes],{type}));const a=el('a','');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
const workDialog=document.createElement('dialog');
workDialog.innerHTML='<form><h2></h2><p></p><div class="workfields"></div><div class="tools"><button type="button" class="save">Save payload</button><button type="button" class="cancel">Cancel</button><button type="submit" class="primary">Run</button></div><p class="workerror" role="alert"></p></form>';
document.body.append(workDialog);
let workContext=null;
function work(action){
 const [title,fields]=workflowSpecs[action];
 workContext={service,action,resource:selected,region:$('region').value};
 const form=workDialog.querySelector('form'),container=form.querySelector('.workfields');container.replaceChildren();
 form.querySelector('h2').textContent=title;
 form.querySelector('p').textContent=selected+' · '+workContext.region;
 form.querySelector('.workerror').textContent='';
 const saved=readStore('console-payloads',{});
 const matching=Object.entries(saved).filter(([,v])=>v.service===service&&v.action===action);
 if(matching.length){const label=el('label','Load saved payload'),select=document.createElement('select');select.append(el('option','Choose saved payload…'));for(const [name] of matching){const o=el('option',name);o.value=name;select.append(o);}select.onchange=()=>{const v=saved[select.value];if(v)for(const input of container.querySelectorAll('[name]'))if(input.type!=='file'&&v.payload[input.name]!==undefined){if(input.type==='checkbox')input.checked=v.payload[input.name];else input.value=v.payload[input.name];}};container.append(label,select);}
 for(const [name,label,value,type] of fields){const wrap=el('div','','formfield'),lab=el('label',label);const input=document.createElement(type?'input':'textarea');input.name=name;input.id='work-'+name;lab.htmlFor=input.id;if(type)input.type=type;if(type==='checkbox')input.checked=value;else if(type!=='file')input.value=value;input.required=!['prefix','names','raw'].includes(name);wrap.append(lab,input);container.append(wrap);}
 form.querySelector('.save').hidden=!fields.length;
 workDialog.showModal();
}
function workValues(){const p={};for(const input of workDialog.querySelectorAll('[name]'))if(input.type!=='file')p[input.name]=input.type==='checkbox'?input.checked:input.value;return p;}
workDialog.querySelector('.cancel').onclick=()=>workDialog.close();
workDialog.querySelector('.save').onclick=()=>{try{const name=prompt('Payload name (stored in this browser)');if(!name)return;const saved=readStore('console-payloads',{});saved[name]={...workContext,payload:workValues()};writeStore('console-payloads',saved);}catch(e){workDialog.querySelector('.workerror').textContent=e.message;}};
workDialog.querySelector('form').onsubmit=async e=>{
 e.preventDefault();const ctx={...workContext},p=workValues(),buttons=[...workDialog.querySelectorAll('button')];
 if(['delete','delete_object','delete_item','ack','purge','unsubscribe','put','empty_bucket','update_code','upload_zip','update_config','update_value'].includes(ctx.action)&&!confirm(ctx.service==='secretsmanager'&&ctx.action==='delete'?(p.forceDelete?'Permanently delete secret ':'Schedule deletion in 7 days for secret ')+ctx.resource+'?':'Confirm '+workflowSpecs[ctx.action][0]+' for '+ctx.resource+'?'+(ctx.action==='put'?' An existing item with this key will be replaced.':'')))return;
 buttons.forEach(b=>b.disabled=true);
 try{
  if(['upload','upload_zip'].includes(ctx.action)){const file=workDialog.querySelector('[type=file]').files[0];if(!file||file.size>750000)throw Error('Choose a file no larger than 750 KB.');const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(const b of bytes)binary+=String.fromCharCode(b);p.data=btoa(binary);p.contentType=file.type;}
  let data=await api(ctx.action==='browse'?'detail':ctx.action,{...p,resource:ctx.resource,region:ctx.region},ctx.service);
  if(ctx.action==='download'){const bytes=Uint8Array.from(atob(data.data),c=>c.charCodeAt(0));downloadFile(bytes,p.key.split('/').pop(),data.contentType);data={key:p.key,bytes:bytes.length,preview:new TextDecoder().decode(bytes.slice(0,16000))};}
  workDialog.close();
  if(ctx.service==='s3'&&service==='s3'&&selected===ctx.resource&&$('region').value===ctx.region&&['upload','delete_object','empty_bucket','browse'].includes(ctx.action)&&typeof s3Refresh==='function'){
   await s3Refresh(ctx.resource,ctx.action==='browse'?p.prefix:undefined);
   return;
  }
  if(service===ctx.service&&$('region').value===ctx.region){if(ctx.action==='delete')await load();else {output(data,workflowSpecs[ctx.action][0]+' · '+ctx.resource);let token=data.NextContinuationToken||data.LastEvaluatedKey;
   if(token&&['browse','query','filtered_scan'].includes(ctx.action)){
    const next=el('button','Next results');
    next.onclick=async()=>{next.disabled=true;try{const more=await api(ctx.action==='browse'?'detail':ctx.action,{...p,resource:ctx.resource,region:ctx.region,cursor:token},ctx.service);output(more,workflowSpecs[ctx.action][0]+' · '+ctx.resource);token=more.NextContinuationToken||more.LastEvaluatedKey;if(!token)next.remove();}catch(e){error(e);}finally{next.disabled=false;}};
    $('actions').append(next);
   }
  }}
 }catch(e){workDialog.querySelector('.workerror').textContent=e.message;}
 finally{buttons.forEach(b=>b.disabled=false);}
};
workDialog.addEventListener('cancel',e=>{if(workDialog.querySelector('[type=submit]').disabled)e.preventDefault();});
const baseDetail=detail;
detail=async function(...args){const target=service,id=requestId;await baseDetail(...args);if(target!==service||id!==requestId||selected!==args[0]||$('detailPanel').hidden)return;
 const actions={s3:['browse','upload','download','delete_object'],sqs:['ack','visibility','purge'],sns:['subscribe','unsubscribe'],lambda:['invoke'],dynamodb:['put','delete_item','query']}[service]||[];
 for(const action of [...actions,'delete']){const b=el('button',workflowSpecs[action][0]);b.onclick=()=>work(action);$('actions').append(b);}
 if(service==='sns'){const b=el('button','List subscriptions');b.onclick=async()=>{try{output(await api('subscriptions',{resource:selected}),'Subscriptions');}catch(e){error(e);}};$('actions').append(b);}
};
// Record successful replayable setup operations, never invocations or destructive actions.
const baseApi=api;
let replaying=false;
api=async function(action,extra={},target=service){const result=await baseApi(action,extra,target);
 if(!replaying&&!['secretsmanager','ssm'].includes(target)&&['create','upload','put','subscribe'].includes(action)){
  try{const steps=readStore('console-recipe',[]);steps.push({service:target,action,params:{region:$('region').value,...extra}});writeStore('console-recipe',steps);}catch(e){$('notice').textContent='Operation succeeded, but the setup recipe could not be saved: '+e.message;$('notice').hidden=false;}
 }
 return result;
};
const workspace=el('section','','panel'),head=el('div','','panelhead'),title=el('div',''),tools=el('div','','tools');
title.append(el('h2','Development recipes'),el('p','Setup actions made here are saved in this browser. Export includes code and uploaded data; it is not a full LocalStack backup.'));
head.append(title,tools);workspace.append(head);$('summary').after(workspace);
function workspaceButton(label,fn){const b=el('button',label);b.onclick=async()=>{b.disabled=true;try{await fn();}catch(e){error(e);}finally{b.disabled=false;}};tools.append(b);}
workspaceButton('Export recipe',()=>downloadFile(JSON.stringify({version:1,steps:readStore('console-recipe',[]),payloads:readStore('console-payloads',{})},null,2),'localstack-recipe.json','application/json'));
workspaceButton('Clear recorded recipe',()=>{if(confirm('Clear browser recipe history? LocalStack resources and saved payloads are retained.'))writeStore('console-recipe',[]);});
async function replay(recipe){
 if(recipe.version!==1||!Array.isArray(recipe.steps))throw Error('Expected a version 1 console recipe.');
 for(const step of recipe.steps)if(!['s3','sqs','sns','lambda','dynamodb'].includes(step.service)||!['create','upload','put','subscribe'].includes(step.action)||!step.params||typeof step.params!=='object')throw Error('Recipe contains an unsupported step.');
 if(!confirm('Run '+recipe.steps.length+' setup steps? Existing items or files may be overwritten. Resources use each step’s recorded region. A failure leaves completed steps in place.'))return;
 replaying=true;const results=[];
 try{for(const step of recipe.steps){try{await api(step.action,step.params,step.service);results.push({service:step.service,action:step.action,status:'succeeded'});}catch(e){results.push({service:step.service,action:step.action,error:e.message});throw e;}}
 if(recipe.payloads&&typeof recipe.payloads==='object')writeStore('console-payloads',{...readStore('console-payloads',{}),...recipe.payloads});
 }finally{replaying=false;await load();output(results,'Recipe results');}
}
workspaceButton('Import and run',()=>new Promise(resolve=>{const input=document.createElement('input');input.type='file';input.accept='.json';input.oncancel=resolve;input.onchange=async()=>{try{const file=input.files[0];if(file.size>10000000)throw Error('Recipe exceeds 10 MB.');await replay(JSON.parse(await file.text()));}catch(e){error(e);}finally{resolve();}};input.click();}));
workspaceButton('Replay recorded',()=>replay({version:1,steps:readStore('console-recipe',[])}));
workspaceButton('SNS → SQS template',async()=>{
 const name=prompt('Name for a new standard topic and queue');if(!name)return;
 const region=$('region').value;
 const topic=await api('create',{name,region},'sns');
 const queue=await api('create',{name,region},'sqs');
 const result=await api('subscribe',{resource:topic.TopicArn,queueUrl:queue.QueueUrl,region,raw:true},'sns');
 await load();output({topic:topic.TopicArn,queue:queue.QueueUrl,subscription:result.SubscriptionArn},'SNS → SQS template created');
});
// Reuse saved payloads for the original SQS/SNS message forms too.
const baseCompose=compose;
compose=function(action){baseCompose(action);if(!['send','publish'].includes(action))return;
 const saved=readStore('console-payloads',{}),select=document.createElement('select');select.setAttribute('aria-label','Saved message payload');select.append(el('option','Load saved message…'));
 for(const [name,v] of Object.entries(saved))if(v.service===service&&v.action===action){const o=el('option',name);o.value=name;select.append(o);}
 select.onchange=()=>{const value=saved[select.value];if(value)$('f-body').value=value.payload.body;};
 const save=el('button','Save message payload');save.type='button';save.onclick=()=>{try{const name=prompt('Payload name (stored in this browser)');if(!name)return;const all=readStore('console-payloads',{});all[name]={service,action,payload:{body:$('f-body').value}};writeStore('console-payloads',all);}catch(e){$('formError').textContent=e.message;$('formError').hidden=false;}};
 $('fields').append(select,save);
};



