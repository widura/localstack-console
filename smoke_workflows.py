import base64
import json
import time
import uuid
from app import execute

region='eu-west-2'
name='console-check-'+uuid.uuid4().hex[:10]
created=[]
def call(s,a,**p): return execute(s,a,p,region)
try:
    call('s3','create',name=name);created.append(('s3',name))
    call('s3','upload',resource=name,key='sample.json',data=base64.b64encode(b'{"ok":true}').decode(),contentType='application/json')
    assert base64.b64decode(call('s3','download',resource=name,key='sample.json')['data'])==b'{"ok":true}'
    call('s3','delete_object',resource=name,key='sample.json')
    queue=call('sqs','create',name=name)['QueueUrl'];created.append(('sqs',queue))
    topic=call('sns','create',name=name)['TopicArn'];created.append(('sns',topic))
    call('sns','subscribe',resource=topic,queueUrl=queue,raw=True)
    assert call('sns','subscriptions',resource=topic)['Subscriptions']
    call('sns','publish',resource=topic,body='integration test')
    messages=[]
    for _ in range(10):
        messages=call('sqs','receive',resource=queue).get('Messages',[])
        if messages:break
    assert messages and messages[0]['Body']=='integration test'
    call('sqs','ack',resource=queue,receipt=messages[0]['ReceiptHandle'])
    call('dynamodb','create',name=name,partitionKey='id');created.append(('dynamodb',name))
    call('dynamodb','put',resource=name,item='{"id":{"S":"one"},"value":{"N":"42"}}')
    result=call('dynamodb','query',resource=name,expression='#id = :id',names='{"#id":"id"}',values='{":id":{"S":"one"}}')
    assert result['Count']==1
    call('dynamodb','delete_item',resource=name,key='{"id":{"S":"one"}}')
    print('PASS: live S3 binary transfer, SNS-to-SQS delivery and acknowledgement, DynamoDB put/query/delete')
finally:
    for service,resource in reversed(created):
        call(service,'delete',resource=resource)
