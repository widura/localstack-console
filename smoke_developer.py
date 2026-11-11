"""Opt-in live integration test: uniquely named LocalStack fixtures, always cleaned up."""
import hashlib
import json
import time
import uuid
from urllib.parse import urlencode,urlsplit,urlunsplit
from urllib.request import Request,urlopen
from app import execute,client
from snapshots import wait_ready

region='eu-west-2';name='console-workbench-'+uuid.uuid4().hex[:8];created=[];mapping=None;role=None

def call(service,action,**params):return execute(service,action,params,region)
def wait(predicate,seconds=30):
    for _ in range(seconds):
        result=predicate()
        if result:return result
        time.sleep(1)
    raise AssertionError('Timed out waiting for LocalStack state')
try:
    call('s3','create',name=name);created.append(('s3',name))
    call('s3','dev_versioning',resource=name,enable=True)
    data=b'stream-check-'*(800000)
    query=urlencode({'bucket':name,'key':'folder/large.bin','region':region});url='http://localhost:8080/api/s3/object?'+query
    with urlopen(Request(url,data=data,method='PUT',headers={'Content-Type':'application/octet-stream'}),timeout=30) as response:assert response.status==200
    with urlopen(url,timeout=30) as response:assert hashlib.sha256(response.read()).digest()==hashlib.sha256(data).digest()
    assert call('s3','dev_folders',resource=name)['CommonPrefixes'][0]['Prefix']=='folder/'
    one=client('s3',region).put_object(Bucket=name,Key='config.json',Body=b'{"version":1}',ContentType='application/json')
    text=call('s3','dev_text',resource=name,key='config.json')
    call('s3','dev_save_text',resource=name,key='config.json',text='{"version":2}',etag=text['etag'],json=True)
    try:call('s3','dev_save_text',resource=name,key='config.json',text='bad',etag=text['etag'])
    except ValueError:pass
    else:raise AssertionError('Stale S3 edit was accepted')
    call('s3','dev_restore_object',resource=name,key='config.json',version=one['VersionId'])
    assert json.loads(call('s3','dev_text',resource=name,key='config.json')['text'])['version']==1
    signed=call('s3','dev_presign',resource=name,key='config.json')['url'];parts=urlsplit(signed)
    gateway=urlsplit(client('s3',region).meta.endpoint_url)
    with urlopen(Request(urlunsplit((gateway.scheme,gateway.netloc,parts.path,parts.query,'')),headers={'Host':parts.netloc}),timeout=10) as response:assert json.load(response)['version']==1
    print('PASS: multipart streamed upload/download, folders, conditional text edit, S3 restore and presigned GET',flush=True)

    queue=call('sqs','create',name=name)['QueueUrl'];created.append(('sqs',queue))
    dlq=call('sqs','create',name=name+'-dlq')['QueueUrl'];created.append(('sqs',dlq))
    call('sqs','dev_queue_settings',resource=queue,settings={'VisibilityTimeout':15,'ReceiveMessageWaitTimeSeconds':1})
    call('sqs','dev_set_dlq',resource=queue,queue=dlq,maxReceives=5)
    client('sqs',region).send_message(QueueUrl=dlq,MessageBody='redrive-check')
    task=call('sqs','dev_redrive',resource=dlq,destination=queue,rate=10)
    tasks=wait(lambda:call('sqs','dev_redrive_tasks',resource=dlq).get('Results'))
    wait(lambda:any(t['Status']=='COMPLETED' for t in call('sqs','dev_redrive_tasks',resource=dlq).get('Results',[])))
    messages=client('sqs',region).receive_message(QueueUrl=queue,WaitTimeSeconds=2).get('Messages',[])
    assert any(m['Body']=='redrive-check' for m in messages)
    for m in messages:client('sqs',region).delete_message(QueueUrl=queue,ReceiptHandle=m['ReceiptHandle'])
    print('PASS: queue settings, DLQ policy and native redrive',flush=True)

    call('dynamodb','create',name=name,partitionKey='id');created.append(('dynamodb',name));wait_ready('dynamodb',name,region,client)
    result=call('dynamodb','dev_import_items',resource=name,items=[{'id':{'S':'one'},'email':{'S':'a@example.test'},'status':{'S':'old'}},{'bad':{'S':'missing-key'}},{'id':{'S':'two'},'email':{'S':'b@example.test'}}])
    assert [r.get('status') for r in result['results']]==['saved',None,'saved']
    call('dynamodb','dev_update_item',resource=name,key={'id':{'S':'one'}},attribute='status',old={'S':'old'},value={'S':'new'})
    call('dynamodb','dev_create_index',resource=name,name='email-index',partition='email',types={'email':'S'})
    wait(lambda:any(i['IndexStatus']=='ACTIVE' for i in client('dynamodb',region).describe_table(TableName=name)['Table'].get('GlobalSecondaryIndexes',[])))
    assert call('dynamodb','dev_items',resource=name,index='email-index',partition='email',value={'S':'a@example.test'})['Count']==1
    print('PASS: partial fixture import, conditional item edit, GSI create/query',flush=True)

    secret=name+'/secret';old=call('secretsmanager','create',name=secret,value='{"password":"old"}');created.append(('secretsmanager',secret))
    call('secretsmanager','update_value',resource=secret,value='{"password":"new"}')
    call('secretsmanager','dev_secret_stage',resource=secret,version=old['VersionId'],stage='tested')
    call('secretsmanager','dev_secret_stage',resource=secret,version=old['VersionId'],stage='AWSCURRENT')
    assert json.loads(call('secretsmanager','reveal',resource=secret)['SecretString'])['password']=='old'
    param='/'+name+'/dev/key';other='/'+name+'/test/key'
    for p in [param,other]:call('ssm','create',name=p,value='old',parameterType='SecureString');created.append(('ssm',p))
    call('ssm','dev_parameter_labels',resource=param,version=1,labels=['stable'])
    call('ssm','update_value',resource=param,value='new')
    assert call('ssm','dev_parameter_version',resource=param,version=1)['Parameter']['Value']=='old'
    call('ssm','dev_parameter_rollback',resource=param,version=1)
    assert call('ssm','reveal',resource=param)['Parameter']['Value']=='old'
    comparison=call('ssm','dev_environment_compare',left='/'+name+'/dev',right='/'+name+'/test',compareValues=True)
    assert comparison['Parameters'][0]['valuesEqual'] is True
    try:call('ssm','dev_parameter_labels',resource=param,version=1,labels=['stable'],remove=True)
    except Exception as e:
        if 'cannot remove parameter labels' not in str(e) and 'unlabel_parameter_version action has not been implemented' not in str(e):raise
        print('LOCALSTACK LIMITATION: label removal is unavailable; assignment/movement works',flush=True)
    print('PASS: secret staging rollback, parameter version labels/rollback, environment comparison',flush=True)

    topic=call('sns','create',name=name)['TopicArn'];created.append(('sns',topic))
    sub=call('sns','subscribe',resource=topic,queueUrl=queue,raw=True)['SubscriptionArn']
    call('sns','dev_subscription_settings',resource=topic,subscription=sub,filter={'type':['accepted']},scope='MessageBody',raw=True)
    call('sns','publish',resource=topic,body='{"type":"ignored"}')
    call('sns','publish',resource=topic,body='{"type":"accepted","id":"filtered"}')
    messages=client('sqs',region).receive_message(QueueUrl=queue,WaitTimeSeconds=2,MaxNumberOfMessages=10).get('Messages',[])
    assert len(messages)==1 and json.loads(messages[0]['Body'])['type']=='accepted'
    for m in messages:client('sqs',region).delete_message(QueueUrl=queue,ReceiptHandle=m['ReceiptHandle'])
    print('PASS: SNS body filters and destination inspection',flush=True)

    iam=client('iam',region);role=name+'-role'
    arn=iam.create_role(RoleName=role,AssumeRolePolicyDocument=json.dumps({'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'lambda.amazonaws.com'},'Action':'sts:AssumeRole'}]}))['Role']['Arn']
    queueArn=client('sqs',region).get_queue_attributes(QueueUrl=queue,AttributeNames=['QueueArn'])['Attributes']['QueueArn']
    tableArn=client('dynamodb',region).describe_table(TableName=name)['Table']['TableArn']
    iam.put_role_policy(RoleName=role,PolicyName='FixtureOnly',PolicyDocument=json.dumps({'Version':'2012-10-17','Statement':[{'Effect':'Allow','Action':['sqs:ReceiveMessage','sqs:DeleteMessage','sqs:GetQueueAttributes'],'Resource':queueArn},{'Effect':'Allow','Action':['dynamodb:PutItem'],'Resource':tableArn},{'Effect':'Allow','Action':['logs:CreateLogGroup','logs:CreateLogStream','logs:PutLogEvents'],'Resource':'arn:aws:logs:*:*:*'}]}))
    source='import boto3,json,os\ndef handler(event,context):\n    print("workbench check")\n    for record in event.get("Records",[]):\n        body=json.loads(record["body"])\n        endpoint=os.environ.get("AWS_ENDPOINT_URL") or "http://"+os.environ.get("LOCALSTACK_HOSTNAME","localstack")+":4566"\n        boto3.client("dynamodb",endpoint_url=endpoint).put_item(TableName=os.environ["TABLE"],Item={"id":{"S":body["id"]},"status":{"S":"processed"}})\n    return {"ok":True}\n'
    call('lambda','create',name=name,role=arn,runtime='python3.12',code=source,timeout=10);created.append(('lambda',name));wait_ready('lambda',name,region,client)
    call('lambda','update_config',resource=name,environment=json.dumps({'TABLE':name}));wait_ready('lambda',name,region,client)
    run=call('lambda','dev_invoke',resource=name,event={});assert run['Payload']=={'ok':True};assert run['RoundTripMs']>0
    version=call('lambda','dev_publish_version',resource=name,description='fixture')['Version'];call('lambda','dev_alias',resource=name,name='dev',version=version)
    assert call('lambda','dev_invoke',resource=name,event={},qualifier='dev')['Payload']['ok']
    mapping=call('lambda','dev_add_sqs_trigger',resource=name,queue=queue,batchSize=1)['UUID']
    wait(lambda:client('lambda',region).get_event_source_mapping(UUID=mapping)['State']=='Enabled')
    call('sns','publish',resource=topic,body='{"type":"accepted","id":"end-to-end"}')
    wait(lambda:client('dynamodb',region).get_item(TableName=name,Key={'id':{'S':'end-to-end'}}).get('Item'),seconds=60)
    call('lambda','dev_mapping_state',resource=name,uuid=mapping,enabled=False)
    assert call('sqs','dev_consumers',resource=queue)['EventSourceMappings']
    print('PASS: Lambda timing/logs, versions/aliases and SNS → SQS → Lambda → DynamoDB',flush=True)
finally:
    if mapping:
        try:client('lambda',region).delete_event_source_mapping(UUID=mapping)
        except Exception:pass
    for service,resource in reversed(created):
        try:
            if service=='s3':call('s3','empty_bucket',resource=resource)
            call(service,'delete',resource=resource,forceDelete=True)
        except Exception as e:print('Fixture cleanup failed:',service,resource,str(e),flush=True)
    if role:
        try:
            iam=client('iam',region);iam.delete_role_policy(RoleName=role,PolicyName='FixtureOnly');iam.delete_role(RoleName=role)
        except Exception as e:print('Fixture role cleanup:',str(e),flush=True)
