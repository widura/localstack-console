// Service workbenches share dialogs, tables and context checks.
const developerPanel=el('section','','dev-workspace');developerPanel.id='developerWorkspace';developerPanel.hidden=true;$('detailPanel').append(developerPanel);
const developerDialog=document.createElement('dialog');developerDialog.id='developerDialog';document.body.append(developerDialog);
developerDialog.addEventListener('close',()=>developerDialog.replaceChildren());
let devSerial=0;
let developerLocalStackVersion='';
const beforeDeveloperApi=api;
api=async function(action,extra={},target=service){const result=await beforeDeveloperApi(action,extra,target);if(target==='health'&&result.version)developerLocalStackVersion=result.version;return result;};
const devContext=()=>({service,resource:selected,region:$('region').value,request:requestId});
const devCurrent=ctx=>ctx.service===service&&ctx.resource===selected&&ctx.region===$('region').value&&ctx.request===requestId&&!$('detailPanel').hidden;
const devApi=(ctx,action,p={})=>api(action,{...p,resource:ctx.resource,region:ctx.region},ctx.service);
function devError(e){const dest=developerDialog.open?developerDialog.querySelector('[role=alert]'):null;if(dest)dest.textContent=e.message;else error(e);}
function devButton(label,fn,cls){const b=el('button',label,cls);b.type='button';b.onclick=async()=>{b.disabled=true;try{await fn();}catch(e){devError(e);}finally{b.disabled=false;}};return b;}
function devNotice(text){$('notice').textContent=text;$('notice').hidden=false;}
function devOpen(title,hint=''){
 developerDialog.replaceChildren(el('h2',title),el('p',hint));const body=el('div','','dev-modal-body'),alert=el('p','','dev-error');alert.setAttribute('role','alert');developerDialog.append(body,alert,devButton('Close',()=>developerDialog.close()));if(!developerDialog.open)developerDialog.showModal();return body;
}
function devField(container,field){
 const wrap=el('div','','formfield'),label=el('label',field.label||field.name);let input;
 if(field.options){input=document.createElement('select');for(const option of field.options){const [value,text]=Array.isArray(option)?option:[option,option],o=el('option',text);o.value=value;input.append(o);}}
 else{input=document.createElement(field.kind==='input'||field.kind==='checkbox'?'input':'textarea');if(field.kind==='checkbox')input.type='checkbox';else if(field.kind==='input')input.type=field.type||'text';else input.rows=field.rows||5;}
 input.name=field.name;input.id='dev-'+field.name;label.htmlFor=input.id;input.required=field.required===true;input.disabled=field.disabled===true;
 if(field.kind==='checkbox')input.checked=!!field.value;else input.value=field.value??'';input.autocomplete='off';input.spellcheck=false;
 wrap.append(label,input);if(field.hint)wrap.append(el('p',field.hint));container.append(wrap);return input;
}
function devForm(title,fields,submit,hint=''){
 const body=devOpen(title,hint),form=document.createElement('form');body.append(form);for(const field of fields)devField(form,field);
 const save=el('button','Save','primary');save.type='submit';form.append(save);
 form.onsubmit=async e=>{e.preventDefault();save.disabled=true;developerDialog.querySelector('[role=alert]').textContent='';
 const values={};for(const input of form.querySelectorAll('[name]'))values[input.name]=input.type==='checkbox'?input.checked:input.value;
 try{if(await submit(values,body)!==false)developerDialog.close();}catch(e){devError(e);}finally{save.disabled=false;}};
 return form;
}
function devRaw(data,title='Response',open=false){const d=el('details','');d.open=open;d.append(el('summary',title),el('pre',JSON.stringify(data,null,2)));return d;}
function devTable(columns,rows){const wrap=el('div','','dev-table-wrap'),table=el('table','','dev-table'),head=el('thead',''),tr=el('tr','');for(const col of columns){const th=el('th',col.label);th.scope='col';tr.append(th);}head.append(tr);const body=el('tbody','');
 for(const row of rows){const tr=el('tr','');for(const col of columns){const td=el('td','');td.dataset.label=col.label;const v=col.render(row);if(v instanceof Node)td.append(v);else td.textContent=v??'—';tr.append(td);}body.append(tr);}table.append(head,body);wrap.append(table);if(!rows.length)wrap.append(el('p','No results.','empty'));return wrap;
}
function devTools(...buttons){const tools=el('div','','tools dev-tools');tools.append(...buttons);return tools;}
function devNavigate(target,resource){service=target;$('search').value='';load().then(()=>{if(service===target)return detail(resource);}).catch(error);}
function devTyped(value){if(value===undefined)return '—';const [type,data]=Object.entries(value)[0]||[];return ['S','N','B'].includes(type)?String(data):JSON.stringify(value);}
function devDiff(a,b){const before=a.split('\n'),after=b.split('\n'),box=el('div','','dev-diff');for(let i=0;i<Math.max(before.length,after.length);i++){if(before[i]===after[i])box.append(el('pre','  '+(before[i]??'')));else{if(before[i]!==undefined)box.append(el('pre','− '+before[i],'dev-removed'));if(after[i]!==undefined)box.append(el('pre','+ '+after[i],'dev-added'));}}return box;}
function devPretty(text){try{return JSON.stringify(JSON.parse(text),null,2);}catch{return text;}}
function devKeyValues(title,initial,submit,stringsOnly=false){
 const body=devOpen(title,'Values remain in this editor only; they are not recorded in browser recipes.'),rows=el('div','');body.append(rows);
 function add(key='',value=''){
  const row=el('div','','dev-kv-row'),keyInput=document.createElement('input'),type=document.createElement('select'),input=document.createElement('textarea');keyInput.placeholder='Key';keyInput.setAttribute('aria-label','Field key');keyInput.value=key;input.setAttribute('aria-label','Field value');input.rows=2;
  for(const text of stringsOnly?['String']:['String','Number','Boolean','JSON','Null']){const o=el('option',text);o.value=text;type.append(o);}type.setAttribute('aria-label','Field type');
  type.value=stringsOnly||typeof value==='string'?'String':value===null?'Null':typeof value==='number'?'Number':typeof value==='boolean'?'Boolean':'JSON';input.value=typeof value==='string'?value:JSON.stringify(value);
  row.append(keyInput,type,input,devButton('Remove',()=>row.remove()));rows.append(row);
 }
 for(const [k,v] of Object.entries(initial))add(k,v);if(!Object.keys(initial).length)add();
 body.append(devTools(devButton('Add field',()=>add()),devButton('Save',async()=>{
  const result={};for(const row of rows.children){const key=row.querySelector('input').value;if(!key)throw Error('Every field needs a key');if(Object.hasOwn(result,key))throw Error('Duplicate key: '+key);const type=row.querySelector('select').value,text=row.querySelector('textarea').value;let value=text;
   if(type==='Number'){if(!text.trim()||!Number.isFinite(Number(text)))throw Error('Enter a valid number for '+key);value=Number(text);}else if(type==='Boolean'){if(!['true','false'].includes(text))throw Error('Enter true or false for '+key);value=text==='true';}else if(type==='JSON')value=JSON.parse(text);else if(type==='Null')value=null;
   Object.defineProperty(result,key,{value,enumerable:true,writable:true,configurable:true});
  }await submit(result);developerDialog.close();},'primary')));
}

