import io
import unittest
import zipfile
from unittest.mock import Mock
from botocore.stub import Stubber, ANY
from botocore.exceptions import ClientError
import app
from resources import create_resource

class CreationTests(unittest.TestCase):
    def check_request(self, service, payload, operation, params, region='eu-west-2'):
        c=app.client(service,region)
        with Stubber(c) as stub:
            stub.add_response(operation,{},params)
            create_resource(service,payload,region,lambda *_:c)
            stub.assert_no_pending_responses()
    def test_buckets(self):
        self.check_request('s3',{'name':'test-bucket'},'create_bucket',{'Bucket':'test-bucket','CreateBucketConfiguration':{'LocationConstraint':'eu-west-2'}})
        self.check_request('s3',{'name':'test-bucket'},'create_bucket',{'Bucket':'test-bucket'},'us-east-1')
    def test_standard_queue(self):
        self.check_request('sqs',{'name':'jobs'},'create_queue',{'QueueName':'jobs','Attributes':{'VisibilityTimeout':'30','DelaySeconds':'0','MessageRetentionPeriod':'345600'}})
    def test_fifo_queue(self):
        self.check_request('sqs',{'name':'jobs','fifo':True,'contentDedup':True,'visibility':'60'},'create_queue',{'QueueName':'jobs.fifo','Attributes':{'FifoQueue':'true','ContentBasedDeduplication':'true','VisibilityTimeout':'60','DelaySeconds':'0','MessageRetentionPeriod':'345600'}})
    def test_topics(self):
        self.check_request('sns',{'name':'events','displayName':'Events'},'create_topic',{'Name':'events','Attributes':{'DisplayName':'Events'}})
        self.check_request('sns',{'name':'events.fifo','fifo':True},'create_topic',{'Name':'events.fifo','Attributes':{'FifoTopic':'true','ContentBasedDeduplication':'false'}})
    def test_table(self):
        self.check_request('dynamodb',{'name':'records','partitionKey':'id','sortKey':'timestamp','sortType':'N'},'create_table',{'TableName':'records','KeySchema':[{'AttributeName':'id','KeyType':'HASH'},{'AttributeName':'timestamp','KeyType':'RANGE'}],'AttributeDefinitions':[{'AttributeName':'id','AttributeType':'S'},{'AttributeName':'timestamp','AttributeType':'N'}],'BillingMode':'PAY_PER_REQUEST'})
    def test_lambda_zip(self):
        for runtime,filename in [('python3.12','index.py'),('nodejs22.x','index.js')]:
            client=Mock(); source='example source'
            create_resource('lambda',{'name':'hello','runtime':runtime,'code':source,'role':'arn:aws:iam::000000000000:role/existing'},'eu-west-2',lambda *_:client)
            args=client.create_function.call_args.kwargs
            self.assertEqual(args['Handler'],'index.handler')
            with zipfile.ZipFile(io.BytesIO(args['Code']['ZipFile'])) as z:
                self.assertEqual(z.namelist(),[filename]);self.assertEqual(z.read(filename).decode(),source)
                self.assertEqual((z.getinfo(filename).external_attr >> 16) & 0o777, 0o644)
        self.check_request('lambda',{'name':'hello','code':'def handler(e,c): return e','role':'arn:aws:iam::000000000000:role/existing'},'create_function',{'FunctionName':'hello','Runtime':'python3.12','Role':'arn:aws:iam::000000000000:role/existing','Handler':'index.handler','Code':{'ZipFile':ANY},'Timeout':3,'MemorySize':128,'Architectures':['x86_64']})
    def test_lambda_auto_role(self):
        iam,lam=Mock(),Mock()
        iam.get_role.side_effect=ClientError({'Error':{'Code':'NoSuchEntity','Message':'missing'}},'GetRole')
        iam.create_role.return_value={'Role':{'Arn':'arn:aws:iam::000000000000:role/localstack-console-lambda'}}
        create_resource('lambda',{'name':'hello','code':'def handler(e,c): return e'},'eu-west-2',lambda service,_:iam if service=='iam' else lam)
        iam.create_role.assert_called_once();iam.put_role_policy.assert_called_once();lam.create_function.assert_called_once()
    def test_validation_before_mutation(self):
        cases=[('s3',{'name':'INVALID'}),('sqs',{'name':'jobs','visibility':'1.5'}),('sqs',{'name':'jobs','delay':901}),('sns',{'name':'jobs.fifo','fifo':False}),('dynamodb',{'name':'records','partitionKey':'id','sortKey':'id'}),('dynamodb',{'name':'records'}),('lambda',{'name':'hello','code':'x','memory':64})]
        for service,payload in cases:
            c=Mock()
            with self.assertRaises(ValueError):create_resource(service,payload,'eu-west-2',lambda *_:c)
            self.assertEqual(c.mock_calls,[])

if __name__=='__main__':unittest.main()

