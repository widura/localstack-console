const $=id=>document.getElementById(id);
const services={health:'Overview',s3:'S3 buckets',sqs:'SQS queues',sns:'SNS topics',lambda:'Lambda functions',dynamodb:'DynamoDB tables',secretsmanager:'Secrets Manager',ssm:'Parameter Store'};
let service='health',items=[],selected='',cursor=null,requestId=0;
const nameOf=x=>typeof x==='string'?x:x.Name||x.TopicArn||x.FunctionName||'';
function el(tag,text,cls){const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e;}
async function api(action,extra={},target=service){const r=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({region:$('region').value,...extra,service:target,action})});const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;}
function error(e){$('error').textContent=e.message;$('error').hidden=false;}
function render(){const q=$('search').value.toLowerCase();$('list').replaceChildren();const filtered=items.filter(x=>nameOf(x).toLowerCase().includes(q));for(const x of filtered){const row=el('div','','row'),name=nameOf(x);const b=el(service==='health'?'span':'button',name,'name');if(service!=='health')b.onclick=()=>detail(name);row.append(b,el('span',service==='health'?x.state:'View details →','badge'));$('list').append(row);}if(!filtered.length)$('list').append(el('div',items.length?'No matching resources.':'No resources found in this region.','empty'));}
async function load(){const id=++requestId;$('notice').hidden=true;$('error').hidden=true;$('detailPanel').hidden=true;$('refresh').disabled=true;$('list').replaceChildren(el('div','Loading…','empty'));$('title').textContent=services[service];$('listTitle').textContent=service==='health'?'Service health':services[service];$('hint').textContent=service==='health'?'Live status from your LocalStack container.':'Select a resource to inspect it. Region applies to regional services.';$('create').hidden=service==='health';document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.service===service));try{const health=await api('list',{},'health');if(id!==requestId)return;$('status').textContent='● Connected to LocalStack';$('summary').replaceChildren();for(const [label,value] of [['Services',Object.keys(health.services||{}).length],['Running',Object.values(health.services||{}).filter(x=>x==='running').length],['Version',health.version||'—']]){const box=el('div','','metric');box.append(el('span',label),el('strong',String(value)));$('summary').append(box);}const result=service==='health'?{items:Object.entries(health.services||{}).map(([Name,state])=>({Name,state}))}:await api('list');if(id!==requestId)return;items=result.items;render();}catch(e){if(id!==requestId)return;items=[];$('summary').replaceChildren();$('status').textContent='Connection or service error';$('list').replaceChildren(el('div','Unable to load. Check the endpoint, region and Docker port mapping.','empty'));error(e);}finally{if(id===requestId)$('refresh').disabled=false;}}
async function detail(resource,action='detail',next=false){const target=service, id=requestId;$('error').hidden=true;selected=resource;$('detailPanel').hidden=false;$('detailTitle').textContent=resource;$('detail').textContent='Loading…';$('actions').replaceChildren();try{const data=await api(action,{resource,...(next?{cursor}: {})},target);if(id!==requestId||selected!==resource)return;$('detail').textContent=JSON.stringify(data,null,2);cursor=data.NextContinuationToken||data.LastEvaluatedKey||null;const add=(text,fn)=>{const b=el('button',text);b.onclick=fn;$('actions').append(b);};if(target==='sqs'){add('Send message',()=>compose('send'));add('Receive up to 10',()=>{if(confirm('Receiving messages makes them invisible to other consumers for 10 seconds. Continue?'))detail(resource,'receive');});}if(target==='sns')add('Publish message',()=>compose('publish'));if(target==='dynamodb')add('Scan 50 items',()=>detail(resource,'scan'));if(cursor)add('Next page',()=>detail(resource,action,true));}catch(e){$('detail').textContent='Request failed.';error(e);}}
let pending;
const samples={
 'python3.12':'import json\n\ndef handler(event, context):\n    return {"statusCode": 200, "body": json.dumps({"message": "Hello from LocalStack!", "event": event})}\n',
 'nodejs22.x':'exports.handler = async (event) => {\n  return { statusCode: 200, body: JSON.stringify({ message: "Hello from LocalStack!", event }) };\n};\n'
};
const singular={s3:'S3 bucket',sqs:'SQS queue',sns:'SNS topic',dynamodb:'DynamoDB table',lambda:'Lambda function',secretsmanager:'secret',ssm:'parameter'};
function inputField(name,label,{value='',type='text',required=false,options=null,hint='',min,max}={}){
 const wrap=el('div','','formfield'),lab=el('label',label);lab.htmlFor='f-'+name;
 let input;
 if(options){input=document.createElement('select');for(const [v,t] of options){const o=el('option',t);o.value=v;input.append(o);}}
 else input=document.createElement(type==='textarea'?'textarea':'input');
 if(!options&&type!=='textarea')input.type=type;
 input.id='f-'+name;input.name=name;input.required=required;
 if(type==='checkbox')input.checked=!!value;else input.value=value;
 if(min!==undefined)input.min=min;if(max!==undefined)input.max=max;
 if(type==='textarea')input.rows=name==='code'?12:5;
 wrap.append(lab,input);if(hint)wrap.append(el('p',hint));$('fields').append(wrap);return input;
}
function compose(action){
 pending={action,service,resource:selected,region:$('region').value};
 $('fields').replaceChildren();$('formError').hidden=true;
 $('dialogTitle').textContent=action==='create'?'Create '+singular[service]:action==='send'?'Send SQS message':'Publish SNS message';
 $('dialogHint').textContent='Target region: '+pending.region+' · LocalStack only';
 $('submit').textContent=action==='create'?'Create resource':'Send message';
 if(action!=='create')inputField('body','Message body',{type:'textarea',required:true,hint:'FIFO messages use group “console” and a unique deduplication ID.'});
 else {
  inputField('name','Resource name',{required:true,hint:service==='s3'?'3–63 lowercase letters, digits, dots or hyphens.':'Choose a name for this resource.'});
  if(['secretsmanager','ssm'].includes(service)){
   inputField('description','Description (optional)');
   if(service==='secretsmanager')inputField('valueType','Value format',{value:'text',options:[['text','Text / JSON'],['binary','Base64 binary']]});
   if(service==='ssm'){
    inputField('parameterType','Parameter type',{value:'String',options:[['String','String'],['StringList','StringList (comma separated)'],['SecureString','SecureString']]});
    inputField('tier','Tier',{value:'Standard',options:[['Standard','Standard · 4 KB'],['Advanced','Advanced · 8 KB']]});
   }
   inputField('value','Value',{type:'textarea',required:true,hint:service==='ssm'?'Hierarchical names such as /my-app/dev/database are supported.':'Enter plain text, JSON, or base64 for binary format.'});
   inputField('kmsKeyId','KMS key ID / alias (optional)',{hint:service==='ssm'?'Only for SecureString. Leave blank to use the default key.':'Leave blank to use the default key.'});
  }
  if(['sqs','sns'].includes(service)){
   const fifo=inputField('fifo','FIFO',{type:'checkbox',hint:'The .fifo suffix is added automatically.'});
   const dedup=inputField('contentDedup','Content-based deduplication',{type:'checkbox'});dedup.disabled=true;
   fifo.onchange=()=>{dedup.disabled=!fifo.checked;};
  }
  if(service==='sqs'){
   inputField('visibility','Visibility timeout (seconds)',{type:'number',value:30,required:true,min:0,max:43200});
   inputField('delay','Delivery delay (seconds)',{type:'number',value:0,required:true,min:0,max:900});
   inputField('retention','Retention (seconds)',{type:'number',value:345600,required:true,min:60,max:1209600});
  }
  if(service==='sns')inputField('displayName','Display name (optional)');
  if(service==='dynamodb'){
   const types=[['S','String'],['N','Number'],['B','Binary']];
   inputField('partitionKey','Partition key',{value:'id',required:true});
   inputField('partitionType','Partition key type',{value:'S',options:types});
   inputField('sortKey','Sort key (optional)');inputField('sortType','Sort key type',{value:'S',options:types});
   $('fields').append(el('p','Uses on-demand capacity. Additional item attributes do not need to be declared here.'));
  }
  if(service==='lambda'){
   const runtime=inputField('runtime','Runtime',{value:'python3.12',options:[['python3.12','Python 3.12'],['nodejs22.x','Node.js 22']]});
   inputField('role','Execution role ARN (optional)',{hint:'Leave blank to create/reuse localstack-console-lambda with logging permissions. An existing role is left unchanged.'});
   inputField('timeout','Timeout (seconds)',{type:'number',value:3,required:true,min:1,max:900});
   inputField('memory','Memory (MB)',{type:'number',value:128,required:true,min:128,max:10240});
   const code=inputField('code','Function code · index.handler',{type:'textarea',value:samples['python3.12'],required:true,hint:'Single-file code; standard library only. The console packages it as a ZIP. LocalStack must support the selected runtime and have Lambda Docker execution configured.'});
   let previous=runtime.value;
   runtime.onchange=()=>{if(code.value!==samples[previous]&&!confirm('Replace your edited code with the new runtime starter?')){runtime.value=previous;return;}code.value=samples[runtime.value];previous=runtime.value;};
  }
 }
 $('dialog').showModal();$('fields').querySelector('input,textarea,select').focus();
}
$('form').onsubmit=async e=>{
 e.preventDefault();const p={...pending};const b=$('submit');b.disabled=true;$('cancel').disabled=true;$('formError').hidden=true;
 const payload={resource:p.resource,region:p.region,dedup:crypto.randomUUID()};
 for(const f of $('fields').querySelectorAll('input,select,textarea'))payload[f.name]=f.type==='checkbox'?f.checked:f.value;
 try{
  const result=await api(p.action,payload,p.service);
  $('dialog').close();
  if(p.action==='create'){
   $('search').value='';await load();
   $('notice').textContent='Creation request succeeded: '+payload.name+'. Refresh to check readiness. If this name already existed, the service may have returned the existing resource.';
   $('notice').hidden=false;
   $('detailPanel').hidden=false;$('detailTitle').textContent='Creation response';$('actions').replaceChildren();$('detail').textContent=JSON.stringify(result,null,2);
  }else{await detail(p.resource);$('notice').textContent='Message sent successfully.';$('notice').hidden=false;}
 }catch(e){$('formError').textContent=e.message;$('formError').hidden=false;}
 finally{b.disabled=false;$('cancel').disabled=false;}
};
$('dialog').addEventListener('cancel',e=>{if($('submit').disabled)e.preventDefault();});
for(const [key,title] of Object.entries(services)){const b=el('button',title);b.dataset.service=key;b.onclick=()=>{service=key;$('search').value='';load();};$('nav').append(b);}
$('refresh').onclick=load;$('region').onchange=load;$('search').oninput=render;$('close').onclick=()=>{selected='';$('detailPanel').hidden=true;};$('create').onclick=()=>compose('create');$('cancel').onclick=()=>$('dialog').close();
fetch('/api/config').then(r=>r.json()).then(c=>{$('endpoint').textContent=c.endpoint;$('region').value=c.region;load();}).catch(error);