// SQS inbox never receives in the background; each receive changes visibility.
async function devQueue(ctx,host){
 host.replaceChildren(el('h3','Message inbox'),el('p','Receive fetches up to 10 messages, hides them for 10 seconds and increases receive counts. Refreshing this panel does not receive messages.'));
 const inbox=el('div',''),status=el('p','No messages received in this session.');host.append(status);
 async function receive(){if(!confirm('Receive up to 10 messages? They will be hidden from other consumers for 10 seconds.'))return;const data=await devApi(ctx,'receive');if(!devCurrent(ctx))return;draw(data.Messages||[]);}
 function draw(messages){status.textContent=messages.length+' messages received at '+new Date().toLocaleTimeString();inbox.replaceChildren();
  for(const message of messages){const card=el('article','','dev-message'),title=el('h4',message.MessageId),receipt=message.ReceiptHandle;
   card.append(title,el('p','Receive count: '+(message.Attributes?.ApproximateReceiveCount||'—')+' · Sent: '+(message.Attributes?.SentTimestamp?new Date(Number(message.Attributes.SentTimestamp)).toLocaleString():'—')),el('pre',devPretty(message.Body)),devRaw(message.MessageAttributes||{},'Message attributes'),devRaw(message.Attributes||{},'System attributes'));
   card.append(devTools(devButton('Acknowledge / delete',async()=>{if(!confirm('Delete this received message?'))return;await devApi(ctx,'ack',{receipt});card.remove();}),devButton('Release now',async()=>{await devApi(ctx,'visibility',{receipt,seconds:0});card.remove();}),devButton('Change visibility',()=>devForm('Message visibility',[{name:'seconds',label:'Seconds',value:'30',kind:'input',required:true}],async p=>{await devApi(ctx,'visibility',{receipt,...p});devNotice('Visibility changed.');})),devButton('Edit and resend copy',()=>devForm('Resend message',[{name:'body',label:'Message body',value:message.Body,required:true},{name:'attributes',label:'Attributes JSON',value:JSON.stringify(message.MessageAttributes||{},null,2)},{name:'group',label:'FIFO group',kind:'input',value:message.Attributes?.MessageGroupId||'console'}],async p=>{await devApi(ctx,'send',{...p,dedup:crypto.randomUUID()});devNotice('A new copy was sent; the original message remains until acknowledged.');}))));inbox.append(card);
  }if(!messages.length)inbox.append(el('p','No messages available.'));
 }
 host.append(devTools(devButton('Receive messages',receive,'primary'),devButton('Queue settings',async()=>{
  const meta=(await devApi(ctx,'detail')).Attributes;devForm('Queue settings',Object.entries({VisibilityTimeout:'Visibility timeout',DelaySeconds:'Delivery delay',MessageRetentionPeriod:'Retention seconds',ReceiveMessageWaitTimeSeconds:'Long-poll wait seconds'}).map(([name,label])=>({name,label,value:meta[name]||'0',kind:'input',required:true})),async p=>{await devApi(ctx,'dev_queue_settings',{settings:p});devNotice('Queue settings updated.');});
 }),devButton('Configure dead-letter queue',async()=>{
  const list=(await api('list',{region:ctx.region},'sqs')).items;devForm('Dead-letter queue',[{name:'queue',label:'Target queue',options:[['','Remove DLQ configuration'],...list.filter(q=>q!==ctx.resource).map(q=>[q,q.split('/').pop()])]},{name:'maxReceives',label:'Maximum receives before dead-lettering',kind:'input',value:'5'}],async p=>{if(!confirm('Update the source queue’s dead-letter policy?'))return false;await devApi(ctx,'dev_set_dlq',p);devNotice('Dead-letter policy updated.');});
 }),devButton('Connected Lambda consumers',async()=>{
  const data=await devApi(ctx,'dev_consumers'),body=devOpen('Lambda consumers');body.append(devTable([{label:'Function',render:m=>m.FunctionArn},{label:'State',render:m=>m.State},{label:'Open',render:m=>devButton('Open invocation workbench',()=>{developerDialog.close();devNavigate('lambda',m.FunctionArn);})}],data.EventSourceMappings||[]));
 }),devButton('Redrive from this DLQ',async()=>{
  const list=(await api('list',{region:ctx.region},'sqs')).items;devForm('Redrive failed messages',[{name:'destination',label:'Destination',options:[['','Original source queues'],...list.filter(q=>q!==ctx.resource).map(q=>[q,q.split('/').pop()])]},{name:'rate',label:'Maximum messages per second',value:'10',kind:'input'}],async p=>{if(!confirm('Start moving messages out of this dead-letter queue?'))return false;const result=await devApi(ctx,'dev_redrive',p);devNotice('Redrive task started: '+result.TaskHandle);});
 }),devButton('Redrive tasks',async()=>{
  const result=await devApi(ctx,'dev_redrive_tasks'),body=devOpen('Redrive tasks');body.append(devTable([{label:'Status',render:r=>r.Status},{label:'Moved',render:r=>r.ApproximateNumberOfMessagesMoved},{label:'Action',render:r=>devButton('Cancel task',async()=>{if(!confirm('Cancel this redrive task?'))return;await devApi(ctx,'dev_cancel_redrive',{handle:r.TaskHandle});devNotice('Cancellation requested.');})}],result.Results||[]));
 })),inbox);
}

