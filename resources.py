"""Validated resource creation for the local console."""
import io
import json
import re
import zipfile
from botocore.exceptions import ClientError


def number(p, key, default, low, high):
    value = p.get(key, default)
    if isinstance(value, bool) or not re.fullmatch(r'\d+', str(value)):
        raise ValueError(f'{key} must be a whole number')
    value = int(value)
    if not low <= value <= high:
        raise ValueError(f'{key} must be between {low} and {high}')
    return value


def create_resource(service, p, region, client):
    name = str(p.get('name', '')).strip()
    if not name:
        raise ValueError('Resource name is required')
    c = client(service, region)
    if service == 's3':
        if (not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', name)
            or '..' in name or '.-' in name or '-.' in name
            or re.fullmatch(r'\d+\.\d+\.\d+\.\d+', name)
            or name.startswith(('xn--', 'sthree-', 'amzn-s3-demo-'))
            or name.endswith(('-s3alias', '--ol-s3', '.mrap', '--x-s3', '--table-s3'))):
            raise ValueError('Use a valid S3 bucket name: 3–63 lowercase letters, digits, dots or hyphens; no IP addresses or reserved names.')
        return c.create_bucket(Bucket=name, **({'CreateBucketConfiguration':
            {'LocationConstraint': region}} if region != 'us-east-1' else {}))
    if service in ('sqs', 'sns'):
        fifo = p.get('fifo', name.endswith('.fifo'))
        if not isinstance(fifo, bool): raise ValueError('fifo must be a boolean')
        if fifo and not name.endswith('.fifo'): name += '.fifo'
        if not fifo and name.endswith('.fifo'): raise ValueError('Choose FIFO for a .fifo resource')
        base = name[:-5] if fifo else name
        if not re.fullmatch(r'[A-Za-z0-9_-]+', base) or len(name) > (80 if service == 'sqs' else 256):
            raise ValueError('Invalid name: use letters, digits, underscores and hyphens within the service name limit.')
        attrs = {}
        if fifo:
            attrs['FifoQueue' if service == 'sqs' else 'FifoTopic'] = 'true'
            dedup = p.get('contentDedup', False)
            if not isinstance(dedup, bool): raise ValueError('contentDedup must be a boolean')
            attrs['ContentBasedDeduplication'] = str(dedup).lower()
        if service == 'sqs':
            attrs.update(VisibilityTimeout=str(number(p,'visibility',30,0,43200)),
                         DelaySeconds=str(number(p,'delay',0,0,900)),
                         MessageRetentionPeriod=str(number(p,'retention',345600,60,1209600)))
            return c.create_queue(QueueName=name, Attributes=attrs)
        if p.get('displayName'): attrs['DisplayName'] = str(p['displayName'])
        return c.create_topic(Name=name, Attributes=attrs)
    if service == 'dynamodb':
        if not re.fullmatch(r'[A-Za-z0-9_.-]{3,255}', name):
            raise ValueError('Table names need 3–255 letters, digits, underscores, hyphens or dots.')
        partition = str(p.get('partitionKey', '')).strip()
        sort = str(p.get('sortKey', '')).strip()
        if not partition or len(partition.encode()) > 255 or len(sort.encode()) > 255:
            raise ValueError('Provide a partition key; key names must be at most 255 bytes.')
        if sort == partition: raise ValueError('Partition and sort keys must differ')
        schema, definitions = [], []
        for key, kind, typ in [(partition,'HASH',p.get('partitionType','S')), (sort,'RANGE',p.get('sortType','S'))]:
            if not key: continue
            if typ not in ('S','N','B'): raise ValueError('Key type must be S, N or B')
            schema.append({'AttributeName':key,'KeyType':kind})
            definitions.append({'AttributeName':key,'AttributeType':typ})
        return c.create_table(TableName=name,KeySchema=schema,AttributeDefinitions=definitions,BillingMode='PAY_PER_REQUEST')
    if service == 'lambda':
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name): raise ValueError('Invalid function name (1–64 letters, digits, underscores or hyphens).')
        runtime = p.get('runtime','python3.12')
        if runtime not in ('python3.12','nodejs22.x'): raise ValueError('Choose Python 3.12 or Node.js 22')
        source = p.get('code','')
        if not isinstance(source,str) or not source.strip() or len(source.encode()) > 250000:
            raise ValueError('Provide source code of up to 250 KB')
        timeout = number(p,'timeout',3,1,900)
        memory = number(p,'memory',128,128,10240)
        role = str(p.get('role','')).strip()
        if role and not re.fullmatch(r'arn:aws:iam::\d{12}:role/[A-Za-z0-9_+=,.@/\-]+',role):
            raise ValueError('Provide a valid IAM role ARN or leave blank to use the console role.')
        archive = io.BytesIO()
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            entry = zipfile.ZipInfo('index.py' if runtime.startswith('python') else 'index.js')
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(entry, source)
        if not role:
            iam = client('iam',region)
            try:
                role = iam.get_role(RoleName='localstack-console-lambda')['Role']['Arn']
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchEntity': raise
                trust = {'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'lambda.amazonaws.com'},'Action':'sts:AssumeRole'}]}
                try:
                    role = iam.create_role(RoleName='localstack-console-lambda',AssumeRolePolicyDocument=json.dumps(trust))['Role']['Arn']
                except ClientError as conflict:
                    if conflict.response['Error']['Code'] != 'EntityAlreadyExists': raise
                    role = iam.get_role(RoleName='localstack-console-lambda')['Role']['Arn']
            # Dedicated console role: logging only, no blanket service permissions.
            iam.put_role_policy(RoleName='localstack-console-lambda',PolicyName='ConsoleLambdaLogs',PolicyDocument=json.dumps({
                'Version':'2012-10-17','Statement':[{'Effect':'Allow','Action':['logs:CreateLogGroup','logs:CreateLogStream','logs:PutLogEvents'],'Resource':'arn:aws:logs:*:*:*'}]}))
        return c.create_function(FunctionName=name,Runtime=runtime,Role=role,Handler='index.handler',
            Code={'ZipFile':archive.getvalue()},Timeout=timeout,MemorySize=memory,Architectures=['x86_64'])
    raise ValueError('Resource creation is not supported for this service')

