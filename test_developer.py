import base64
import io
import unittest
from unittest.mock import Mock
from botocore.exceptions import ClientError
from developer import developer, typed_item
from transfers import LimitedInput, upload, MAX_UPLOAD


class DeveloperTests(unittest.TestCase):
    def setUp(self):
        self.c=Mock();self.factory=Mock(return_value=self.c)

    def op(self,service,action,**p):
        return developer(service,action,{'resource':'resource',**p},'eu-west-2',self.factory)

    def test_folder_listing_keeps_prefix_cursor(self):
        self.op('s3','dev_folders',prefix='docs/',cursor='next')
        self.c.list_objects_v2.assert_called_once_with(Bucket='resource',Prefix='docs/',Delimiter='/',MaxKeys=100,ContinuationToken='next')

    def test_text_edit_rejects_stale_etag(self):
        self.c.head_object.return_value={'ETag':'new'}
        with self.assertRaises(ValueError):self.op('s3','dev_save_text',key='a',text='changed',etag='old')
        self.c.put_object.assert_not_called()

    def test_json_validation_before_write(self):
        with self.assertRaises(ValueError):self.op('s3','dev_save_text',key='a',text='{',json=True)
        self.c.put_object.assert_not_called()

    def test_version_restoration_uses_version_id(self):
        self.c.head_object.return_value={'Metadata':{'origin':'test'}}
        self.op('s3','dev_restore_object',key='a /b',version='v1')
        self.c.copy_object.assert_called_once_with(Bucket='resource',Key='a /b',CopySource={'Bucket':'resource','Key':'a /b','VersionId':'v1'},MetadataDirective='REPLACE',Metadata={'origin':'test'})

    def test_dlq_cannot_point_to_itself(self):
        with self.assertRaises(ValueError):self.op('sqs','dev_set_dlq',queue='resource')
        self.c.set_queue_attributes.assert_not_called()

    def test_queue_settings_validate_before_write(self):
        with self.assertRaises(ValueError):self.op('sqs','dev_queue_settings',settings={'VisibilityTimeout':43201})
        self.c.set_queue_attributes.assert_not_called()

    def test_subscription_ownership_check(self):
        self.c.get_subscription_attributes.return_value={'Attributes':{'TopicArn':'other'}}
        with self.assertRaises(ValueError):self.op('sns','dev_subscription_settings',subscription='arn',filter='{}')
        self.c.set_subscription_attributes.assert_not_called()

    def test_invocation_decodes_error_and_timing(self):
        body=io.BytesIO(b'{"errorMessage":"boom"}')
        self.c.invoke.return_value={'Payload':body,'FunctionError':'Unhandled','LogResult':base64.b64encode(b'REPORT RequestId: test Duration: 12.5 ms Billed Duration: 13 ms').decode()}
        result=self.op('lambda','dev_invoke',event='{}')
        self.assertEqual(result['ExecutionDurationMs'],12.5);self.assertEqual(result['Payload']['errorMessage'],'boom');self.assertTrue(body.closed)

    def test_mapping_ownership_prevents_cross_function_changes(self):
        self.c.get_event_source_mapping.return_value={'FunctionArn':'arn:aws:lambda:eu-west-2:000000000000:function:other'}
        self.c.get_function_configuration.return_value={'FunctionArn':'arn:aws:lambda:eu-west-2:000000000000:function:resource'}
        with self.assertRaises(ValueError):self.op('lambda','dev_remove_mapping',uuid='test')
        self.c.delete_event_source_mapping.assert_not_called()

    def test_conditional_attribute_update_preserves_others(self):
        self.op('dynamodb','dev_update_item',key={'id':{'S':'1'}},attribute='status',old={'S':'old'},value={'S':'new'})
        args=self.c.update_item.call_args.kwargs
        self.assertEqual(args['UpdateExpression'],'SET #field = :value');self.assertEqual(args['ConditionExpression'],'#field = :old')
        with self.assertRaises(ValueError):self.op('dynamodb','dev_update_item',key={'id':{'S':'1'}},attribute='id',old={'S':'1'},value={'S':'2'})

    def test_import_partial_failures_retain_success(self):
        self.c.put_item.side_effect=[{},ValueError('bad item'),{}]
        result=self.op('dynamodb','dev_import_items',items=[{'id':{'S':str(i)}} for i in range(3)])
        self.assertEqual([x.get('status') for x in result['results']],['saved',None,'saved'])

    def test_binary_typed_values_recursive(self):
        self.assertEqual(typed_item({'id':{'S':'1'},'map':{'M':{'blob':{'B':'AP8='}}}})['map']['M']['blob']['B'],b'\x00\xff')

    def test_secret_rollback_moves_current_label(self):
        self.c.list_secret_version_ids.return_value={'Versions':[{'VersionId':'new','VersionStages':['AWSCURRENT']},{'VersionId':'old','VersionStages':['AWSPREVIOUS']}]}
        self.op('secretsmanager','dev_secret_stage',version='old')
        self.c.update_secret_version_stage.assert_called_once_with(SecretId='resource',VersionStage='AWSCURRENT',MoveToVersionId='old',RemoveFromVersionId='new')

    def test_environment_compare_no_values_without_optin(self):
        self.c.get_paginator.return_value.paginate.return_value=[{'Parameters':[{'Name':'/app/dev/key','Type':'SecureString'},{'Name':'/app/test/key','Type':'SecureString'}]}]
        result=self.op('ssm','dev_environment_compare',left='/app/dev',right='/app/test')
        self.assertEqual(result['Parameters'][0]['relativeName'],'key');self.c.get_parameter.assert_not_called()

    def test_unsupported_label_removal_is_explained(self):
        self.c.unlabel_parameter_version.side_effect=ClientError({'Error':{'Code':'InternalFailure','Message':'The unlabel_parameter_version action has not been implemented'}},'UnlabelParameterVersion')
        with self.assertRaisesRegex(ValueError,'cannot remove parameter labels'):
            self.op('ssm','dev_parameter_labels',version=1,labels=['stable'],remove=True)

    def test_limited_input_does_not_consume_next_request(self):
        stream=io.BytesIO(b'abcdefNEXT');reader=LimitedInput(stream,6)
        self.assertEqual(reader.read(0),b'');self.assertEqual(reader.read(100),b'abcdef');self.assertEqual(reader.read(),b'');self.assertEqual(stream.read(),b'NEXT')

    def test_truncated_stream_raises(self):
        reader=LimitedInput(io.BytesIO(b'a'),2);reader.read()
        with self.assertRaises(ValueError):reader.read()

    def test_stream_upload_rejects_oversized_before_sdk(self):
        handler=Mock();handler.path='/api/s3/object?bucket=b&key=k';handler.headers={'Content-Length':str(MAX_UPLOAD+1)}
        with self.assertRaises(ValueError):upload(handler,self.factory)
        self.factory.assert_not_called()


if __name__=='__main__':unittest.main()