async function devItems(ctx,host,params={}){
 const serial=++devSerial;host.replaceChildren(el('p','Loading items…'));
 const result=await devApi(ctx,'dev_items',params);if(!devCurrent(ctx)||serial!==devSerial)return;
 host.replaceChildren(el('h3','Items'));const schema=result.Table,primary=schema.KeySchema,primaryNames=new Set(primary.map(k=>k.AttributeName));
 const indexes=schema.GlobalSecondaryIndexes||[],names=[...new Set((result.Items||[]).flatMap(item=>Object.keys(item)))];
 const ordered=[...primary.map(k=>k.AttributeName),...names.filter(n=>!primaryNames.has(n)).sort()];
 function key(item){return Object.fromEntries(primary.map(k=>[k.AttributeName,item[k.AttributeName]]));}
 async function query(){
  const form=devForm('Query builder',[{name:'index',label:'Table / index',options:[['','Base table'],...indexes.map(v=>[v.IndexName,v.IndexName])]},{name:'partition',label:'Partition key attribute',value:primary.find(k=>k.KeyType==='HASH').AttributeName,kind:'input',required:true},{name:'value',label:'Partition key typed value',value:'{"S":"example"}',required:true},{name:'sort',label:'Sort key attribute (optional)',value:primary.find(k=>k.KeyType==='RANGE')?.AttributeName||'',kind:'input'},{name:'sortOp',label:'Sort condition',options:['=','begins_with','<','<=','>','>=']},{name:'sortValue',label:'Sort typed value (optional)',value:''}],async p=>{JSON.parse(p.value);await devItems(ctx,host,p);});
  form.querySelector('[name=index]').onchange=e=>{const spec=e.target.value?indexes.find(i=>i.IndexName===e.target.value):schema;form.querySelector('[name=partition]').value=spec.KeySchema.find(k=>k.KeyType==='HASH').AttributeName;form.querySelector('[name=sort]').value=spec.KeySchema.find(k=>k.KeyType==='RANGE')?.AttributeName||'';};
 }
 host.append(devTools(devButton('Query builder',query,'primary'),devButton('Scan table',()=>devItems(ctx,host)),devButton('Add item',()=>devForm('Add item',[{name:'item',label:'Typed attribute-value JSON',value:JSON.stringify(Object.fromEntries(primary.map(k=>[k.AttributeName,{S:''}])),null,2),required:true}],async p=>{if(!confirm('Save item? An existing item with this key will be replaced.'))return false;await devApi(ctx,'dev_put_item',p);await devItems(ctx,host,params);})),devButton('Import JSON items',()=>devForm('Import items',[{name:'items',label:'Array of typed attribute-value items (up to 100)',value:'[]',required:true}],async(p,body)=>{if(!confirm('Import these items? Matching primary keys will be overwritten.'))return false;const result=await devApi(ctx,'dev_import_items',p);body.append(devRaw(result,'Per-item results',true));await devItems(ctx,host,params);return false;})),devButton('Create secondary index',()=>devForm('Create global secondary index',[{name:'name',label:'Index name',kind:'input',required:true},{name:'partition',label:'Partition key',kind:'input',required:true},{name:'sort',label:'Sort key (optional)',kind:'input'},{name:'types',label:'Key attribute types JSON',value:'{}',hint:'Example: {"email":"S","createdAt":"N"}. Unspecified types use S.'}],async p=>{await devApi(ctx,'dev_create_index',p);devNotice('Index creation requested. Refresh to check its status.');await devItems(ctx,host,params);}))),el('p',(result.Count||0)+' items · '+(result.ScannedCount??result.Count??0)+' evaluated · '+(params.index||'Base table')));
 const columns=ordered.map(name=>({label:name,render:item=>{
  if(!(name in item))return '—';if(primaryNames.has(name))return el('code',devTyped(item[name]));
  const button=devButton(devTyped(item[name]),()=>devForm('Edit '+name,[{name:'value',label:'Typed value',value:JSON.stringify(item[name],null,2),required:true}],async p=>{await devApi(ctx,'dev_update_item',{key:key(item),attribute:name,old:item[name],...p});await devItems(ctx,host,params);},'Only this attribute is updated. Concurrent changes to it cause a conflict.'),'dev-cell');return button;
 }}));
 columns.push({label:'Actions',render:item=>devTools(devButton('Edit document',()=>devForm('Edit item',[{name:'item',label:'Typed JSON item',value:JSON.stringify(item,null,2),required:true}],async p=>{const edited=JSON.parse(p.item);if(JSON.stringify(key(edited))!==JSON.stringify(key(item)))throw Error('Primary key changes require creating a new item');if(!confirm('Replace this item with the edited document?'))return false;await devApi(ctx,'dev_put_item',p);await devItems(ctx,host,params);})),devButton('Delete',async()=>{if(!confirm('Delete this item?'))return;await devApi(ctx,'dev_delete_item',{key:key(item)});await devItems(ctx,host,params);} ))});
 host.append(devTable(columns,result.Items||[]));if(result.LastEvaluatedKey)host.append(devButton('Next items',()=>devItems(ctx,host,{...params,cursor:result.LastEvaluatedKey})));
 host.append(devRaw({KeySchema:schema.KeySchema,Indexes:indexes.map(i=>({Name:i.IndexName,Status:i.IndexStatus,KeySchema:i.KeySchema}))},'Table and index schemas'));
}

