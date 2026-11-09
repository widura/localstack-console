"""Everyday operations; all clients use the console's explicit local credentials."""
import base64
import json


def operate(service, action, p, region, client):
    c = client(service, region)
    r = p.get('resource', '')
    if action == 'delete':
        operations = {'s3': ('delete_bucket', 'Bucket'), 'sqs': ('delete_queue', 'QueueUrl'),
                      'sns': ('delete_topic', 'TopicArn'), 'lambda': ('delete_function', 'FunctionName'),
                      'dynamodb': ('delete_table', 'TableName')}
        op, key = operations[service]
        return getattr(c, op)(**{key: r})
    if service == 'lambda' and action == 'invoke':
        event = p.get('event', '{}')
        json.loads(event)
        result = c.invoke(FunctionName=r, Payload=event.encode(), LogType='Tail')
        body = result.pop('Payload').read().decode('utf-8', errors='replace')
        try: result['Payload'] = json.loads(body)
        except ValueError: result['Payload'] = body
        if result.get('LogResult'):
            result['Logs'] = base64.b64decode(result.pop('LogResult')).decode('utf-8', errors='replace')
        return result
    if service == 's3':
        if action == 'object_metadata': return c.head_object(Bucket=r, Key=p['key'])
        if action == 'upload':
            return c.put_object(Bucket=r, Key=p['key'], Body=base64.b64decode(p['data'], validate=True), ContentType=p.get('contentType') or 'application/octet-stream')
        if action == 'download':
            result = c.get_object(Bucket=r, Key=p['key'])
            stream = result.get('Body')
            try:
                if result.get('ContentLength', 0) > 750000: raise ValueError('Console downloads are limited to 750 KB; use the CLI for larger files.')
                data = stream.read(750001)
                if len(data) > 750000: raise ValueError('Console downloads are limited to 750 KB; use the CLI for larger files.')
                return {'data': base64.b64encode(data).decode(), 'contentType': result.get('ContentType')}
            finally:
                if stream is not None: stream.close()
        if action == 'delete_object': return c.delete_object(Bucket=r, Key=p['key'])
    if service == 'sqs':
        if action == 'ack': return c.delete_message(QueueUrl=r, ReceiptHandle=p['receipt'])
        if action == 'visibility': return c.change_message_visibility(QueueUrl=r, ReceiptHandle=p['receipt'], VisibilityTimeout=int(p['seconds']))
        if action == 'purge': return c.purge_queue(QueueUrl=r)
    if service == 'sns':
        if action == 'subscriptions':
            return {'Subscriptions': [s for page in c.get_paginator('list_subscriptions_by_topic').paginate(TopicArn=r) for s in page['Subscriptions']]}
        if action == 'unsubscribe': return c.unsubscribe(SubscriptionArn=p['subscription'])
        if action == 'subscribe':
            sqs = client('sqs', region)
            url = p['queueUrl']
            attrs = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=['QueueArn', 'Policy'])['Attributes']
            arn = attrs['QueueArn']
            policy = json.loads(attrs.get('Policy') or '{"Version":"2012-10-17","Statement":[]}')
            statement = {'Effect':'Allow','Principal':{'Service':'sns.amazonaws.com'},'Action':'sqs:SendMessage',
                         'Resource':arn,'Condition':{'ArnEquals':{'aws:SourceArn':r}}}
            if statement not in policy['Statement']: policy['Statement'].append(statement)
            sqs.set_queue_attributes(QueueUrl=url, Attributes={'Policy':json.dumps(policy)})
            return c.subscribe(TopicArn=r, Protocol='sqs', Endpoint=arn, Attributes={'RawMessageDelivery':str(bool(p.get('raw'))).lower()})
    if service == 'dynamodb':
        if action == 'put': return c.put_item(TableName=r, Item=json.loads(p['item']))
        if action == 'delete_item': return c.delete_item(TableName=r, Key=json.loads(p['key']))
        if action == 'query':
            args = {'TableName':r, 'KeyConditionExpression':p['expression'], 'ExpressionAttributeValues':json.loads(p['values']), 'Limit':50}
            if p.get('names'): args['ExpressionAttributeNames'] = json.loads(p['names'])
            if p.get('cursor'): args['ExclusiveStartKey'] = p['cursor']
            return c.query(**args)
    raise ValueError('Unsupported operation')
