"""Portable exports of selected existing resources and bounded sample data."""
import base64
import json
import time
from urllib.parse import urlsplit
from urllib.request import urlopen
from resources import create_resource
from workflows import operate
from configuration import configuration_operation, parameter_metadata

SERVICES = {'s3','sqs','sns','lambda','dynamodb','secretsmanager','ssm'}
MAX_FILE = 750000


def export_resource(service, resource, region, client):
    c = client(service, region)
    params = {'name':resource}
    steps = []
    notes = []
    if service == 's3':
        objects = c.list_objects_v2(Bucket=resource, MaxKeys=20)
        if objects.get('IsTruncated'): notes.append('Only the first 20 current objects are included.')
        budget = 3000000
        for obj in objects.get('Contents', []):
            if obj['Size'] > MAX_FILE or obj['Size'] > budget:
                notes.append('Skipped object exceeding file or 3 MB sample budget: '+obj['Key'])
                continue
            result = c.get_object(Bucket=resource, Key=obj['Key'])
            try: data = result['Body'].read(MAX_FILE+1)
            finally: result['Body'].close()
            if len(data) > MAX_FILE:
                notes.append('Skipped oversized object: '+obj['Key']); continue
            budget -= len(data)
            steps.append({'service':service,'action':'upload','params':{'resource':resource,'key':obj['Key'],'data':base64.b64encode(data).decode(),'contentType':result.get('ContentType','application/octet-stream')}})
        notes.append('S3 export includes current object samples, not versions, bucket policies or lifecycle settings.')
    elif service == 'sqs':
        attrs = c.get_queue_attributes(QueueUrl=resource, AttributeNames=['All'])['Attributes']
        params = {'name':resource.rstrip('/').split('/')[-1], 'fifo':attrs.get('FifoQueue')=='true',
                  'contentDedup':attrs.get('ContentBasedDeduplication')=='true',
                  'visibility':attrs.get('VisibilityTimeout','30'), 'delay':attrs.get('DelaySeconds','0'),
                  'retention':attrs.get('MessageRetentionPeriod','345600')}
        notes.append('Queue messages are excluded to avoid changing visibility or receive counts. Queue policies and redrive settings are not exported.')
    elif service == 'sns':
        attrs = c.get_topic_attributes(TopicArn=resource)['Attributes']
        params = {'name':resource.split(':')[-1], 'fifo':attrs.get('FifoTopic')=='true',
                  'contentDedup':attrs.get('ContentBasedDeduplication')=='true', 'displayName':attrs.get('DisplayName','')}
        for page in c.get_paginator('list_subscriptions_by_topic').paginate(TopicArn=resource):
            for sub in page['Subscriptions']:
                if sub['Protocol'] != 'sqs' or not sub['SubscriptionArn'].startswith('arn:'): continue
                sqs = client('sqs', region)
                queue = sqs.get_queue_url(QueueName=sub['Endpoint'].split(':')[-1])['QueueUrl']
                settings = c.get_subscription_attributes(SubscriptionArn=sub['SubscriptionArn'])['Attributes']
                steps.append({'service':'sns','action':'subscribe','params':{'resource':resource,'queueUrl':queue,'raw':settings.get('RawMessageDelivery')=='true'}})
        notes.append('SNS export includes SQS subscriptions and raw delivery; other subscription types, filters and topic policies are excluded.')
    elif service == 'dynamodb':
        table = c.describe_table(TableName=resource)['Table']
        types = {a['AttributeName']:a['AttributeType'] for a in table['AttributeDefinitions']}
        params = {'name':resource}
        for key in table['KeySchema']:
            prefix = 'partition' if key['KeyType']=='HASH' else 'sort'
            params[prefix+'Key'] = key['AttributeName']; params[prefix+'Type'] = types[key['AttributeName']]
        data = c.scan(TableName=resource, Limit=50)
        for item in data.get('Items', []):
            steps.append({'service':service,'action':'put','params':{'resource':resource,'item':json.dumps(item,default=lambda v:{'__binary__':base64.b64encode(v).decode()})}})
        if data.get('LastEvaluatedKey'): notes.append('Only the first scan page (50 evaluated items) is included.')
        notes.append('Tables restore with on-demand capacity; indexes, streams, TTL and table policies are excluded.')
    elif service == 'lambda':
        config = c.get_function(FunctionName=resource)
        f = config['Configuration']
        location = config['Code'].get('Location')
        if not location: raise ValueError('Only ZIP-based Lambda functions can be exported')
        # Fetch code from the configured local gateway, never from an arbitrary code URL.
        endpoint = urlsplit(c.meta.endpoint_url)
        source = urlsplit(location)
        local_url = endpoint._replace(path=source.path, query=source.query).geturl()
        with urlopen(local_url, timeout=12) as response: code = response.read(MAX_FILE+1)
        if len(code) > MAX_FILE: raise ValueError('Lambda ZIP exceeds the 750 KB export limit')
        params = {'name':f['FunctionName'],'runtime':f['Runtime'],'code':'def handler(event, context):\n    return event\n' if f['Runtime'].startswith('python') else 'exports.handler = async event => event;','timeout':f['Timeout'],'memory':f['MemorySize']}
        steps.extend([
            {'service':service,'action':'upload_zip','params':{'resource':resource,'data':base64.b64encode(code).decode()}},
            {'service':service,'action':'update_config','params':{'resource':resource,'handler':f['Handler'],'environment':json.dumps(f.get('Environment',{}).get('Variables',{}))}}
        ])
        notes.append('Lambda restore uses the console execution role. Layers, triggers, versions, aliases and custom permissions are excluded.')
    elif service == 'secretsmanager':
        meta = c.describe_secret(SecretId=resource)
        value = configuration_operation(service,'reveal',{'resource':resource},region,client)
        binary = 'SecretBinary' in value
        params = {'name':meta['Name'],'value':value['SecretBinary' if binary else 'SecretString'],
                  'valueType':'binary' if binary else 'text','description':meta.get('Description','')}
        if meta.get('KmsKeyId'): params['kmsKeyId'] = meta['KmsKeyId']
        notes.append('Contains the current secret value in plaintext/base64. Versions, rotation, tags and resource policies are excluded; custom KMS keys must already exist.')
    elif service == 'ssm':
        meta = parameter_metadata(c,resource)
        value = c.get_parameter(Name=resource,WithDecryption=True)['Parameter']
        params = {'name':resource,'value':value['Value'],'parameterType':meta['Type'],
                  'tier':meta.get('Tier','Standard'),'description':meta.get('Description','')}
        if meta['Type']=='SecureString' and meta.get('KeyId'): params['kmsKeyId']=meta['KeyId']
        notes.append('Contains the current parameter value in plaintext, including SecureString. History, labels, policies, tags and validation patterns are excluded; custom KMS keys must already exist.')
    else: raise ValueError('Unsupported export service')
    return {'create':{'service':service,'action':'create','params':params},'steps':steps,'notes':notes}


