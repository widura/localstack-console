"""Secrets Manager and SSM Parameter Store operations for local development."""
import base64
import re

SERVICES = {'secretsmanager', 'ssm'}


def secret_value(p):
    value = p.get('value')
    if not isinstance(value, str) or not value:
        raise ValueError('A nonempty secret value is required')
    kind = p.get('valueType', 'text')
    if kind == 'binary':
        try: data = base64.b64decode(value, validate=True)
        except ValueError: raise ValueError('Binary secret values must be valid base64') from None
        if not 1 <= len(data) <= 65536: raise ValueError('Secret values are limited to 64 KB')
        return {'SecretBinary': data}
    if kind != 'text': raise ValueError('Choose text or base64 binary')
    if len(value.encode()) > 65536: raise ValueError('Secret values are limited to 64 KB')
    return {'SecretString':value}


def parameter_value(p, tier):
    value = p.get('value')
    if not isinstance(value,str) or not value: raise ValueError('A nonempty parameter value is required')
    limit = 8192 if tier == 'Advanced' else 4096
    if len(value.encode()) > limit: raise ValueError('Parameter value exceeds its tier limit ('+str(limit)+' bytes)')
    return value


def create_configuration(service, p, region, client):
    name = str(p.get('name','')).strip()
    if service == 'secretsmanager':
        if not re.fullmatch(r'[A-Za-z0-9/_+=.@-]{1,512}',name): raise ValueError('Invalid secret name (1–512 letters, digits or /_+=.@-)')
        args = {'Name':name,**secret_value(p)}
        if p.get('description'): args['Description'] = p['description']
        if p.get('kmsKeyId'): args['KmsKeyId'] = p['kmsKeyId']
        return client(service,region).create_secret(**args)
    if service == 'ssm':
        if (not re.fullmatch(r'/?[A-Za-z0-9_.\-/]{1,1011}',name) or len(name)>1011
            or '//' in name or name.endswith('/') or re.match(r'^/?(aws|ssm)',name,re.I)):
            raise ValueError('Invalid parameter name. Use a name or /hierarchical/path; aws and ssm prefixes are reserved.')
        typ = p.get('parameterType','String')
        tier = p.get('tier','Standard')
        if typ not in {'String','StringList','SecureString'}: raise ValueError('Choose String, StringList or SecureString')
        if tier not in {'Standard','Advanced'}: raise ValueError('Choose Standard or Advanced tier')
        args = {'Name':name,'Type':typ,'Tier':tier,'Value':parameter_value(p,tier),'Overwrite':False}
        if p.get('description'): args['Description'] = p['description']
        if p.get('kmsKeyId'):
            if typ != 'SecureString': raise ValueError('A KMS key applies only to SecureString parameters')
            args['KeyId'] = p['kmsKeyId']
        return client(service,region).put_parameter(**args)
    raise ValueError('Unsupported configuration service')


def parameter_metadata(c, name):
    result = c.describe_parameters(ParameterFilters=[{'Key':'Name','Option':'Equals','Values':[name]}])
    entries = result.get('Parameters',[])
    if not entries: raise ValueError('Parameter not found: '+name)
    return entries[0]


def configuration_operation(service, action, p, region, client):
    c = client(service,region)
    name = p.get('resource','')
    if service == 'secretsmanager':
        if action == 'detail': return c.describe_secret(SecretId=name)
        if action == 'reveal':
            result = c.get_secret_value(SecretId=name)
            if 'SecretBinary' in result: result['SecretBinary'] = base64.b64encode(result['SecretBinary']).decode()
            return result
        if action == 'update_value': return c.update_secret(SecretId=name,**secret_value(p))
        if action == 'history':
            versions=[]
            token=None
            while True:
                page=c.list_secret_version_ids(SecretId=name,IncludeDeprecated=True,**({'NextToken':token} if token else {}))
                versions.extend(page.get('Versions',[]))
                token=page.get('NextToken')
                if not token: break
            return {'Versions':versions}
        if action == 'delete':
            force = p.get('forceDelete',False)
            if not isinstance(force,bool): raise ValueError('forceDelete must be a boolean')
            return c.delete_secret(SecretId=name,**({'ForceDeleteWithoutRecovery':True} if force else {'RecoveryWindowInDays':7}))
        if action == 'restore_secret': return c.restore_secret(SecretId=name)
    if service == 'ssm':
        if action == 'detail': return {'Parameter':parameter_metadata(c,name)}
        if action == 'reveal': return c.get_parameter(Name=name,WithDecryption=True)
        if action == 'update_value':
            meta = parameter_metadata(c,name)
            args = {'Name':name,'Type':meta['Type'],'Value':parameter_value(p,meta.get('Tier','Standard')),'Overwrite':True}
            for key in ['Description','KeyId','AllowedPattern','Tier','DataType']:
                if meta.get(key): args[key]=meta[key]
            return c.put_parameter(**args)
        if action == 'history':
            versions=[]
            for page in c.get_paginator('get_parameter_history').paginate(Name=name,WithDecryption=False):
                versions.extend({k:v for k,v in entry.items() if k!='Value'} for entry in page.get('Parameters',[]))
            return {'Versions':versions}
        if action == 'delete': return c.delete_parameter(Name=name)
    raise ValueError('Unsupported configuration operation')
