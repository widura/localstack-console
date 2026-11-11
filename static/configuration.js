// Values are fetched only when explicitly revealed or opened for editing.
const isConfiguration=target=>['secretsmanager','ssm'].includes(target);
const valueDialog=document.createElement('dialog');valueDialog.id='configurationValueDialog';
const valueHeading=el('h2',''),valueHint=el('p',''),valueText=document.createElement('textarea'),valueClose=el('button','Hide value');
valueText.readOnly=true;valueText.rows=12;valueText.setAttribute('aria-label','Stored value');valueText.autocomplete='off';valueText.spellcheck=false;
valueClose.type='button';valueClose.onclick=()=>valueDialog.close();valueDialog.append(valueHeading,valueHint,valueText,valueClose);document.body.append(valueDialog);
let valueRequest=0;
valueDialog.addEventListener('close',()=>{valueRequest++;valueText.value='';});
async function revealConfiguration(resource,target,region){
 const request=++valueRequest;valueHeading.textContent=resource;valueHint.textContent='Loading value…';valueText.value='';valueDialog.showModal();
 try{const data=await api('reveal',{resource,region},target);if(request!==valueRequest||!valueDialog.open)return;
  const binary=target==='secretsmanager'&&'SecretBinary' in data;
  valueHint.textContent=binary?'Binary secret · base64 encoded':'Current stored value · '+region;
  valueText.value=target==='ssm'?data.Parameter.Value:binary?data.SecretBinary:data.SecretString;
 }catch(e){if(request===valueRequest&&valueDialog.open)valueHint.textContent=e.message;}
}
const configurationDetail=detail;
detail=async function(resource,...args){const target=service,id=requestId,region=$('region').value;await configurationDetail(resource,...args);
 if(!isConfiguration(target)||service!==target||id!==requestId||selected!==resource||$('detailPanel').hidden)return;
 const add=(label,fn)=>{const b=el('button',label);b.onclick=async()=>{b.disabled=true;try{await fn();}catch(e){error(e);}finally{b.disabled=false;}};$('actions').append(b);};
 add('Reveal value',()=>revealConfiguration(resource,target,region));
 add('Update value',()=>work('update_value'));
 add('Version history',()=>detail(resource,'history'));
 if(target==='secretsmanager')add('Cancel scheduled deletion',async()=>{if(confirm('Cancel scheduled deletion for '+resource+'?')){await api('restore_secret',{resource,region},target);await detail(resource);}});
};
const configurationWork=work;
work=function(action){
 if(isConfiguration(service)&&action==='update_value')workflowSpecs.update_value=['Update stored value',service==='secretsmanager'?[['valueType','Value format','text'],['value','New value','']]:[['value','New value','']]];
 configurationWork(action);
 if(!isConfiguration(service))return;
 workDialog.querySelector('.save').hidden=true;
 if(action==='delete'&&service==='secretsmanager'){
  workDialog.querySelector('h2').textContent='Delete secret';
  workDialog.querySelector('p').textContent='Schedule deletion with a 7-day recovery window, or explicitly choose permanent deletion below.';
  const wrap=el('div','','formfield'),label=el('label','Delete immediately without recovery'),force=document.createElement('input');
  force.type='checkbox';force.name='forceDelete';force.id='forceSecretDelete';label.htmlFor=force.id;wrap.append(label,force);workDialog.querySelector('.workfields').append(wrap);
 }
 if(action!=='update_value')return;
 const ctx=workContext,submit=workDialog.querySelector('[type=submit]');submit.disabled=true;
 if(service==='secretsmanager'){
  const old=workDialog.querySelector('[name=valueType]'),select=document.createElement('select');select.id=old.id;select.name='valueType';
  for(const [value,label] of [['text','Text / JSON'],['binary','Base64 binary']]){const option=el('option',label);option.value=value;select.append(option);}old.replaceWith(select);
 }
 const field=workDialog.querySelector('[name=value]');field.autocomplete='off';field.spellcheck=false;
 workDialog.querySelector('p').textContent='Loading current value for editing. Saving creates a new version; parameter type and encryption settings are preserved.';
 api('reveal',{resource:ctx.resource,region:ctx.region},ctx.service).then(data=>{
  if(workContext!==ctx||!workDialog.open)return;
  const binary='SecretBinary' in data;
  field.value=ctx.service==='ssm'?data.Parameter.Value:binary?data.SecretBinary:data.SecretString;
  if(ctx.service==='secretsmanager')workDialog.querySelector('[name=valueType]').value=binary?'binary':'text';
  workDialog.querySelector('p').textContent='Saving creates a new version. Values are not saved to browser payloads or recipe history.';
 }).catch(e=>{if(workContext===ctx)workDialog.querySelector('.workerror').textContent=e.message;}).finally(()=>{if(workContext===ctx)submit.disabled=false;});
};
workDialog.addEventListener('close',()=>{if(isConfiguration(workContext?.service))for(const f of workDialog.querySelectorAll('[name=value]'))f.value='';});
$('dialog').addEventListener('close',()=>{if(isConfiguration(pending?.service))for(const f of $('fields').querySelectorAll('[name=value]'))f.value='';});
const configurationRender=render;
render=function(){configurationRender();if(!isConfiguration(service))return;
 const byName=new Map(items.map(item=>[nameOf(item),item]));for(const row of $('list').querySelectorAll('.row')){const item=byName.get(row.querySelector('.name').textContent);if(item)row.querySelector('.badge').textContent=item.DeletedDate?'Scheduled for deletion':item.Type||'Secret';}
};
