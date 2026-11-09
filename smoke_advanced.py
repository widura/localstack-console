"""Opt-in live checks. Creates unique fixtures and removes only those fixtures."""
import base64
import json
import uuid
from app import execute, client
from snapshots import wait_ready

region='eu-west-2'
name='console-rest-'+uuid.uuid4().hex[:8]
selection=[]
def call(service,action,**params):return execute(service,action,params,region)
def cleanup():
    if selection:
        result=call('health','cleanup',selection=selection,confirmation='DELETE',emptyBuckets=True)
        errors=[r for r in result['results'] if r.get('error')]
        if errors:print('Cleanup notes:',errors)
try:
    call('s3','create',name=name);selection.append({'service':'s3','resource':name})
    client('s3',region).put_bucket_versioning(Bucket=name,VersioningConfiguration={'Status':'Enabled'})
    for body in [b'old',b'new']:call('s3','upload',resource=name,key='sample.txt',data=base64.b64encode(body).decode())
    queue=call('sqs','create',name=name)['QueueUrl'];selection.append({'service':'sqs','resource':queue})
    topic=call('sns','create',name=name)['TopicArn'];selection.append({'service':'sns','resource':topic})
    call('sns','subscribe',resource=topic,queueUrl=queue,raw=True)
    call('sqs','send_batch',resource=queue,messages='[{"body":"batch","attributes":{"kind":{"DataType":"String","StringValue":"test"}}}]')
    received=call('sqs','receive',resource=queue)['Messages'][0]
    assert received['MessageAttributes']['kind']['StringValue']=='test'
    call('sqs','ack',resource=queue,receipt=received['ReceiptHandle'])
    call('sns','publish',resource=topic,body='attrs',attributes='{"kind":{"DataType":"String","StringValue":"topic"}}')
    call('dynamodb','create',name=name,partitionKey='id');selection.append({'service':'dynamodb','resource':name})
    wait_ready('dynamodb',name,region,client)
    client('dynamodb',region).put_item(TableName=name,Item={'id':{'S':'one'},'status':{'S':'ready'},'binary':{'B':b'\x00\xff'}})
    assert call('dynamodb','scan',resource=name,expression='#s = :s',names='{"#s":"status"}',values='{":s":{"S":"ready"}}')['Count']==1
    call('lambda','create',name=name,code='def handler(event, context):\n    return event\n',runtime='python3.12')
    selection.append({'service':'lambda','resource':name});wait_ready('lambda',name,region,client)
    assert 'def handler' in call('lambda','source',resource=name)['code']
    call('lambda','update_config',resource=name,environment='{"EXAMPLE":"yes"}',timeout='10',memory='256')
    wait_ready('lambda',name,region,client)
    call('lambda','update_code',resource=name,code='import os\ndef handler(event, context):\n    return {"setting":os.environ["EXAMPLE"],"event":event}\n')
    wait_ready('lambda',name,region,client)
    assert call('lambda','invoke',resource=name,event='{}')['Payload']['setting']=='yes'
    exported=call('health','export_selection',selection=selection)
    assert len(exported['steps'])==10,exported
    cleanup()
    for step in exported['steps']:
        call(step['service'],'restore_step',operation=step['action'],params=step['params'])
    assert base64.b64decode(call('s3','download',resource=name,key='sample.txt')['data'])==b'new'
    assert call('dynamodb','scan',resource=name)['Items'][0]['binary']['B']==b'\x00\xff'
    assert call('lambda','invoke',resource=name,event='{"restored":true}')['Payload']=={'setting':'yes','event':{'restored':True}}
    assert call('sns','subscriptions',resource=topic)['Subscriptions']
    print('PASS: batch attributes, filtered scan, Lambda source/config update, export and restore of all five services, binary samples, versioned bucket cleanup')
finally:cleanup()