async function devTopic(ctx,host){
 const result=await devApi(ctx,'dev_subscriptions');if(!devCurrent(ctx))return;
 host.replaceChildren(el('h3','Topic routes'),el('p','Publish a test event, then open a destination queue to explicitly receive and inspect delivery. Receiving can affect active consumers.'));
 host.append(devTools(devButton('Publish test event',()=>{compose('publish');$('f-body').value='{"type":"order.created","test":true}';},'primary'),devButton('Refresh routes',()=>devTopic(ctx,host))));
 const rows=result.Subscriptions||[];
 host.append(devTable([{label:'Route',render:s=>{const box=el('div','','dev-route');box.append(el('span',ctx.resource.split(':').pop()),el('span','→'),el('strong',s.Endpoint));return box;}},{label:'Settings',render:s=>devRaw({scope:s.Settings?.FilterPolicyScope||'MessageAttributes',filter:s.Settings?.FilterPolicy?JSON.parse(s.Settings.FilterPolicy):{},rawDelivery:s.Settings?.RawMessageDelivery},'Filter and delivery',true)},{label:'Actions',render:s=>devTools(
  devButton('Edit filter / delivery',()=>devForm('Subscription settings',[{name:'filter',label:'Filter policy JSON ({} matches all)',value:s.Settings?.FilterPolicy||'{}',required:true},{name:'scope',label:'Filter on',options:['MessageAttributes','MessageBody'],value:s.Settings?.FilterPolicyScope||'MessageAttributes'},{name:'raw',label:'Raw delivery',kind:'checkbox',value:s.Settings?.RawMessageDelivery==='true'}],async p=>{await devApi(ctx,'dev_subscription_settings',{subscription:s.SubscriptionArn,...p});await devTopic(ctx,host);},'AWS updates these attributes in separate calls; after a failure, refresh to inspect which changes applied.')),
  ...(s.QueueUrl?[devButton('Open destination inbox',()=>devNavigate('sqs',s.QueueUrl))]:[])
 )}],rows));
}

