// Complete the existing service workflows and workspace tools.
Object.assign(workflowSpecs,{
 update_code:['Update function source',[['code','Source code · index.handler','']]],
 upload_zip:['Upload function ZIP',[['file','ZIP file (maximum 750 KB)','','file']]],
 update_config:['Update function configuration',[['runtime','Runtime (blank keeps current)',''],['handler','Handler (blank keeps current)',''],['timeout','Timeout seconds (blank keeps current)',''],['memory','Memory MB (blank keeps current)',''],['environment','Environment JSON (replaces all variables; blank keeps current)','']]],
 send_batch:['Send message batch',[['messages','JSON array of 1–10 strings or objects with body, attributes and group','["first message", "second message"]']]],
 empty_bucket:['Empty bucket (all versions)',[]],
 filtered_scan:['Filtered scan',[['expression','Filter expression (blank scans all items)','#field = :value'],['names','Attribute name aliases JSON','{"#field":"status"}'],['values','Typed attribute values JSON','{":value":{"S":"ready"}}']]]
});
const dailyWork=work;
work=function(action){dailyWork(action);
 if(action==='update_code')workDialog.querySelector('p').textContent+=' · Replaces the entire package with one source file. Use ZIP upload for dependencies.';
 if(action==='update_config')for(const f of workDialog.querySelectorAll('[name]'))f.required=false;
 if(action==='filtered_scan')workDialog.querySelector('[name=expression]').required=false;
 if(action==='update_code'||action==='update_config'){
  const ctx=workContext,submit=workDialog.querySelector('[type=submit]');submit.disabled=true;
  api(action==='update_code'?'source':'detail',{resource:ctx.resource,region:ctx.region},ctx.service).then(data=>{
   if(!workDialog.open||workContext!==ctx)return;
   if(action==='update_code')workDialog.querySelector('[name=code]').value=data.code;
   else for(const [field,key] of [['runtime','Runtime'],['handler','Handler'],['timeout','Timeout'],['memory','MemorySize']])workDialog.querySelector('[name='+field+']').value=data[key]??'';
   if(action==='update_config')workDialog.querySelector('[name=environment]').value=JSON.stringify(data.Environment?.Variables||{},null,2);
  }).catch(e=>{if(workContext===ctx)workDialog.querySelector('.workerror').textContent=e.message;}).finally(()=>{if(workContext===ctx)submit.disabled=false;});
 }
};
// Supply an API alias for filtered scan while preserving routing fields.
const dailyApi=api;
api=async function(action,extra={},target=service){return dailyApi(action==='filtered_scan'?'scan':action,extra,target);};
const dailyCompose=compose;
compose=function(action){dailyCompose(action);if(['send','publish'].includes(action)){
 inputField('attributes','Message attributes JSON',{type:'textarea',value:'{}',hint:'Example: {"kind":{"DataType":"String","StringValue":"order"}}'});
 const select=$('fields').querySelector('[aria-label="Saved message payload"]');
 const previous=select.onchange;select.onchange=()=>{previous();const v=readStore('console-payloads',{})[select.value];if(v)$('f-attributes').value=v.payload.attributes||'{}';};
 const save=[...$('fields').querySelectorAll('button')].find(b=>b.textContent==='Save message payload');
 save.onclick=()=>{try{const name=prompt('Payload name (stored in this browser)');if(!name)return;const all=readStore('console-payloads',{});all[name]={service:pending.service,action,payload:{body:$('f-body').value,attributes:$('f-attributes').value}};writeStore('console-payloads',all);}catch(e){$('formError').hidden=false;$('formError').textContent=e.message;}};
}};
const moreDetail=detail;
detail=async function(...args){const target=service,id=requestId;await moreDetail(...args);if(target!==service||id!==requestId||selected!==args[0]||$('detailPanel').hidden)return;
 const actions={lambda:['update_code','upload_zip','update_config'],sqs:['send_batch'],s3:['empty_bucket'],dynamodb:['filtered_scan']}[service]||[];
 for(const action of actions){const b=el('button',workflowSpecs[action][0]);b.onclick=()=>work(action);$('actions').append(b);}
 const copy=el('button','Copy resource identifier');copy.onclick=()=>navigator.clipboard.writeText(selected).catch(error);
 const snippets=el('button','CLI / boto3 snippets');snippets.onclick=()=>showSnippets(target,args[0]);
 $('actions').append(copy,snippets);
};
function showSnippets(target,resource){
 const ops={s3:['s3api','list-objects-v2','Bucket'],sqs:['sqs','get-queue-attributes','QueueUrl'],sns:['sns','get-topic-attributes','TopicArn'],lambda:['lambda','get-function-configuration','FunctionName'],dynamodb:['dynamodb','describe-table','TableName']};
 const [cli,op,key]=ops[target],sdk=op.replaceAll('-','_'),flag=key.replace(/[A-Z]/g,(c,i)=>(i?'-':'')+c.toLowerCase());
 const quote=s=>"'"+s.replaceAll("'","'\\''")+"'";
 const endpoint=$('endpoint').textContent.replace('host.docker.internal','localhost'),region=$('region').value;
 const extra=target==='sqs'?' --attribute-names All':'';
 const pythonExtra=target==='sqs'?', AttributeNames=["All"]':'';
 output({shell:'AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws --endpoint-url '+quote(endpoint)+' --region '+quote(region)+' '+cli+' '+op+' --'+flag+' '+quote(resource)+extra,
 powershell:'$env:AWS_ACCESS_KEY_ID="test"; $env:AWS_SECRET_ACCESS_KEY="test"; aws --endpoint-url "'+endpoint+'" --region "'+region.replaceAll('"','`"')+'" '+cli+' '+op+' --'+flag+' "'+resource.replaceAll('"','`"')+'"'+extra,
 boto3:'import boto3\nc = boto3.client('+JSON.stringify(target)+', endpoint_url='+JSON.stringify(endpoint)+', region_name='+JSON.stringify(region)+', aws_access_key_id="test", aws_secret_access_key="test")\nprint(c.'+sdk+'('+key+'='+JSON.stringify(resource)+pythonExtra+'))'},'Development snippets');
}
let chosen=new Map(),selectionRegion=$('region').value;
const selectionPanel=el('section','','panel'),selectionHead=el('div','','panelhead'),selectionInfo=el('div',''),selectionTools=el('div','','tools'),selectionCount=el('p','No resources selected');
selectionInfo.append(el('h2','Resource selection'),selectionCount,el('p','Select checkboxes across services in one region. Exports include configuration and bounded sample data, with exclusions listed in the file.'));
selectionHead.append(selectionInfo,selectionTools);selectionPanel.append(selectionHead);workspace.after(selectionPanel);
function selectionButton(label,fn){const b=el('button',label);b.onclick=async()=>{b.disabled=true;try{await fn();}catch(e){error(e);}finally{b.disabled=false;}};selectionTools.append(b);}
function selectionChanged(){selectionCount.textContent=chosen.size+' selected · '+selectionRegion;}
const priorRender=render;
render=function(){if(selectionRegion!==$('region').value){chosen.clear();selectionRegion=$('region').value;selectionChanged();}priorRender();if(service==='health')return;
 for(const row of $('list').querySelectorAll('.row')){const resource=row.querySelector('.name').textContent,key=service+'|'+resource,box=document.createElement('input');box.type='checkbox';box.checked=chosen.has(key);box.setAttribute('aria-label','Select '+resource);const target=service;box.onchange=()=>{if(box.checked)chosen.set(key,{service:target,resource});else chosen.delete(key);selectionChanged();};row.prepend(box);}
};
selectionButton('Select visible',()=>{if(service==='health')return;for(const box of $('list').querySelectorAll('input[type=checkbox]'))if(!box.checked)box.click();});
selectionButton('Clear selection',()=>{chosen.clear();selectionChanged();render();});
selectionButton('Export selected',async()=>{const file=await api('export_selection',{selection:[...chosen.values()],region:selectionRegion},'health');downloadFile(JSON.stringify(file,null,2),'localstack-resources.json','application/json');output(file.notes,'Export notes');});
selectionButton('Cleanup selected',async()=>{
 if(!chosen.size)throw Error('Select resources first.');
 const list=[...chosen.values()];const confirmation=prompt('Permanently delete these resources in '+selectionRegion+'?\n'+list.map(x=>x.service+': '+x.resource).join('\n')+'\nType DELETE to continue.');if(confirmation!=='DELETE')return;
 const emptyBuckets=list.some(x=>x.service==='s3')&&confirm('Also empty selected S3 buckets, including every version and delete marker? Cancel keeps nonempty buckets.');
 const result=await api('cleanup',{selection:list,region:selectionRegion,confirmation,emptyBuckets},'health');
 for(const entry of result.results)if(entry.status==='deleted')chosen.delete(entry.service+'|'+entry.resource);
 selectionChanged();await load();output(result,'Cleanup results');
});
// Version 2 resource exports use backend readiness waits and remap created identifiers.
const recipeReplay=replay;
replay=async function(recipe){
 if(replaying)throw Error('A restore is already running.');
 if(!recipe||![1,2].includes(recipe.version))throw Error('Expected a console recipe or resource export.');
 const allowed=new Set(['create','upload','put','subscribe','upload_zip','update_config','update_code']);
 if(!Array.isArray(recipe.steps)||recipe.steps.length>1000||recipe.steps.some(s=>!['s3','sqs','sns','lambda','dynamodb'].includes(s.service)||!allowed.has(s.action)||!s.params||typeof s.params!=='object'))throw Error('Invalid resource export.');
 if(!confirm('Restore '+recipe.steps.length+' steps? Items, code, configuration and files can be overwritten. Existing resources may be reused. Completed steps remain after a failure.\n'+(recipe.notes||[]).join('\n')))return;
 replaying=true;const results=[],mapping=new Map();
 try{for(const step of recipe.steps){const params={...step.params};for(const key of ['resource','queueUrl']){const lookup=(key==='queueUrl'?'sqs':step.service)+'|'+params[key];if(mapping.has(lookup))params[key]=mapping.get(lookup);}
  try{const result=await api('restore_step',{operation:step.action,params,region:params.region||$('region').value},step.service);
   if(step.action==='create'){const id=result.QueueUrl||result.TopicArn||result.FunctionName||params.name;mapping.set(step.service+'|'+params.name,id);
    // Map original references (including a queue URL from another machine) to the created ID.
    for(const next of recipe.steps)for(const key of ['resource','queueUrl']){const old=next.params?.[key];if((key==='queueUrl'?'sqs':next.service)===step.service&&old&&(old===params.name||old.split(/[/:]/).pop()===params.name))mapping.set(step.service+'|'+old,id);}
   }
   results.push({service:step.service,action:step.action,status:'succeeded'});
  }catch(e){results.push({service:step.service,action:step.action,error:e.message});throw e;}
 }if(recipe.payloads&&typeof recipe.payloads==='object')writeStore('console-payloads',{...readStore('console-payloads',{}),...recipe.payloads});}finally{replaying=false;await load();output(results,'Restore results');}
};
// A single self-scheduling timer prevents overlapping refresh requests.
const refreshTools=el('div','','tools'),pollLabel=el('label','Auto refresh '),poll=document.createElement('select'),stamp=el('span','Not refreshed yet');
poll.setAttribute('aria-label','Auto refresh interval');for(const [value,label] of [['0','Off'],['10000','10 seconds'],['30000','30 seconds'],['60000','60 seconds']]){const o=el('option',label);o.value=value;poll.append(o);}pollLabel.append(poll);refreshTools.append(pollLabel,stamp);document.querySelector('header').after(refreshTools);
let pollTimer=null,pollBusy=false;
function scheduleRefresh(){clearTimeout(pollTimer);const delay=Number(poll.value);if(delay)pollTimer=setTimeout(async()=>{try{if(!document.hidden&&!document.querySelector('dialog[open]')&&!pollBusy&&!replaying&&!$('refresh').disabled){pollBusy=true;const resource=selected,target=service,region=$('region').value,expected=requestId+1,wasOpen=!$('detailPanel').hidden;await load();if(requestId===expected&&target===service&&region===$('region').value&&wasOpen&&resource&&service!=='health')await detail(resource);}}finally{pollBusy=false;scheduleRefresh();}},delay);}
poll.onchange=scheduleRefresh;
const oldLoad=load;
load=async function(...args){if(selectionRegion!==$('region').value){chosen.clear();selectionRegion=$('region').value;selectionChanged();}await oldLoad(...args);stamp.textContent=($('status').textContent.includes('Connected')?'Last refresh: ':'Refresh failed: ')+new Date().toLocaleTimeString();};

$('refresh').onclick=()=>load();$('region').onchange=()=>load();



