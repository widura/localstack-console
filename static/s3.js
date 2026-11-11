// S3 object browser: keys stay attached to row actions, never manually re-entered.
const s3Files=el('div','','s3-files');
s3Files.id='s3Files';s3Files.hidden=true;$('detailPanel').append(s3Files);
const s3State={bucket:'',region:'',prefix:'',tokens:[null],page:0,data:null,serial:0};
const objectDialog=document.createElement('dialog');objectDialog.id='s3ObjectDialog';
const objectTitle=el('h2',''),objectInfo=el('p',''),objectBody=el('div','','s3-preview'),objectClose=el('button','Close');
objectClose.type='button';objectClose.onclick=()=>objectDialog.close();
objectDialog.append(objectTitle,objectInfo,objectBody,objectClose);document.body.append(objectDialog);
let previewURL=null,previewSerial=0;
objectDialog.addEventListener('close',()=>{previewSerial++;if(previewURL){URL.revokeObjectURL(previewURL);previewURL=null;}objectBody.replaceChildren();});
function s3Size(value){if(!value)return '0 B';const units=['B','KB','MB','GB','TB'],i=Math.min(Math.floor(Math.log(value)/Math.log(1024)),units.length-1);return (value/1024**i).toLocaleString(undefined,{maximumFractionDigits:i?1:0})+' '+units[i];}
function s3Date(value){const d=new Date(value);return Number.isNaN(d.getTime())?String(value||'—'):d.toLocaleString();}
function s3Active(bucket,region){return service==='s3'&&selected===bucket&&$('region').value===region&&!$('detailPanel').hidden;}
function s3Button(label,fn,cls){const b=el('button',label,cls);b.type='button';b.onclick=async()=>{b.disabled=true;try{await fn();}catch(e){error(e);}finally{b.disabled=false;}};return b;}
async function s3Refresh(bucket=s3State.bucket,prefix){
 const region=$('region').value;
 if(!s3Active(bucket,region))return;
 if(s3State.bucket!==bucket||s3State.region!==region){Object.assign(s3State,{bucket,region,prefix:'',tokens:[null],page:0});}
 if(prefix!==undefined&&prefix!==s3State.prefix){s3State.prefix=prefix;s3State.tokens=[null];s3State.page=0;}
 const serial=++s3State.serial,request=requestId;
 $('detail').hidden=true;s3Files.hidden=false;s3Files.setAttribute('aria-busy','true');
 s3Files.replaceChildren(el('div','Loading files…','empty'));
 try{
  const data=await api('dev_folders',{resource:bucket,region,prefix:s3State.prefix,...(s3State.tokens[s3State.page]?{cursor:s3State.tokens[s3State.page]}:{})},'s3');
  if(serial!==s3State.serial||request!==requestId||!s3Active(bucket,region))return;
  s3State.data=data;s3Draw();
 }catch(e){if(serial===s3State.serial&&s3Active(bucket,region)){
  s3Files.replaceChildren(el('div','Unable to load files. '+e.message,'empty'),s3Button('Retry',()=>s3Refresh(bucket)));error(e);
 }}finally{if(serial===s3State.serial)s3Files.removeAttribute('aria-busy');}
}
function s3Draw(){
 const {bucket,region,prefix,page,data}=s3State;
 s3Files.replaceChildren();
 const filter=el('form','','s3-filter tools'),label=el('label','Key prefix'),input=document.createElement('input');
 input.id='s3Prefix';input.value=prefix;input.placeholder='e.g. uploads/';label.htmlFor=input.id;
 const apply=el('button','Browse');apply.type='submit';filter.append(label,input,apply);
 if(prefix)filter.append(s3Button('Show all files',()=>s3Refresh(bucket,'')));
 filter.onsubmit=e=>{e.preventDefault();s3State.tokens=[null];s3State.page=0;s3Refresh(bucket,input.value);};s3Files.append(filter);
 const objects=data.Contents||[],total=objects.reduce((sum,o)=>sum+o.Size,0);
 s3Files.append(el('p',objects.length+' objects · '+s3Size(total)+' on this page · Page '+(page+1),'s3-count'));
 if(!objects.length)s3Files.append(el('div',prefix?'No files match this prefix.':'This bucket is empty. Upload a file to get started.','empty'));
 else{
  const wrap=el('div','','s3-table-wrap'),table=el('table','','s3-table'),caption=el('caption','Files in '+bucket+(prefix?' matching '+prefix:''));
  const head=el('thead',''),headRow=el('tr','');for(const title of ['File name / key','Size','Last modified','Actions']){const th=el('th',title);th.scope='col';headRow.append(th);}head.append(headRow);
  const body=el('tbody','');
  for(const object of objects){const row=el('tr',''),name=el('td','','s3-name'),actions=el('td','','s3-row-actions');
   const open=s3Button(object.Key,()=>s3Object(object.Size>750000?'metadata':'preview',object,bucket,region),'s3-key');open.title=object.Key;name.append(open);
   const buttons=el('div','','tools');
   for(const [action,title] of [['preview','Preview'],['download','Download'],['metadata','Details'],['edit','Edit text'],['versions','Versions'],['link','Presigned URL'],['copy','Copy key'],['delete','Delete']]){
    const button=s3Button(title,()=>s3Object(action,object,bucket,region),action==='delete'?'s3-delete':'');button.setAttribute('aria-label',title+' '+object.Key);
    if(object.Size>750000&&action==='preview'){button.disabled=true;button.title='Preview limit is 750 KB. Download streams larger files.';}
    if(object.Size>1000000&&action==='edit'){button.disabled=true;button.title='The text editor is limited to 1 MB.';}
    buttons.append(button);
   }
   actions.append(buttons);row.append(name,el('td',s3Size(object.Size)),el('td',s3Date(object.LastModified)),actions);body.append(row);
  }
  table.append(caption,head,body);wrap.append(table);s3Files.append(wrap);
 }
 const paging=el('div','','tools s3-pagination');
 if(page>0)paging.append(s3Button('Previous files',()=>{s3State.page--;return s3Refresh(bucket);}));
 if(data.NextContinuationToken)paging.append(s3Button('Next files',()=>{s3State.tokens[page+1]=data.NextContinuationToken;s3State.page=page+1;return s3Refresh(bucket);}));
 paging.append(el('span','100 entries per page · Uploads up to 100 MB · Downloads stream directly'));s3Files.append(paging);
 const raw=el('details','','s3-raw');raw.append(el('summary','Raw listing response'),el('pre',JSON.stringify(data,null,2)));s3Files.append(raw);
}
function imageType(bytes){
 if(bytes[0]===137&&bytes[1]===80&&bytes[2]===78&&bytes[3]===71)return 'image/png';
 if(bytes[0]===255&&bytes[1]===216&&bytes[2]===255)return 'image/jpeg';
 if(String.fromCharCode(...bytes.slice(0,6)).match(/^GIF8[79]a$/))return 'image/gif';
 if(String.fromCharCode(...bytes.slice(0,4))==='RIFF'&&String.fromCharCode(...bytes.slice(8,12))==='WEBP')return 'image/webp';
 return null;
}
async function s3Object(action,object,bucket,region){
 if(!s3Active(bucket,region))return;
 const key=object.Key;
 if(action==='copy'){await navigator.clipboard.writeText(key);$('notice').textContent='Copied key: '+key;$('notice').hidden=false;return;}
 if(action==='delete'){
  if(!confirm('Delete "'+key+'" from "'+bucket+'"? In a versioned bucket this adds a delete marker.'))return;
  await api('delete_object',{resource:bucket,region,key},'s3');
  if(s3Active(bucket,region)){await s3Refresh(bucket);$('notice').textContent='Deleted file: '+key;$('notice').hidden=false;}return;
 }
 if(action==='download'){
  const data=await api('download',{resource:bucket,region,key},'s3');
  downloadFile(Uint8Array.from(atob(data.data),c=>c.charCodeAt(0)),key.split('/').pop()||'download',data.contentType||'application/octet-stream');return;
 }
 if(objectDialog.open)objectDialog.close();
 objectTitle.textContent=key;objectInfo.textContent=bucket+' · '+s3Size(object.Size)+' · '+s3Date(object.LastModified);
 objectBody.replaceChildren(el('p','Loading…'));objectDialog.showModal();const serial=++previewSerial;
 try{
  const data=await api(action==='metadata'?'object_metadata':'download',{resource:bucket,region,key},'s3');
  if(serial!==previewSerial||!objectDialog.open)return;
  objectBody.replaceChildren();
  if(action==='metadata'){
   const grid=el('dl','','s3-metadata');
   for(const [label,value] of [['Key',key],['Content type',data.ContentType||'—'],['Size',s3Size(data.ContentLength??object.Size)],['Last modified',s3Date(data.LastModified||object.LastModified)],['ETag',data.ETag||'—'],['Version',data.VersionId||'Not versioned']])grid.append(el('dt',label),el('dd',String(value)));
   objectBody.append(grid);
   if(Object.keys(data.Metadata||{}).length)objectBody.append(el('h3','Custom metadata'),el('pre',JSON.stringify(data.Metadata,null,2)));
   const raw=el('details','','s3-raw');raw.append(el('summary','Raw metadata response'),el('pre',JSON.stringify(data,null,2)));objectBody.append(raw);return;
  }
  const bytes=Uint8Array.from(atob(data.data),c=>c.charCodeAt(0)),type=imageType(bytes);
  if(type){const image=document.createElement('img');image.alt=key;previewURL=URL.createObjectURL(new Blob([bytes],{type}));image.src=previewURL;objectBody.append(image);}
  else{
   let text;
   try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);if(text.includes('\u0000'))text=null;}catch{text=null;}
   if(text===null)objectBody.append(el('p','Preview is available for UTF-8 text, JSON, PNG, JPEG, GIF and WebP. Download this file to open it.'));
   else{try{text=JSON.stringify(JSON.parse(text),null,2);}catch{}const clipped=text.length>64000;objectBody.append(el('pre',text.slice(0,64000)));if(clipped)objectBody.append(el('p','Showing the first 64,000 characters. Download for the complete file.'));}
  }
 }catch(e){if(serial===previewSerial&&objectDialog.open)objectBody.replaceChildren(el('p',e.message,'s3-object-error'));}
}
const beforeS3Detail=detail;
detail=async function(resource,...args){
 if(service!=='s3'){s3State.serial++;s3Files.hidden=true;$('detail').hidden=false;return beforeS3Detail(resource,...args);}
 const scroll=selected!==resource;selected=resource;$('detailPanel').hidden=false;$('detailTitle').textContent=resource;$('error').hidden=true;$('actions').replaceChildren();
 $('actions').append(s3Button('Upload file',()=>work('upload'),'primary'),s3Button('Refresh files',()=>s3Refresh(resource)));
 const admin=el('details','','s3-admin'),adminTools=el('div','','tools');admin.append(el('summary','Bucket actions'),adminTools);
 for(const [label,fn] of [['Copy bucket name',()=>navigator.clipboard.writeText(resource)],['CLI / boto3 snippets',()=>showSnippets('s3',resource)],['Empty bucket (all versions)',()=>work('empty_bucket')],['Delete bucket',()=>work('delete')]])adminTools.append(s3Button(label,fn));
 $('actions').append(admin);await s3Refresh(resource);
 if(scroll&&s3Active(resource,$('region').value))$('detailPanel').scrollIntoView?.({behavior:'smooth',block:'start'});
};
const beforeS3Work=work;
work=function(action){beforeS3Work(action);if(service==='s3'&&action==='upload'){
 const field=workDialog.querySelector('[name=key]'),file=workDialog.querySelector('[type=file]');
 field.value=s3State.bucket===selected?s3State.prefix:'';
 let suggested=field.value;
 file.onchange=()=>{if(file.files[0]&&(field.value===suggested||!field.value)){suggested=(s3State.bucket===selected?s3State.prefix:'')+file.files[0].name;field.value=suggested;}};
 workDialog.querySelector('.save').hidden=true;
 workDialog.querySelector('p').textContent+=' · Choose a file; its name fills the object key. Uploading an existing key replaces its current content.';
}};
const beforeS3Output=output;
output=function(...args){s3State.serial++;s3Files.hidden=true;$('detail').hidden=false;return beforeS3Output(...args);};
const beforeS3Load=load;
load=async function(...args){s3State.serial++;s3Files.hidden=true;$('detail').hidden=false;return beforeS3Load(...args);};