const invocationSessions=new Map();
async function devLambda(ctx,host){
 const sessionKey=ctx.region+'|'+ctx.resource;
 if(!invocationSessions.has(sessionKey))invocationSessions.set(sessionKey,{event:'{}',runs:[]});
 const state=invocationSessions.get(sessionKey);host.replaceChildren(el('h3','Invocation workbench'));
 const event=devField(host,{name:'lambda-event',label:'JSON event',value:state.event,rows:8}),qualifier=devField(host,{name:'lambda-qualifier',label:'Version or alias (blank uses $LATEST)',value:state.qualifier||'',kind:'input'}),status=el('p',''),results=el('div','');
 event.oninput=()=>{state.event=event.value;};qualifier.oninput=()=>{state.qualifier=qualifier.value;};
 const saved=readStore('console-payloads',{}),select=document.createElement('select');select.setAttribute('aria-label','Saved invocation events');select.append(el('option','Load saved event…'));
 for(const [name,p] of Object.entries(saved))if(p.service==='lambda'&&p.action==='invoke'){const o=el('option',name);o.value=name;select.append(o);}
 select.onchange=()=>{if(saved[select.value])event.value=saved[select.value].payload.event;};host.prepend(select);
 function drawRuns(){results.replaceChildren();if(!state.runs.length)return;
  const picked=new Set(),compare=devButton('Compare selected runs',()=>{if(picked.size!==2)throw Error('Select exactly two runs');const [a,b]=[...picked].map(i=>state.runs[i]);const body=devOpen('Invocation comparison',a.label+' → '+b.label);body.append(el('p','Round trip: '+a.result.RoundTripMs+' ms → '+b.result.RoundTripMs+' ms'),devDiff(JSON.stringify(a.result.Payload,null,2),JSON.stringify(b.result.Payload,null,2)),devRaw({before:a.result.Logs,after:b.result.Logs},'Execution logs'));});
  results.append(compare,devTable([{label:'Compare',render:run=>{const box=document.createElement('input');box.type='checkbox';box.setAttribute('aria-label','Compare '+run.label);box.onchange=()=>{const i=state.runs.indexOf(run);if(box.checked)picked.add(i);else picked.delete(i);};return box;}},{label:'Run',render:r=>r.label},{label:'Status',render:r=>r.result.FunctionError||'Succeeded'},{label:'Execution',render:r=>r.result.ExecutionDurationMs===null?'Not reported':r.result.ExecutionDurationMs+' ms'},{label:'Round trip',render:r=>r.result.RoundTripMs+' ms'},{label:'Inspect',render:r=>devButton('Response / logs',()=>{const body=devOpen(r.label);body.append(devRaw(r.event,'Input event',true),devRaw(r.result.Payload,'Response',true),el('pre',r.result.Logs||'No execution logs returned.'));})}],state.runs));
  const latest=state.runs[0];results.append(el('h4','Latest response'),devRaw(latest.result.Payload,'Response',true),devRaw(latest.result.Logs,'Execution logs',true));
 }
 host.append(devTools(devButton('Run function',async()=>{
  const payload=JSON.parse(event.value);state.event=event.value;status.textContent='Invoking…';
  try{const result=await devApi(ctx,'dev_invoke',{event:JSON.stringify(payload),qualifier:qualifier.value});if(!devCurrent(ctx))return;state.runs.unshift({label:new Date().toLocaleTimeString()+' · '+(qualifier.value||'$LATEST'),event:payload,result});state.runs=state.runs.slice(0,10);status.textContent=result.FunctionError?'Function returned '+result.FunctionError:'Invocation completed';drawRuns();}catch(e){status.textContent='Invocation failed';throw e;}
 },'primary'),devButton('Save event',()=>{JSON.parse(event.value);const name=prompt('Saved event name');if(name){const all=readStore('console-payloads',{});all[name]={service:'lambda',action:'invoke',payload:{event:event.value}};writeStore('console-payloads',all);devNotice('Event saved.');}}),devButton('Environment variables',async()=>{const meta=await devApi(ctx,'detail');devKeyValues('Environment variables',meta.Environment?.Variables||{},async vars=>{await devApi(ctx,'update_config',{environment:JSON.stringify(vars)});devNotice('Environment update requested.');},true);}),devButton('Versions / aliases',()=>devFunctionVersions(ctx)),devButton('SQS triggers',()=>devTriggers(ctx))),status,results);drawRuns();
}
async function devFunctionVersions(ctx){
 const data=await devApi(ctx,'dev_function_versions'),body=devOpen('Function versions and aliases');
 body.append(devTools(devButton('Publish version',()=>devForm('Publish immutable version',[{name:'description',label:'Description',kind:'input'}],async p=>{await devApi(ctx,'dev_publish_version',p);await devFunctionVersions(ctx);return false;})),devButton('Create / move alias',()=>devForm('Function alias',[{name:'name',label:'Alias name',kind:'input',required:true},{name:'version',label:'Version',options:(data.Versions||[]).filter(v=>v.Version!=='$LATEST').map(v=>v.Version),required:true}],async p=>{if(!p.version)throw Error('Publish a version first');if(!confirm('Point alias '+p.name+' at version '+p.version+'?'))return false;await devApi(ctx,'dev_alias',p);await devFunctionVersions(ctx);return false;}))));
 body.append(devTable([{label:'Version',render:v=>v.Version},{label:'Description',render:v=>v.Description},{label:'Modified',render:v=>v.LastModified}],data.Versions||[]),devTable([{label:'Alias',render:a=>a.Name},{label:'Version',render:a=>a.FunctionVersion}],data.Aliases||[]));
}
async function devTriggers(ctx){
 const mappings=(await devApi(ctx,'dev_mappings')).EventSourceMappings||[],body=devOpen('SQS event source mappings');
 body.append(devButton('Connect SQS queue',async()=>{const queues=(await api('list',{region:ctx.region},'sqs')).items;devForm('Connect queue trigger',[{name:'queue',label:'Queue',options:queues.map(q=>[q,q.split('/').pop()]),required:true},{name:'batchSize',label:'Batch size (1–10)',value:'10',kind:'input'}],async p=>{if(!confirm('Enable this trigger? Lambda will consume available messages and execute your code.'))return false;await devApi(ctx,'dev_add_sqs_trigger',p);await devTriggers(ctx);return false;},'The execution role needs permission to receive/delete SQS messages and get queue attributes. The console does not broaden role permissions.');}));
 body.append(devTable([{label:'Queue ARN',render:m=>m.EventSourceArn},{label:'State',render:m=>m.State},{label:'Batch',render:m=>m.BatchSize},{label:'Actions',render:m=>devTools(devButton(m.State==='Enabled'?'Disable':'Enable',async()=>{if(!confirm('Change this trigger state? Enabling it consumes queue messages.'))return;await devApi(ctx,'dev_mapping_state',{uuid:m.UUID,enabled:m.State!=='Enabled'});await devTriggers(ctx);}),devButton('Remove',async()=>{if(!confirm('Remove this trigger?'))return;await devApi(ctx,'dev_remove_mapping',{uuid:m.UUID});await devTriggers(ctx);}))}],mappings));
}

