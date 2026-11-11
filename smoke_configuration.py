"""Opt-in live service checks using unique, disposable LocalStack resources."""
import base64
import json
import uuid
from urllib.request import Request,urlopen
from app import execute

region='eu-west-2';prefix='/console-config-check/'+uuid.uuid4().hex[:10];created=[]
def call(service,action,**params):
    body=json.dumps({'service':service,'action':action,'region':region,**params}).encode()
    with urlopen(Request('http://localhost:8080/api/action',data=body,headers={'Content-Type':'application/json'}),timeout=20) as response:return json.load(response)
try:
    for name,kind,value in [(prefix+'/secret','text','{"demo":true}'),(prefix+'/binary','binary','AP8=')]:
        call('secretsmanager','create',name=name,valueType=kind,value=value);created.append(('secretsmanager',name))
    for kind,value in [('String','demo'),('StringList','one,two'),('SecureString','test-only-value')]:
        name=prefix+'/'+kind;call('ssm','create',name=name,parameterType=kind,value=value);created.append(('ssm',name))
        assert call('ssm','detail',resource=name)['Parameter']['Type']==kind
        assert call('ssm','reveal',resource=name)['Parameter']['Value']==value
    for service,name in created:
        assert name in [entry['Name'] for entry in call(service,'list')['items']]
    secret=prefix+'/secret';parameter=prefix+'/SecureString'
    call('secretsmanager','update_value',resource=secret,value='updated-test')
    assert call('secretsmanager','reveal',resource=secret)['SecretString']=='updated-test'
    assert len(call('secretsmanager','history',resource=secret)['Versions'])>=2
    call('ssm','update_value',resource=parameter,value='updated-test')
    assert call('ssm','reveal',resource=parameter)['Parameter']['Value']=='updated-test'
    assert all('Value' not in v for v in call('ssm','history',resource=parameter)['Versions'])
    call('secretsmanager','delete',resource=secret)
    assert call('secretsmanager','detail',resource=secret).get('DeletedDate')
    call('secretsmanager','restore_secret',resource=secret)
    assert call('secretsmanager','reveal',resource=secret)['SecretString']=='updated-test'
    exported=call('health','export_selection',selection=[{'service':s,'resource':n} for s,n in created],includeSensitiveValues=True)
    for step in exported['steps']:
        p={**step['params'],'name':step['params']['name']+'-restored'}
        call(step['service'],'restore_step',operation=step['action'],params=p);created.append((step['service'],p['name']))
    assert call('secretsmanager','reveal',resource=prefix+'/binary-restored')['SecretBinary']=='AP8='
    assert call('ssm','reveal',resource=parameter+'-restored')['Parameter']['Value']=='updated-test'
    print('PASS: HTTP routes, both service listings, text/binary secrets, all parameter types, updates/history, deletion recovery, value export/restore')
finally:
    for service,name in reversed(created):
        execute(service,'delete',{'resource':name,'forceDelete':True},region)
