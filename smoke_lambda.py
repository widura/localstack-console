import time
import uuid
from app import execute, client
name='console-invoke-check-'+uuid.uuid4().hex[:8]
r='eu-west-2'
created=False
try:
    execute('lambda','create',{'name':name,'runtime':'python3.12','code':'def handler(event, context):\n    print("console invocation test")\n    return {"echo": event}\n','timeout':30},r)
    created=True
    for _ in range(90):
        state=execute('lambda','detail',{'resource':name},r)
        if state.get('State')=='Active':break
        if state.get('State')=='Failed':raise RuntimeError(state)
        time.sleep(1)
    result=execute('lambda','invoke',{'resource':name,'event':'{"hello":"local"}'},r)
    assert result['Payload']=={'echo':{'hello':'local'}},result
    assert 'console invocation test' in result['Logs']
    print('PASS: live Lambda invocation, decoded JSON response and execution logs')
finally:
    if created: execute('lambda','delete',{'resource':name},r)
