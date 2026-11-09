"""Additional development operations for the existing five services."""
import base64
import io
import json
import zipfile
from resources import number


def package_source(source, runtime):
    if not isinstance(source, str) or not source.strip():
        raise ValueError('Source code is required')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        info = zipfile.ZipInfo('index.py' if runtime.startswith('python') else 'index.js')
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, source)
    return out.getvalue()


def attributes(p):
    value = p.get('attributes') or '{}'
    attrs = json.loads(value) if isinstance(value, str) else value
    if not isinstance(attrs, dict): raise ValueError('Message attributes must be a JSON object')
    return attrs


def advanced(service, action, p, region, client):
    c = client(service, region)
    resource = p.get('resource', '')
    if service == 'lambda':
        if action == 'source':
            from urllib.parse import urlsplit
            from urllib.request import urlopen
            result = c.get_function(FunctionName=resource)
            config = result['Configuration']
            if config.get('Handler') != 'index.handler' or config.get('Runtime') not in {'python3.12','nodejs22.x'}:
                raise ValueError('The source editor supports index.handler on Python 3.12 or Node.js 22. Use ZIP upload for other layouts.')
            location = urlsplit(result['Code']['Location'])
            endpoint = urlsplit(c.meta.endpoint_url)
            with urlopen(endpoint._replace(path=location.path,query=location.query).geturl(),timeout=12) as response:
                code = response.read(750001)
            if len(code)>750000: raise ValueError('Code ZIP exceeds editor limit')
            with zipfile.ZipFile(io.BytesIO(code)) as archive:
                path = 'index.py' if config['Runtime'].startswith('python') else 'index.js'
                if archive.getinfo(path).file_size>250000: raise ValueError('Source exceeds 250 KB')
                return {'code':archive.read(path).decode()}

        if action == 'update_code':
            config = c.get_function_configuration(FunctionName=resource)
            if config.get('Handler')!='index.handler' or config.get('Runtime') not in {'python3.12','nodejs22.x'}: raise ValueError('Use ZIP upload for this runtime or handler')
            code = package_source(p['code'], config['Runtime'])
            return c.update_function_code(FunctionName=resource, ZipFile=code)
        if action == 'upload_zip':
            code = base64.b64decode(p['data'], validate=True)
            with zipfile.ZipFile(io.BytesIO(code)) as archive:
                if not archive.namelist(): raise ValueError('ZIP archive is empty')
                if sum(i.file_size for i in archive.infolist()) > 50000000: raise ValueError('Unpacked ZIP exceeds 50 MB')
            return c.update_function_code(FunctionName=resource, ZipFile=code)
        if action == 'update_config':
            args = {'FunctionName':resource}
            if p.get('timeout') not in ('', None): args['Timeout'] = number(p, 'timeout', 3, 1, 900)
            if p.get('memory') not in ('', None): args['MemorySize'] = number(p, 'memory', 128, 128, 10240)
            if p.get('handler'): args['Handler'] = p['handler']
            if p.get('runtime'): args['Runtime'] = p['runtime']
            if p.get('environment', '') != '':
                env = json.loads(p['environment'])
                if not isinstance(env, dict) or any(not isinstance(v, str) for v in env.values()):
                    raise ValueError('Environment must be a JSON object with string values')
                args['Environment'] = {'Variables':env}
            if len(args) == 1: raise ValueError('Enter at least one configuration change')
            return c.update_function_configuration(**args)
    if service == 'sqs' and action == 'send_batch':
        messages = json.loads(p['messages'])
        if not isinstance(messages, list) or not 1 <= len(messages) <= 10:
            raise ValueError('Provide a JSON array of 1–10 messages')
        entries = []
        import uuid
        for index, message in enumerate(messages):
            if isinstance(message, str): message = {'body': message}
            if not isinstance(message, dict) or not isinstance(message.get('body'), str): raise ValueError('Each message needs a string body')
            entry = {'Id':str(index), 'MessageBody':message['body'], 'MessageAttributes':attributes(message)}
            if resource.endswith('.fifo'):
                entry.update(MessageGroupId=message.get('group') or 'console', MessageDeduplicationId=uuid.uuid4().hex)
            entries.append(entry)
        return c.send_message_batch(QueueUrl=resource, Entries=entries)
    if service == 's3' and action == 'empty_bucket':
        # Delete versions and delete markers as well as unversioned objects.
        deleted = 0
        for page in c.get_paginator('list_object_versions').paginate(Bucket=resource):
            objects = [{'Key':v['Key'], 'VersionId':v['VersionId']} for v in page.get('Versions', []) + page.get('DeleteMarkers', [])]
            if objects:
                result = c.delete_objects(Bucket=resource, Delete={'Objects':objects, 'Quiet':True})
                if result.get('Errors'): raise ValueError(json.dumps(result['Errors']))
                deleted += len(objects)
        return {'deletedVersionsAndMarkers':deleted}
    raise ValueError('Unsupported operation')
