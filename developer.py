"""Developer workbenches. Each operation has an explicit SDK call and bounded inputs."""
import base64
import json
import time
from urllib.parse import quote, urlsplit
from botocore.exceptions import ClientError
from resources import number
from configuration import parameter_metadata, configuration_operation


def decoded(value):
    return json.loads(value) if isinstance(value,str) else value


def pages(c, operation, key, **kwargs):
    result=[]
    token=None
    while True:
        page=getattr(c,operation)(**kwargs,**({'NextToken':token} if token else {}))
        result.extend(page.get(key,[]));token=page.get('NextToken')
        if not token:return result


def item_key(item, schema):
    return {key['AttributeName']:item[key['AttributeName']] for key in schema}

def typed_attribute(value):
    if 'B' in value and isinstance(value['B'],str):return {'B':base64.b64decode(value['B'],validate=True)}
    if 'BS' in value:return {'BS':[base64.b64decode(v,validate=True) if isinstance(v,str) else v for v in value['BS']]}
    if 'M' in value:return {'M':{k:typed_attribute(v) for k,v in value['M'].items()}}
    if 'L' in value:return {'L':[typed_attribute(v) for v in value['L']]}
    return value

def typed_item(value):return {k:typed_attribute(v) for k,v in value.items()}


def developer(service, action, p, region, client):
    c=client(service,region);r=p.get('resource','')
    if service=='s3':
        if action=='dev_folders':
            args={'Bucket':r,'Prefix':p.get('prefix',''),'Delimiter':'/','MaxKeys':100}
            if p.get('cursor'):args['ContinuationToken']=p['cursor']
            return c.list_objects_v2(**args)
        if action=='dev_versioning':
            if p.get('enable') is True:return c.put_bucket_versioning(Bucket=r,VersioningConfiguration={'Status':'Enabled'})
            return c.get_bucket_versioning(Bucket=r)
        if action=='dev_object_versions':
            args={'Bucket':r,'Prefix':p['key'],'MaxKeys':100}
            if p.get('keyMarker'):args['KeyMarker']=p['keyMarker']
            if p.get('versionMarker'):args['VersionIdMarker']=p['versionMarker']
            result=c.list_object_versions(**args)
            for field in ['Versions','DeleteMarkers']:result[field]=[v for v in result.get(field,[]) if v['Key']==p['key']]
            return result
        if action=='dev_restore_object':
            original=c.head_object(Bucket=r,Key=p['key'],VersionId=p['version'])
            args={'Bucket':r,'Key':p['key'],'CopySource':{'Bucket':r,'Key':p['key'],'VersionId':p['version']},'MetadataDirective':'REPLACE','Metadata':original.get('Metadata',{})}
            for field in ['ContentType','CacheControl','ContentDisposition','ContentEncoding','ContentLanguage','Expires','WebsiteRedirectLocation','ServerSideEncryption','SSEKMSKeyId','StorageClass']:
                if field in original:args[field]=original[field]
            return c.copy_object(**args)
        if action=='dev_text':
            args={'Bucket':r,'Key':p['key']}
            if p.get('version'):args['VersionId']=p['version']
            result=c.get_object(**args)
            try:
                if result.get('ContentLength',0)>1000000:raise ValueError('Text editor limit is 1 MB')
                raw=result['Body'].read(1000001)
                if len(raw)>1000000:raise ValueError('Text editor limit is 1 MB')
                text=raw.decode('utf-8')
                if '\x00' in text:raise ValueError('This object is binary; download it instead')
                return {'text':text,'etag':result.get('ETag'),'contentType':result.get('ContentType','text/plain'),'metadata':result.get('Metadata',{})}
            finally:result['Body'].close()
        if action=='dev_save_text':
            text=p['text']
            if not isinstance(text,str) or len(text.encode())>1000000:raise ValueError('Text editor limit is 1 MB')
            if p.get('json'):json.loads(text)
            if p.get('etag') and c.head_object(Bucket=r,Key=p['key'])['ETag']!=p['etag']:
                raise ValueError('Object changed since the editor opened. Reopen it before saving.')
            # Detect stale edits before writing. S3 conditional PutObject enforces the ETag atomically.
            args={'Bucket':r,'Key':p['key'],'Body':text.encode(),'ContentType':p.get('contentType') or 'text/plain','Metadata':p.get('metadata') or {}}
            if p.get('etag'):args['IfMatch']=p['etag']
            return c.put_object(**args)
        if action=='dev_presign':
            import boto3
            from botocore.config import Config
            endpoint=urlsplit(c.meta.endpoint_url)
            host='localhost' if endpoint.hostname in {'host.docker.internal','localstack'} else endpoint.hostname
            public=endpoint._replace(netloc=host+(':'+str(endpoint.port) if endpoint.port else '')).geturl()
            signing=boto3.client('s3',endpoint_url=public,region_name=region,aws_access_key_id='test',aws_secret_access_key='test',config=Config(signature_version='s3v4',s3={'addressing_style':'path'}))
            op=p.get('method','get_object')
            if op not in {'get_object','put_object'}:raise ValueError('Choose download or upload')
            return {'url':signing.generate_presigned_url(op,Params={'Bucket':r,'Key':p['key']},ExpiresIn=number(p,'expires',300,1,3600)), 'method':'GET' if op=='get_object' else 'PUT'}
    if service=='sqs':
        if action=='dev_consumers':
            arn=c.get_queue_attributes(QueueUrl=r,AttributeNames=['QueueArn'])['Attributes']['QueueArn']
            return {'EventSourceMappings':pages(client('lambda',region),'list_event_source_mappings','EventSourceMappings',EventSourceArn=arn)}
        if action=='dev_queue_settings':
            settings=decoded(p.get('settings',{}));attrs={}
            for key,limits in {'VisibilityTimeout':(0,43200),'DelaySeconds':(0,900),'MessageRetentionPeriod':(60,1209600),'ReceiveMessageWaitTimeSeconds':(0,20)}.items():
                if key in settings:attrs[key]=str(number(settings,key,0,*limits))
            if not attrs:raise ValueError('Provide queue settings')
            return c.set_queue_attributes(QueueUrl=r,Attributes=attrs)
        if action=='dev_set_dlq':
            policy=''
            if p.get('queue'):
                if p['queue']==r:raise ValueError('A queue cannot be its own dead-letter queue')
                arn=c.get_queue_attributes(QueueUrl=p['queue'],AttributeNames=['QueueArn'])['Attributes']['QueueArn']
                policy=json.dumps({'deadLetterTargetArn':arn,'maxReceiveCount':number(p,'maxReceives',5,1,1000)})
            return c.set_queue_attributes(QueueUrl=r,Attributes={'RedrivePolicy':policy})
        if action=='dev_redrive':
            arn=c.get_queue_attributes(QueueUrl=r,AttributeNames=['QueueArn'])['Attributes']['QueueArn']
            args={'SourceArn':arn,'MaxNumberOfMessagesPerSecond':number(p,'rate',10,1,500)}
            if p.get('destination'):
                args['DestinationArn']=c.get_queue_attributes(QueueUrl=p['destination'],AttributeNames=['QueueArn'])['Attributes']['QueueArn']
            return c.start_message_move_task(**args)
        if action=='dev_redrive_tasks':
            arn=c.get_queue_attributes(QueueUrl=r,AttributeNames=['QueueArn'])['Attributes']['QueueArn']
            return c.list_message_move_tasks(SourceArn=arn,MaxResults=10)
        if action=='dev_cancel_redrive':return c.cancel_message_move_task(TaskHandle=p['handle'])
    if service=='sns':
        if action=='dev_subscriptions':
            result=pages(c,'list_subscriptions_by_topic','Subscriptions',TopicArn=r)
            for entry in result:
                if entry['SubscriptionArn'].startswith('arn:'):
                    entry['Settings']=c.get_subscription_attributes(SubscriptionArn=entry['SubscriptionArn'])['Attributes']
                if entry['Protocol']=='sqs':
                    sqs=client('sqs',region)
                    try:entry['QueueUrl']=sqs.get_queue_url(QueueName=entry['Endpoint'].split(':')[-1])['QueueUrl']
                    except ClientError as e:entry['QueueError']=e.response['Error']['Message']
            return {'Subscriptions':result}
        if action=='dev_subscription_settings':
            policy=decoded(p.get('filter','{}'))
            if not isinstance(policy,dict):raise ValueError('Filter policy must be a JSON object')
            scope=p.get('scope','MessageAttributes')
            if scope not in {'MessageAttributes','MessageBody'}:raise ValueError('Invalid filter scope')
            # Verify subscription belongs to the selected topic before changing it.
            arn=p['subscription'];meta=c.get_subscription_attributes(SubscriptionArn=arn)['Attributes']
            if meta.get('TopicArn')!=r:raise ValueError('Subscription does not belong to this topic')
            c.set_subscription_attributes(SubscriptionArn=arn,AttributeName='FilterPolicyScope',AttributeValue=scope)
            c.set_subscription_attributes(SubscriptionArn=arn,AttributeName='FilterPolicy',AttributeValue=json.dumps(policy))
            return c.set_subscription_attributes(SubscriptionArn=arn,AttributeName='RawMessageDelivery',AttributeValue='true' if p.get('raw') is True else 'false')
    if service=='lambda':
        if action=='dev_invoke':
            payload=decoded(p.get('event','{}'));args={'FunctionName':r,'Payload':json.dumps(payload).encode(),'LogType':'Tail'}
            if p.get('qualifier'):args['Qualifier']=p['qualifier']
            start=time.perf_counter();result=c.invoke(**args)
            stream=result.pop('Payload')
            try:body=stream.read().decode('utf-8',errors='replace')
            finally:stream.close()
            try:result['Payload']=json.loads(body)
            except ValueError:result['Payload']=body
            result['RoundTripMs']=round((time.perf_counter()-start)*1000,1)
            result['Logs']=base64.b64decode(result.pop('LogResult','')).decode('utf-8',errors='replace')
            import re
            match=re.search(r'(?<!Billed )Duration: ([\d.]+) ms',result['Logs'])
            result['ExecutionDurationMs']=float(match[1]) if match else None
            return result
        if action=='dev_function_versions':
            versions=[]
            for page in c.get_paginator('list_versions_by_function').paginate(FunctionName=r):versions.extend(page.get('Versions',[]))
            aliases=[]
            for page in c.get_paginator('list_aliases').paginate(FunctionName=r):aliases.extend(page.get('Aliases',[]))
            return {'Versions':versions,'Aliases':aliases}
        if action=='dev_publish_version':return c.publish_version(FunctionName=r,Description=p.get('description',''))
        if action=='dev_alias':
            name=p['name'];args={'FunctionName':r,'Name':name,'FunctionVersion':str(p['version'])}
            try:c.get_alias(FunctionName=r,Name=name)
            except ClientError as e:
                if e.response['Error']['Code']!='ResourceNotFoundException':raise
                return c.create_alias(**args)
            return c.update_alias(**args)
        if action=='dev_mappings':
            return {'EventSourceMappings':pages(c,'list_event_source_mappings','EventSourceMappings',FunctionName=r)}
        if action=='dev_add_sqs_trigger':
            sqs=client('sqs',region);arn=sqs.get_queue_attributes(QueueUrl=p['queue'],AttributeNames=['QueueArn'])['Attributes']['QueueArn']
            return c.create_event_source_mapping(FunctionName=r,EventSourceArn=arn,BatchSize=number(p,'batchSize',10,1,10),Enabled=True)
        if action in {'dev_mapping_state','dev_remove_mapping'}:
            meta=c.get_event_source_mapping(UUID=p['uuid']);function=c.get_function_configuration(FunctionName=r)['FunctionArn']
            if meta['FunctionArn'].split(':function:')[-1].split(':')[0]!=function.split(':function:')[-1].split(':')[0]:raise ValueError('Trigger belongs to another function')
            return c.delete_event_source_mapping(UUID=p['uuid']) if action=='dev_remove_mapping' else c.update_event_source_mapping(UUID=p['uuid'],Enabled=p.get('enabled') is True)
    if service=='dynamodb':
        if action=='dev_items':
            schema=c.describe_table(TableName=r)['Table'];args={'TableName':r,'Limit':50}
            if p.get('index'):args['IndexName']=p['index']
            if p.get('cursor'):args['ExclusiveStartKey']=p['cursor']
            if p.get('partition'):
                names={'#pk':p['partition']};values={':pk':typed_attribute(decoded(p['value']))};expression='#pk = :pk'
                if p.get('sort') and p.get('sortValue'):
                    names['#sk']=p['sort'];values[':sk']=typed_attribute(decoded(p['sortValue']))
                    operator=p.get('sortOp','=')
                    if operator not in {'=','<','<=','>','>=','begins_with'}:raise ValueError('Invalid sort operator')
                    expression+=' AND '+('begins_with(#sk, :sk)' if operator=='begins_with' else '#sk '+operator+' :sk')
                args.update(KeyConditionExpression=expression,ExpressionAttributeNames=names,ExpressionAttributeValues=values)
                data=c.query(**args)
            else:data=c.scan(**args)
            return {'Table':schema,**data}
        if action=='dev_update_item':
            key=typed_item(decoded(p['key']));name=p['attribute'];value=typed_attribute(decoded(p['value']));old=typed_attribute(decoded(p['old']))
            if name in key:raise ValueError('Primary key attributes cannot be edited in place')
            return c.update_item(TableName=r,Key=key,UpdateExpression='SET #field = :value',ConditionExpression='#field = :old',ExpressionAttributeNames={'#field':name},ExpressionAttributeValues={':value':value,':old':old})
        if action=='dev_put_item':return c.put_item(TableName=r,Item=typed_item(decoded(p['item'])))
        if action=='dev_delete_item':return c.delete_item(TableName=r,Key=typed_item(decoded(p['key'])))
        if action=='dev_import_items':
            items=decoded(p['items'])
            if not isinstance(items,list) or not 1<=len(items)<=100:raise ValueError('Import 1–100 typed JSON items')
            results=[]
            for i,item in enumerate(items):
                try:
                    if not isinstance(item,dict):raise ValueError('Item must be an object')
                    c.put_item(TableName=r,Item=typed_item(item));results.append({'index':i,'status':'saved'})
                except Exception as e:results.append({'index':i,'error':str(e)})
            return {'results':results}
        if action=='dev_create_index':
            name=p['name'];partition=p['partition'];sort=p.get('sort');types=decoded(p.get('types',{}))
            keys=[{'AttributeName':partition,'KeyType':'HASH'}]
            if sort:keys.append({'AttributeName':sort,'KeyType':'RANGE'})
            definitions=[{'AttributeName':k['AttributeName'],'AttributeType':types.get(k['AttributeName'],'S')} for k in keys]
            if any(d['AttributeType'] not in {'S','N','B'} for d in definitions):raise ValueError('Key types must be S, N or B')
            spec={'IndexName':name,'KeySchema':keys,'Projection':{'ProjectionType':'ALL'}}
            table=c.describe_table(TableName=r)['Table']
            if table.get('BillingModeSummary',{}).get('BillingMode')!='PAY_PER_REQUEST':
                spec['ProvisionedThroughput']={'ReadCapacityUnits':1,'WriteCapacityUnits':1}
            return c.update_table(TableName=r,AttributeDefinitions=definitions,GlobalSecondaryIndexUpdates=[{'Create':spec}])
    if service=='secretsmanager':
        if action=='dev_secret_version':
            result=c.get_secret_value(SecretId=r,VersionId=p['version'])
            if 'SecretBinary' in result:result['SecretBinary']=base64.b64encode(result['SecretBinary']).decode()
            return result
        if action=='dev_secret_stage':
            stage=p.get('stage','AWSCURRENT');target=p['version']
            versions=configuration_operation(service,'history',{'resource':r},region,client)['Versions']
            if not any(v['VersionId']==target for v in versions):raise ValueError('Version does not belong to this secret')
            previous=next((v['VersionId'] for v in versions if stage in v.get('VersionStages',[])),None)
            if previous==target:return {'status':'already assigned'}
            args={'SecretId':r,'VersionStage':stage,'MoveToVersionId':target}
            if previous:args['RemoveFromVersionId']=previous
            return c.update_secret_version_stage(**args)
    if service=='ssm':
        if action=='dev_parameter_version':
            return c.get_parameter(Name=r+':'+str(number(p,'version',1,1,1000000000)),WithDecryption=True)
        if action=='dev_parameter_rollback':
            previous=c.get_parameter(Name=r+':'+str(number(p,'version',1,1,1000000000)),WithDecryption=True)['Parameter']
            return configuration_operation(service,'update_value',{'resource':r,'value':previous['Value']},region,client)
        if action=='dev_parameter_labels':
            labels=decoded(p['labels'])
            if not isinstance(labels,list) or not 1<=len(labels)<=10 or any(not isinstance(v,str) for v in labels):raise ValueError('Provide 1–10 labels')
            version=number(p,'version',1,1,1000000000)
            if p.get('remove'):
                try:return c.unlabel_parameter_version(Name=r,ParameterVersion=version,Labels=labels)
                except ClientError as e:
                    if 'not been implemented' in e.response.get('Error',{}).get('Message',''):
                        raise ValueError('This LocalStack version cannot remove parameter labels. Assigning or moving labels is supported.') from None
                    raise
            return c.label_parameter_version(Name=r,ParameterVersion=version,Labels=labels)
        if action=='dev_parameter_import':
            entries=decoded(p['entries'])
            if not isinstance(entries,list) or not 1<=len(entries)<=100:raise ValueError('Import 1–100 parameters')
            from configuration import create_configuration
            results=[]
            for entry in entries:
                try:
                    name=entry['name']
                    if entry.get('overwrite') is True:
                        result=configuration_operation('ssm','update_value',{'resource':name,'value':entry['value']},region,client)
                    else:result=create_configuration('ssm',entry,region,client)
                    results.append({'name':name,'status':'saved','version':result.get('Version')})
                except Exception as e:results.append({'name':entry.get('name') if isinstance(entry,dict) else None,'error':str(e)})
            return {'results':results}
        if action=='dev_environment_compare':
            # Metadata-only comparison by relative name; fetching values is a separate opt-in.
            left=p['left'].rstrip('/')+'/';right=p['right'].rstrip('/')+'/'
            entries=[]
            for page in c.get_paginator('describe_parameters').paginate():entries.extend(page.get('Parameters',[]))
            a={v['Name'][len(left):]:v for v in entries if v['Name'].startswith(left)};b={v['Name'][len(right):]:v for v in entries if v['Name'].startswith(right)}
            rows=[]
            for key in sorted(a.keys()|b.keys()):
                x,y=a.get(key),b.get(key);row={'relativeName':key,'left':x,'right':y}
                if p.get('compareValues') is True and x and y:
                    v1=c.get_parameter(Name=x['Name'],WithDecryption=True)['Parameter']['Value'];v2=c.get_parameter(Name=y['Name'],WithDecryption=True)['Parameter']['Value']
                    row['valuesEqual']=v1==v2
                rows.append(row)
            return {'Parameters':rows}
    raise ValueError('Unsupported developer operation')