async function devConfigVersions(ctx){
 const history=(await devApi(ctx,'history')).Versions||[],body=devOpen('Version history','Values remain hidden until you explicitly reveal or compare them.'),picked=new Set();
 async function value(version){const data=await devApi(ctx,ctx.service==='ssm'?'dev_parameter_version':'dev_secret_version',{version});return ctx.service==='ssm'?data.Parameter.Value:data.SecretString??data.SecretBinary;}
 body.append(devButton('Reveal comparison of selected versions',async()=>{if(picked.size!==2)throw Error('Select exactly two versions');const [a,b]=[...picked],left=await value(a),right=await value(b);const panel=devOpen('Version comparison',a+' → '+b);panel.append(devDiff(devPretty(left),devPretty(right)));}));
 body.append(devTable([{label:'Compare',render:v=>{const id=v.VersionId??v.Version,box=document.createElement('input');box.type='checkbox';box.setAttribute('aria-label','Compare version '+id);box.onchange=()=>box.checked?picked.add(id):picked.delete(id);return box;}},{label:'Version',render:v=>v.VersionId??v.Version},{label:'Labels',render:v=>(v.VersionStages||v.Labels||[]).join(', ')||'—'},{label:'Modified',render:v=>String(v.CreatedDate||v.LastModifiedDate||'—')},{label:'Actions',render:v=>{
  const version=v.VersionId??v.Version;return devTools(devButton('Reveal this version',async()=>{const text=await value(version),panel=devOpen('Version '+version);panel.append(el('pre',devPretty(text)));}),devButton(ctx.service==='ssm'?'Restore as new version':'Make current',async()=>{if(!confirm('Restore version '+version+'? '+(ctx.service==='ssm'?'This writes a new parameter version.':'This moves AWSCURRENT to that version.')))return;await devApi(ctx,ctx.service==='ssm'?'dev_parameter_rollback':'dev_secret_stage',{version,stage:'AWSCURRENT'});await devConfigVersions(ctx);}),devButton('Manage labels',()=>{
   if(ctx.service==='ssm')devForm('Parameter version labels',[{name:'labels',label:'Labels JSON array',value:JSON.stringify(v.Labels||[])},{name:'remove',label:'Remove these labels',kind:'checkbox',disabled:developerLocalStackVersion==='4.0.3',hint:developerLocalStackVersion==='4.0.3'?'Removal is unavailable in LocalStack 4.0.3. Assigning and moving labels works.':''}],async p=>{const result=await devApi(ctx,'dev_parameter_labels',{version,...p});if(result.InvalidLabels?.length)throw Error('Invalid labels: '+result.InvalidLabels.join(', '));await devConfigVersions(ctx);return false;});
   else devForm('Assign staging label',[{name:'stage',label:'Label to move to this version',value:'AWSPREVIOUS',kind:'input',required:true}],async p=>{await devApi(ctx,'dev_secret_stage',{version,...p});await devConfigVersions(ctx);return false;});
  }));
 }}],history));
}
async function devSecret(ctx,host){
 host.replaceChildren(el('h3','Secret tools'),el('p','JSON fields are loaded only when you open the editor. Version comparisons start with values masked.'));
 host.append(devTools(devButton('Edit JSON fields',async()=>{const data=await devApi(ctx,'reveal');if(data.SecretString===undefined)throw Error('Binary secrets use the base64 value editor');let value;try{value=JSON.parse(data.SecretString);}catch{throw Error('This value is not JSON. Use Update value, or first store a JSON object.');}if(!value||typeof value!=='object'||Array.isArray(value))throw Error('The field editor needs a JSON object');devKeyValues('Secret JSON fields',value,async result=>{await devApi(ctx,'update_value',{value:JSON.stringify(result)});devNotice('A new secret version was saved.');});},'primary'),devButton('Compare / restore versions',()=>devConfigVersions(ctx))));
}

// Parameter hierarchy uses metadata from the existing paginated resource list.
let parameterPath='';
const parameterTreeTools=el('div','','dev-path-tools');parameterTreeTools.hidden=true;$('list').before(parameterTreeTools);
function devParameterBulk(){
 devForm('Import parameters',[{name:'format',label:'Format',options:['JSON','.env']},{name:'prefix',label:'Prefix for .env keys',value:'/app/dev/',kind:'input'},{name:'type',label:'Type for .env entries',options:['String','SecureString','StringList']},{name:'entries',label:'JSON array or .env text',value:'[{"name":"/app/dev/example","value":"demo","parameterType":"String"}]',required:true},{name:'overwrite',label:'Overwrite existing parameters (preserves their type/encryption)',kind:'checkbox'}],async(p,body)=>{
  let entries;if(p.format==='JSON')entries=JSON.parse(p.entries);else entries=p.entries.split(/\r?\n/).filter(line=>line.trim()&&!line.trim().startsWith('#')).map(line=>{const match=line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$/);if(!match)throw Error('Invalid .env line');let value=match[2].trim();if((value.startsWith('"')&&value.endsWith('"'))||(value.startsWith("'")&&value.endsWith("'")))value=value.slice(1,-1);return {name:p.prefix.replace(/\/?$/,'/')+match[1],value,parameterType:p.type};});
  if(!Array.isArray(entries))throw Error('Expected an array');entries=entries.map(e=>({...e,overwrite:p.overwrite}));
  if(!confirm('Import '+entries.length+' parameters? '+(p.overwrite?'Existing values may be replaced.':'Existing names will report conflicts.')))return false;
  const results=await api('dev_parameter_import',{entries,region:$('region').value},'ssm');body.append(devRaw(results,'Per-parameter results',true));await load();return false;
 },'Values are not persisted in browser recipes. .env import supports literal key=value lines, not shell expansion.');
}
function devEnvironmentCompare(){devForm('Compare parameter environments',[{name:'left',label:'Left prefix',value:'/app/dev',kind:'input',required:true},{name:'right',label:'Right prefix',value:'/app/test',kind:'input',required:true},{name:'compareValues',label:'Decrypt values to compare equality (values are not displayed)',kind:'checkbox'}],async(p,body)=>{
 const data=await api('dev_environment_compare',{...p,region:$('region').value},'ssm');body.querySelector('.dev-comparison')?.remove();const results=el('div','','dev-comparison');results.append(devTable([{label:'Relative name',render:v=>v.relativeName},{label:'Left',render:v=>v.left?.Type||'Missing'},{label:'Right',render:v=>v.right?.Type||'Missing'},{label:'Values',render:v=>v.valuesEqual===undefined?'Not compared':v.valuesEqual?'Equal':'Different'}],data.Parameters));body.append(results);return false;
 });}
