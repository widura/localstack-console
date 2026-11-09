import base64
import io
import json
import unittest
from unittest.mock import Mock
from workflows import operate


class WorkflowsTest(unittest.TestCase):
    def setUp(self):
        self.c = Mock()
        self.factory = Mock(return_value=self.c)

    def run_action(self, service, action, **params):
        return operate(service, action, {'resource':'example', **params}, 'eu-west-2', self.factory)

    def test_invoke_decodes_payload_and_logs(self):
        self.c.invoke.return_value = {'Payload':io.BytesIO(b'{"ok":true}'), 'LogResult':base64.b64encode(b'hello').decode()}
        result = self.run_action('lambda','invoke',event='{}')
        self.assertEqual(result['Payload'], {'ok':True})
        self.assertEqual(result['Logs'], 'hello')
        self.c.invoke.assert_called_once_with(FunctionName='example',Payload=b'{}',LogType='Tail')

    def test_invalid_event_does_not_invoke(self):
        with self.assertRaises(ValueError): self.run_action('lambda','invoke',event='{')
        self.c.invoke.assert_not_called()

    def test_binary_file_roundtrip(self):
        content=b'\x00\xffabc'
        self.run_action('s3','upload',key='a.bin',data=base64.b64encode(content).decode())
        self.assertEqual(self.c.put_object.call_args.kwargs['Body'],content)
        self.c.get_object.return_value={'Body':io.BytesIO(content),'ContentLength':len(content)}
        self.assertEqual(base64.b64decode(self.run_action('s3','download',key='a.bin')['data']),content)

    def test_download_limit(self):
        self.c.get_object.return_value={'ContentLength':750001}
        with self.assertRaises(ValueError): self.run_action('s3','download',key='large')

    def test_download_closes_stream_and_checks_actual_size(self):
        stream=io.BytesIO(b'x'*750001)
        self.c.get_object.return_value={'Body':stream,'ContentLength':0}
        with self.assertRaises(ValueError): self.run_action('s3','download',key='large')
        self.assertTrue(stream.closed)

    def test_object_metadata_uses_selected_key(self):
        self.run_action('s3','object_metadata',key='folder/file.json')
        self.c.head_object.assert_called_once_with(Bucket='example',Key='folder/file.json')

    def test_ack_uses_receipt_not_message_id(self):
        self.run_action('sqs','ack',receipt='receipt-token')
        self.c.delete_message.assert_called_once_with(QueueUrl='example',ReceiptHandle='receipt-token')

    def test_put_and_delete_preserve_typed_keys(self):
        item={'id':{'S':'one'},'count':{'N':'2'}}
        self.run_action('dynamodb','put',item=json.dumps(item))
        self.c.put_item.assert_called_once_with(TableName='example',Item=item)
        self.run_action('dynamodb','delete_item',key='{"id":{"S":"one"}}')
        self.c.delete_item.assert_called_once_with(TableName='example',Key={'id':{'S':'one'}})

    def test_query_cursor_and_aliases(self):
        self.run_action('dynamodb','query',expression='#id = :id',names='{"#id":"id"}',values='{":id":{"S":"one"}}',cursor={'id':{'S':'one'}})
        args=self.c.query.call_args.kwargs
        self.assertEqual(args['ExclusiveStartKey'],{'id':{'S':'one'}})
        self.assertEqual(args['ExpressionAttributeNames'],{'#id':'id'})

    def test_subscription_preserves_existing_policy(self):
        prior={'Effect':'Allow','Action':'sqs:GetQueueAttributes','Resource':'queue','Principal':{'AWS':'owner'}}
        self.c.get_queue_attributes.return_value={'Attributes':{'QueueArn':'queue','Policy':json.dumps({'Version':'2012-10-17','Statement':[prior]})}}
        self.run_action('sns','subscribe',queueUrl='url',raw=True)
        statements=json.loads(self.c.set_queue_attributes.call_args.kwargs['Attributes']['Policy'])['Statement']
        self.assertEqual(statements[0],prior)
        self.assertEqual(statements[1]['Condition'],{'ArnEquals':{'aws:SourceArn':'example'}})
        self.c.subscribe.assert_called_once_with(TopicArn='example',Protocol='sqs',Endpoint='queue',Attributes={'RawMessageDelivery':'true'})


if __name__=='__main__': unittest.main()