def export_selection(selection, region, client, include_sensitive=False):
    if not isinstance(selection,list) or not 1 <= len(selection) <= 50: raise ValueError('Select 1–50 resources')
    if not include_sensitive and any(item.get('service') in {'secretsmanager','ssm'} for item in selection):
        raise ValueError('Confirm inclusion of secret and parameter values before exporting')
    creates, data, subscriptions, notes = [], [], [], []
    for item in selection:
        if item.get('service') not in SERVICES or not item.get('resource'): raise ValueError('Invalid resource selection')
        result = export_resource(item['service'],item['resource'],region,client)
        creates.append(result['create'])
        for step in result['steps']:
            (subscriptions if step['action']=='subscribe' else data).append(step)
        notes.extend(item['resource']+': '+note for note in result['notes'])
    steps = creates+data+subscriptions
    for step in steps: step['params']['region'] = region
    result = {'version':2,'steps':steps,'notes':notes,'sourceRegion':region}
    if len(json.dumps(result).encode()) > 9000000: raise ValueError('Export exceeds 9 MB; select fewer resources or smaller samples')
    return result


def restore_step(service, action, p, region, client):
    """Wait for asynchronous resources before the next replay step."""
    from advanced import advanced
    if service not in SERVICES or action not in {'create','upload','put','subscribe','upload_zip','update_config','update_code'}:
        raise ValueError('Unsupported restore step')
    if service in {'lambda','dynamodb'} and action != 'create':
        wait_ready(service,p['resource'],region,client)
    if action == 'create':
        result = create_resource(service,p,region,client)
        if service in {'lambda','dynamodb'}: wait_ready(service,p['name'],region,client)
        return result
    if action in {'upload_zip','update_config','update_code'}:
        result = advanced(service,action,p,region,client)
        wait_ready(service,p['resource'],region,client)
        return result
    if service=='dynamodb' and action=='put':
        p = dict(p)
        p['item'] = json.loads(p['item'],object_hook=lambda d:base64.b64decode(d['__binary__']) if set(d)=={'__binary__'} else d)
        return client(service,region).put_item(TableName=p['resource'],Item=p['item'])
    return operate(service,action,p,region,client)


def wait_ready(service, resource, region, client):
    c = client(service,region)
    for _ in range(90):
        data = c.get_function_configuration(FunctionName=resource) if service=='lambda' else c.describe_table(TableName=resource)['Table']
        if service=='lambda':
            if data.get('State')=='Failed' or data.get('LastUpdateStatus')=='Failed': raise ValueError('Lambda creation/update failed: '+str(data))
            ready = data.get('State')=='Active' and data.get('LastUpdateStatus')!='InProgress'
        else: ready = data.get('TableStatus')=='ACTIVE'
        if ready: return
        time.sleep(1)
    raise ValueError('Resource is still pending; refresh before retrying: '+resource)