function devParameterTree(){
 parameterTreeTools.replaceChildren();parameterTreeTools.hidden=service!=='ssm';if(service!=='ssm')return;
 const allButton=devButton('All parameters',()=>{parameterPath='';render();});parameterTreeTools.append(devTools(allButton,devButton('Import JSON / .env',devParameterBulk),devButton('Compare environments',devEnvironmentCompare),devButton('Select this path for export',()=>{const prefix=parameterPath||'/';for(const item of items){const name=nameOf(item);if((name.startsWith('/')?name:'/'+name).startsWith(prefix))chosen.set('ssm|'+name,{service:'ssm',resource:name});}selectionChanged();render();})));
 const paths=parameterPath.split('/').filter(Boolean);let path='';const crumbs=el('div','','tools');for(const segment of paths){path+='/'+segment;const current=path+'/';crumbs.append(devButton(segment+' /',()=>{parameterPath=current;render();}));}parameterTreeTools.append(crumbs,el('p','Path: '+(parameterPath||'/')));
 const q=$('search').value.toLowerCase(),visible=items.filter(item=>nameOf(item).toLowerCase().includes(q)),folders=new Set(),leaves=[];
 for(const item of visible){const name=nameOf(item),normalized=name.startsWith('/')?name:'/'+name,base=parameterPath||'/';if(!normalized.startsWith(base))continue;const remaining=normalized.slice(base.length);if(remaining.includes('/'))folders.add(base+remaining.split('/')[0]+'/');else leaves.push(item);}
 $('list').replaceChildren();for(const folder of [...folders].sort()){const row=el('div','','row');row.append(devButton('📁 '+folder,()=>{parameterPath=folder;render();},'name'),el('span','Folder','badge'));$('list').append(row);}
 for(const item of leaves){const name=nameOf(item),row=el('div','','row'),check=document.createElement('input');check.type='checkbox';check.checked=chosen.has('ssm|'+name);check.setAttribute('aria-label','Select '+name);check.onchange=()=>{if(check.checked)chosen.set('ssm|'+name,{service:'ssm',resource:name});else chosen.delete('ssm|'+name);selectionChanged();};row.append(check,devButton(name,()=>detail(name),'name'),el('span',item.Type||'Parameter','badge'));$('list').append(row);}
 if(!folders.size&&!leaves.length)$('list').append(el('div','No parameters under this path.','empty'));
}

function devTransferURL(ctx,key,version){const query=new URLSearchParams({bucket:ctx.resource,key,region:ctx.region});if(version)query.set('version',version);return '/api/s3/object?'+query;}
let uploadBusy=false;
developerDialog.addEventListener('cancel',event=>{if(uploadBusy)event.preventDefault();});
function devUploadFiles(ctx,initial=[]){
 const body=devOpen('Upload files','Raw streamed uploads up to 100 MB per file. Existing keys can be replaced. Successful earlier uploads remain if a later file fails.');
 const prefix=document.createElement('input');prefix.value=s3State.prefix;prefix.setAttribute('aria-label','Upload key prefix');
 const chooser=document.createElement('input');chooser.type='file';chooser.multiple=true;chooser.setAttribute('aria-label','Choose upload files');
 const rows=el('div','');let files=[...initial],stop=false,current=null;
 function draw(){rows.replaceChildren();for(const file of files){const row=el('div','','dev-upload-row'),progress=document.createElement('progress');progress.max=100;progress.value=0;row.append(el('strong',file.webkitRelativePath||file.name),el('span',s3Size(file.size)),progress,el('span','Waiting'));rows.append(row);}}
 chooser.onchange=()=>{files=[...chooser.files];draw();};body.append(el('label','Object key prefix'),prefix,chooser,rows);draw();
 const cancel=devButton('Stop remaining uploads',()=>{stop=true;current?.abort();});cancel.disabled=true;
 const start=devButton('Upload selected files',async()=>{
  if(!files.length)throw Error('Choose at least one file');if(!confirm('Upload '+files.length+' files? Matching keys will be overwritten.'))return;
  uploadBusy=true;stop=false;cancel.disabled=false;chooser.disabled=true;prefix.disabled=true;const close=developerDialog.querySelector(':scope > button');if(close)close.disabled=true;
  try{for(let index=0;index<files.length;index++){
   const file=files[index],row=rows.children[index],progress=row.querySelector('progress'),status=row.lastChild;
   if(stop){status.textContent='Not uploaded (stopped)';continue;}
   if(file.size>100*1024*1024){status.textContent='Failed: exceeds 100 MB';continue;}
   const key=prefix.value+(file.webkitRelativePath||file.name);status.textContent='Uploading…';
   try{await new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();current=xhr;xhr.open('PUT',devTransferURL(ctx,key));xhr.setRequestHeader('Content-Type',file.type||'application/octet-stream');
    xhr.upload.onprogress=event=>{if(event.lengthComputable){progress.value=event.loaded/event.total*100;status.textContent=Math.round(progress.value)+'% sent';}};
    xhr.onload=()=>xhr.status>=200&&xhr.status<300?resolve():reject(Error((()=>{try{return JSON.parse(xhr.responseText).error;}catch{return 'HTTP '+xhr.status;}})()));
    xhr.onerror=()=>reject(Error('Network error'));xhr.onabort=()=>reject(Error('Stopped'));xhr.send(file);
   });progress.value=100;status.textContent='Uploaded: '+key;}catch(e){status.textContent='Failed: '+e.message;}
  }
  if(devCurrent(ctx))await s3Refresh(ctx.resource);
  }finally{uploadBusy=false;current=null;cancel.disabled=true;chooser.disabled=false;prefix.disabled=false;if(close)close.disabled=false;}
 });body.append(devTools(start,cancel));
}
const developerS3Object=s3Object;
s3Object=async function(action,object,bucket,region){
 const ctx={service:'s3',resource:bucket,region,request:requestId};
 if(!s3Active(bucket,region))return;
 if(action==='download'){
  const a=el('a','');a.href=devTransferURL(ctx,object.Key);a.download=object.Key.split('/').pop()||'download';document.body.append(a);a.click();a.remove();return;
 }
 if(action==='edit'){
  const data=await devApi(ctx,'dev_text',{key:object.Key});devForm('Edit '+object.Key,[{name:'text',label:'UTF-8 text',value:data.text,rows:14},{name:'json',label:'Validate as JSON',kind:'checkbox',value:object.Key.endsWith('.json')||data.contentType.includes('json')}],async p=>{
   if(!confirm('Save changes to '+object.Key+'? This replaces the current content.'))return false;
   await devApi(ctx,'dev_save_text',{key:object.Key,etag:data.etag,contentType:data.contentType,metadata:data.metadata,...p});await s3Refresh(bucket);
  },'The editor preserves content type and custom metadata. It sends a conditional ETag write to detect stale edits. Text is limited to 1 MB.');return;
 }
 if(action==='versions'){await devObjectVersions(ctx,object.Key);return;}
 if(action==='link'){
  devForm('Presigned URL',[{name:'method',label:'Operation',options:[['get_object','Download (GET)'],['put_object','Upload (PUT)']]},{name:'expires',label:'Expires in seconds (maximum 3600)',value:'300',kind:'input'}],async(p,body)=>{const result=await devApi(ctx,'dev_presign',{key:object.Key,...p});body.querySelector('.dev-url')?.remove();const box=el('div','','dev-url'),field=document.createElement('textarea');field.readOnly=true;field.value=result.url;field.setAttribute('aria-label','Presigned URL');box.append(el('p',result.method+' · Uses the public LocalStack hostname'),field,devButton('Copy URL',()=>navigator.clipboard.writeText(result.url)));body.append(box);return false;});return;
 }
 return developerS3Object(action,object,bucket,region);
};
async function devObjectVersions(ctx,key,markers={}){
 const data=await devApi(ctx,'dev_object_versions',{key,...markers}),body=devOpen('Versions of '+key,'Restoring copies the selected version into a new current version. Delete markers remain in history.');
 const rows=[...(data.Versions||[]).map(v=>({...v,kind:'Object'})),...(data.DeleteMarkers||[]).map(v=>({...v,kind:'Delete marker'}))].sort((a,b)=>String(b.LastModified).localeCompare(String(a.LastModified)));
 body.append(devTable([{label:'Version',render:v=>v.VersionId},{label:'Kind',render:v=>v.kind+(v.IsLatest?' · current':'')},{label:'Modified',render:v=>String(v.LastModified)},{label:'Actions',render:v=>v.kind==='Object'?devTools(devButton('Restore',async()=>{if(!confirm('Restore version '+v.VersionId+' as current?'))return;await devApi(ctx,'dev_restore_object',{key,version:v.VersionId});await s3Refresh(ctx.resource);await devObjectVersions(ctx,key);}),devButton('Download version',()=>{const a=el('a','');a.href=devTransferURL(ctx,key,v.VersionId);a.download=key.split('/').pop()||'download';a.click();})):''}],rows));
 if(data.IsTruncated)body.append(devButton('Next version page',()=>devObjectVersions(ctx,key,{keyMarker:data.NextKeyMarker,versionMarker:data.NextVersionIdMarker})));
}
const developerS3Draw=s3Draw;
s3Draw=function(){developerS3Draw();const ctx=devContext(),bar=devTools(devButton('Enable bucket versioning',async()=>{if(!confirm('Enable versioning for future object changes in this bucket?'))return;await devApi(ctx,'dev_versioning',{enable:true});devNotice('Bucket versioning enabled.');}));
 const path=el('div','','tools dev-breadcrumb');path.append(devButton('Bucket root',()=>s3Refresh(ctx.resource,'')));let prefix='';for(const segment of s3State.prefix.split('/').filter(Boolean)){prefix+=segment+'/';const target=prefix;path.append(devButton(segment+' /',()=>s3Refresh(ctx.resource,target)));}bar.append(path);s3Files.prepend(bar);
 const folders=s3State.data?.CommonPrefixes||[];if(folders.length){const box=el('div','','dev-folders');for(const entry of folders)box.append(devButton('📁 '+entry.Prefix,()=>s3Refresh(ctx.resource,entry.Prefix)));s3Files.querySelector('.s3-filter').after(box);}
 const drop=el('div','Drop files here, then review and start the upload.','dev-drop');drop.ondragover=e=>{e.preventDefault();drop.classList.add('dragging');};drop.ondragleave=()=>drop.classList.remove('dragging');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('dragging');if(e.dataTransfer.files.length)devUploadFiles(ctx,[...e.dataTransfer.files]);};s3Files.append(drop);
};

