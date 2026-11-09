import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import boto3
from botocore.config import Config
from resources import create_resource
from workflows import operate
from advanced import advanced, attributes
from snapshots import export_selection, restore_step

ENDPOINT = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566').rstrip('/')
REGION = os.getenv('AWS_DEFAULT_REGION', 'eu-west-2')
# Explicit test credentials: never consult the host's AWS credentials.
def client(service, region):
    return boto3.client(service, endpoint_url=ENDPOINT, region_name=region,
        aws_access_key_id='test', aws_secret_access_key='test',
        config=Config(connect_timeout=3, read_timeout=905 if service == 'lambda' else 12, retries={'max_attempts': 0},
                      s3={'addressing_style': 'path'}))

def execute(service, action, p, region):
    if action == 'export_selection':
        return export_selection(p.get('selection'), region, client)
    if action == 'restore_step':
        return restore_step(service,p.get('operation'),p.get('params',{}),region,client)
    if action == 'cleanup':
        if p.get('confirmation') != 'DELETE': raise ValueError('Type DELETE to confirm cleanup')
        selection = p.get('selection')
        if not isinstance(selection,list) or not 1 <= len(selection) <= 50: raise ValueError('Select 1–50 resources')
        if any(x.get('service') not in {'s3','sqs','sns','lambda','dynamodb'} or not x.get('resource') for x in selection): raise ValueError('Invalid resource selection')
        results=[]
        for item in selection:
            try:
                if item['service']=='s3' and p.get('emptyBuckets'):
                    advanced('s3','empty_bucket',item,region,client)
                operate(item['service'],'delete',item,region,client)
                results.append({**item,'status':'deleted'})
            except Exception as e: results.append({**item,'error':str(e)})
        return {'results':results}
    if action in {'source','update_code','upload_zip','update_config','send_batch','empty_bucket'}:
        return advanced(service,action,p,region,client)
    if service == 'health':
        with urlopen(ENDPOINT + '/_localstack/health', timeout=4) as r:
            return json.load(r)
    if action == 'create':
        return create_resource(service, p, region, client)
    if action in {'invoke','upload','download','object_metadata','delete_object','ack','visibility','purge','subscriptions','subscribe','unsubscribe','put','delete_item','query','delete'}:
        return operate(service, action, p, region, client)
    c = client(service, region)
    if action == 'list':
        names = {'s3': ('list_buckets', 'Buckets'), 'sqs': ('list_queues', 'QueueUrls'),
                 'sns': ('list_topics', 'Topics'), 'lambda': ('list_functions', 'Functions'),
                 'dynamodb': ('list_tables', 'TableNames')}
        op, key = names[service]
        kwargs = {'MaxResults': 1000} if service == 'sqs' else {}
        if c.can_paginate(op):
            items=[]
            for page in c.get_paginator(op).paginate(**kwargs):
                items.extend(page.get(key, []))
            return {'items': items}
        return {'items': getattr(c, op)(**kwargs).get(key, [])}
    resource = p.get('resource', '')
    if service == 's3' and action == 'detail':
        return c.list_objects_v2(Bucket=resource, MaxKeys=100, Prefix=p.get('prefix', ''),
            **({'ContinuationToken': p['cursor']} if p.get('cursor') else {}))
    if service == 'sqs':
        # Keep queue requests on the configured LocalStack gateway, even if the
        # URL returned by LocalStack names a different Docker host.
        if action == 'detail': return c.get_queue_attributes(QueueUrl=resource, AttributeNames=['All'])
        if action == 'send':
            extra = {'MessageGroupId':p.get('group') or 'console', 'MessageDeduplicationId':p['dedup']} if resource.endswith('.fifo') else {}
            return c.send_message(QueueUrl=resource, MessageBody=p['body'], MessageAttributes=attributes(p), **extra)
        if action == 'receive': return c.receive_message(QueueUrl=resource, MaxNumberOfMessages=10, WaitTimeSeconds=1, VisibilityTimeout=10, MessageAttributeNames=['All'], MessageSystemAttributeNames=['All'])
    if service == 'sns' and action == 'detail': return c.get_topic_attributes(TopicArn=resource)
    if service == 'sns' and action == 'publish':
        extra = {'MessageGroupId':p.get('group') or 'console', 'MessageDeduplicationId':p['dedup']} if resource.endswith('.fifo') else {}
        return c.publish(TopicArn=resource, Message=p['body'], MessageAttributes=attributes(p), **extra)
    if service == 'lambda' and action == 'detail': return c.get_function_configuration(FunctionName=resource)
    if service == 'dynamodb' and action == 'detail': return c.describe_table(TableName=resource)
    if service == 'dynamodb' and action == 'scan':
        args = {'TableName':resource,'Limit':50}
        if p.get('cursor'): args['ExclusiveStartKey'] = p['cursor']
        if p.get('expression'):
            args['FilterExpression'] = p['expression']
            if p.get('values'): args['ExpressionAttributeValues'] = json.loads(p['values'])
            if p.get('names'): args['ExpressionAttributeNames'] = json.loads(p['names'])
        return c.scan(**args)
    raise ValueError('Unsupported operation')

class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body, content='application/json'):
        data = body.encode() if isinstance(body, str) else json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type', content)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/config': return self.reply(200, {'endpoint':ENDPOINT, 'region':REGION})
        files = {'/':('index.html','text/html; charset=utf-8'), '/app.js':('app.js','text/javascript'), '/workflows.js':('workflows.js','text/javascript'), '/advanced.js':('advanced.js','text/javascript'), '/s3.js':('s3.js','text/javascript'), '/style.css':('style.css','text/css')}
        if path not in files: return self.reply(404, {'error':'Not found'})
        name, mime = files[path]
        self.reply(200, (Path(__file__).parent/'static'/name).read_text(), mime)
    def do_POST(self):
        # Browser requests require same-origin JSON; no permissive CORS headers.
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            return self.reply(403, {'error':'Cross-origin request blocked'})
        if self.path != '/api/action' or self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            return self.reply(400, {'error':'Expected JSON API request'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size <= 0 or size > 1100000: raise ValueError('Request must be between 1 byte and 1 MB')
            p=json.loads(self.rfile.read(size))
            service=p.get('service')
            if service not in {'health','s3','sqs','sns','lambda','dynamodb'}: raise ValueError('Unsupported service')
            result=execute(service,p.get('action'),p,p.get('region') or REGION)
            self.reply(200,result)
        except Exception as e:
            response = getattr(e,'response',{})
            details = response.get('Error',{})
            message = (details.get('Code','AWS error')+': '+details.get('Message',str(e))) if details else str(e)
            self.reply(400,{'error':message,'code':details.get('Code'),'requestId':response.get('ResponseMetadata',{}).get('RequestId')})

if __name__ == '__main__':
    print('LocalStack Console: http://localhost:8080', flush=True)
    ThreadingHTTPServer((os.getenv('BIND_HOST','127.0.0.1'),8080), Handler).serve_forever()


