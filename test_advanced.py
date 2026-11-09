import base64
import io
import json
import unittest
import zipfile
from unittest.mock import Mock, patch
from advanced import advanced, package_source
from snapshots import export_selection, export_resource, restore_step
import app


class AdvancedTests(unittest.TestCase):
    def setUp(self):
        self.c=Mock();self.factory=Mock(return_value=self.c)

    def test_config_validates_before_update(self):
        with self.assertRaises(ValueError): advanced('lambda','update_config',{'resource':'f','environment':'{"X":4}'},'r',self.factory)
        self.c.update_function_configuration.assert_not_called()
        advanced('lambda','update_config',{'resource':'f','environment':'{}','memory':'256'},'r',self.factory)
        self.c.update_function_configuration.assert_called_once_with(FunctionName='f',MemorySize=256,Environment={'Variables':{}})

    def test_source_zip_permissions(self):
        with zipfile.ZipFile(io.BytesIO(package_source('print(1)','python3.12'))) as z:
            self.assertEqual(z.read('index.py'),b'print(1)')
            self.assertEqual((z.getinfo('index.py').external_attr>>16)&0o777,0o644)

    def test_zip_rejects_invalid_archive(self):
        with self.assertRaises(zipfile.BadZipFile): advanced('lambda','upload_zip',{'resource':'f','data':base64.b64encode(b'bad').decode()},'r',self.factory)
        self.c.update_function_code.assert_not_called()

    def test_batch_validates_all_entries_before_send(self):
        with self.assertRaises(ValueError): advanced('sqs','send_batch',{'resource':'q','messages':'["valid", 5]'},'r',self.factory)
        self.c.send_message_batch.assert_not_called()
        advanced('sqs','send_batch',{'resource':'q.fifo','messages':'[{"body":"one","attributes":{"kind":{"DataType":"String","StringValue":"test"}}},"two"]'},'r',self.factory)
        entries=self.c.send_message_batch.call_args.kwargs['Entries']
        self.assertEqual(entries[0]['MessageAttributes']['kind']['StringValue'],'test')
        self.assertNotEqual(entries[0]['MessageDeduplicationId'],entries[1]['MessageDeduplicationId'])

    def test_empty_bucket_includes_delete_markers(self):
        self.c.get_paginator.return_value.paginate.return_value=[{'Versions':[{'Key':'a','VersionId':'1'}],'DeleteMarkers':[{'Key':'b','VersionId':'2'}]}]
        self.c.delete_objects.return_value={}
        result=advanced('s3','empty_bucket',{'resource':'bucket'},'r',self.factory)
        self.assertEqual(result['deletedVersionsAndMarkers'],2)
        self.assertEqual(len(self.c.delete_objects.call_args.kwargs['Delete']['Objects']),2)

    def test_cleanup_requires_confirmation_and_prevalidates_selection(self):
        with patch('app.client') as factory:
            with self.assertRaises(ValueError): app.execute('health','cleanup',{'selection':[{'service':'s3','resource':'b'}]},'r')
            with self.assertRaises(ValueError): app.execute('health','cleanup',{'confirmation':'DELETE','selection':[{'service':'s3','resource':'b'},{'service':'iam','resource':'r'}]},'r')
            factory.assert_not_called()

    def test_cleanup_reports_partial_failure(self):
        with patch('app.operate',side_effect=[{},ValueError('not empty')]):
            result=app.execute('health','cleanup',{'confirmation':'DELETE','selection':[{'service':'sqs','resource':'q'},{'service':'s3','resource':'b'}]},'r')
            self.assertEqual(result['results'][0]['status'],'deleted')
            self.assertEqual(result['results'][1]['error'],'not empty')

    def test_scan_filter_and_cursor(self):
        with patch('app.client',return_value=self.c):
            app.execute('dynamodb','scan',{'resource':'t','expression':'#s=:s','names':'{"#s":"status"}','values':'{":s":{"S":"ok"}}','cursor':{'id':{'S':'1'}}},'r')
        args=self.c.scan.call_args.kwargs
        self.assertEqual(args['FilterExpression'],'#s=:s')
        self.assertEqual(args['ExclusiveStartKey'],{'id':{'S':'1'}})

    def test_queue_export_never_receives_messages(self):
        self.c.get_queue_attributes.return_value={'Attributes':{'VisibilityTimeout':'20'}}
        data=export_resource('sqs','http://localhost/000000000000/myqueue','r',self.factory)
        self.assertEqual(data['create']['params']['name'],'myqueue')
        self.c.receive_message.assert_not_called()

    def test_export_orders_all_creates_before_sample_data(self):
        with patch('snapshots.export_resource',side_effect=[{'create':{'service':'s3','action':'create','params':{'name':'b'}},'steps':[{'service':'s3','action':'upload','params':{}}],'notes':[]},{'create':{'service':'sqs','action':'create','params':{'name':'q'}},'steps':[],'notes':[]}]):
            data=export_selection([{'service':'s3','resource':'b'},{'service':'sqs','resource':'q'}],'r',self.factory)
        self.assertEqual([s['action'] for s in data['steps']],['create','create','upload'])
        self.assertEqual(data['version'],2)

    def test_restore_rejects_delete(self):
        with self.assertRaises(ValueError): restore_step('s3','delete',{'resource':'b'},'r',self.factory)
        self.factory.assert_not_called()

    def test_binary_item_restore(self):
        self.c.describe_table.return_value={'Table':{'TableStatus':'ACTIVE'}}
        item={'id':{'S':'one'},'data':{'B':{'__binary__':base64.b64encode(b'\x00\xff').decode()}}}
        restore_step('dynamodb','put',{'resource':'t','item':json.dumps(item)},'r',self.factory)
        self.assertEqual(self.c.put_item.call_args.kwargs['Item']['data']['B'],b'\x00\xff')


if __name__=='__main__': unittest.main()