// Keep workbench requests scoped to the resource that opened them.
const beforeDeveloperDetail=detail;
detail=async function(resource,...args){
 const ctx={service,resource,region:$('region').value,request:requestId};developerPanel.hidden=true;devSerial++;
 await beforeDeveloperDetail(resource,...args);if(!devCurrent(ctx))return;
 if(service==='s3'){
  const upload=[...$('actions').querySelectorAll('button')].find(b=>b.textContent==='Upload file');if(upload){upload.textContent='Upload files';upload.onclick=()=>devUploadFiles(ctx);}return;
 }
 developerPanel.hidden=false;$('detail').hidden=true;developerPanel.replaceChildren();
 try{
  if(ctx.service==='sqs'){
   const old=[...$('actions').querySelectorAll('button')].find(b=>b.textContent==='Receive up to 10');old?.remove();await devQueue(ctx,developerPanel);
  }else if(ctx.service==='dynamodb')await devItems(ctx,developerPanel);
  else if(ctx.service==='sns')await devTopic(ctx,developerPanel);
  else if(ctx.service==='lambda')await devLambda(ctx,developerPanel);
  else if(ctx.service==='secretsmanager')await devSecret(ctx,developerPanel);
  else if(ctx.service==='ssm'){developerPanel.append(el('h3','Parameter versions'),devButton('Compare / restore versions and labels',()=>devConfigVersions(ctx)));}
  if(devCurrent(ctx))developerPanel.append(devRaw($('detail').textContent,'Original response'));
 }catch(e){if(devCurrent(ctx)){developerPanel.append(el('p',e.message,'dev-error'),devButton('Retry workspace',()=>detail(resource)));$('detail').hidden=false;}}
};
const beforeDeveloperLoad=load;
load=async function(...args){devSerial++;developerPanel.hidden=true;return beforeDeveloperLoad(...args);};
const beforeDeveloperOutput=output;
output=function(...args){devSerial++;developerPanel.hidden=true;return beforeDeveloperOutput(...args);};
const beforeDeveloperRender=render;
render=function(){beforeDeveloperRender();devParameterTree();};
