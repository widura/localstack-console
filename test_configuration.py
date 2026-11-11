import base64
import unittest
from unittest.mock import Mock, patch
from configuration import create_configuration, configuration_operation
from snapshots import export_selection, export_resource, restore_step
import app


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.c=Mock();self.factory=Mock(return_value=self.c)
    def op(self,service,action,**params):
        return configuration_operation(service,action,{'resource':'/dev/example',**params},'eu-west-2',self.factory)

    def test_create_text_and_binary_secret(self):
        create_configuration('secretsmanager',{'name':'dev/example','value':'{"test":true}','description':'dev'},'r',self.factory)
        self.c.create_secret.assert_called_once_with(Name='dev/example',SecretString='{"test":true}',Description='dev')
        create_configuration('secretsmanager',{'name':'binary','valueType':'binary','value':base64.b64encode(b'\x00\xff').decode()},'r',self.factory)
        self.assertEqual(self.c.create_secret.call_args.kwargs['SecretBinary'],b'\x00\xff')

    def test_invalid_inputs_do_not_mutate(self):
        for service,p in [('ssm',{'name':'aws/reserved','value':'x'}),('ssm',{'name':'/dev/a','value':'x','parameterType':'Invalid'}),('ssm',{'name':'/dev/a','value':'x'*4097}),('ssm',{'name':'/dev/a','value':'x','kmsKeyId':'key'}),('secretsmanager',{'name':'bad name','value':'x'}),('secretsmanager',{'name':'good','valueType':'binary','value':'!invalid!'}),('secretsmanager',{'name':'good','value':'x'*65537})]:
            with self.subTest(service=service):
                with self.assertRaises(ValueError):create_configuration(service,p,'r',self.factory)
        self.factory.assert_not_called()

    def test_secure_parameter_create_never_overwrites(self):
        create_configuration('ssm',{'name':'/dev/token','value':'example','parameterType':'SecureString','kmsKeyId':'alias/example'},'r',self.factory)
        self.c.put_parameter.assert_called_once_with(Name='/dev/token',Value='example',Type='SecureString',Tier='Standard',Overwrite=False,KeyId='alias/example')

    def test_metadata_does_not_fetch_values(self):
        self.c.describe_parameters.return_value={'Parameters':[{'Name':'/dev/example','Type':'SecureString'}]}
        self.op('ssm','detail');self.op('secretsmanager','detail')
        self.c.get_parameter.assert_not_called();self.c.get_secret_value.assert_not_called()

    def test_reveal_decrypts_and_binary_is_base64(self):
        self.op('ssm','reveal')
        self.c.get_parameter.assert_called_once_with(Name='/dev/example',WithDecryption=True)
        self.c.get_secret_value.return_value={'SecretBinary':b'\x00\xff'}
        self.assertEqual(self.op('secretsmanager','reveal')['SecretBinary'],'AP8=')

    def test_parameter_update_preserves_encryption_and_tier(self):
        self.c.describe_parameters.return_value={'Parameters':[{'Name':'/dev/example','Type':'SecureString','Tier':'Advanced','KeyId':'alias/dev','Description':'keep','AllowedPattern':'.*','DataType':'text'}]}
        self.op('ssm','update_value',value='new')
        args=self.c.put_parameter.call_args.kwargs
        self.assertEqual(args['Type'],'SecureString');self.assertEqual(args['KeyId'],'alias/dev');self.assertEqual(args['Tier'],'Advanced');self.assertTrue(args['Overwrite']);self.assertEqual(args['Description'],'keep')

    def test_secret_update_creates_value_version(self):
        self.op('secretsmanager','update_value',value='new')
        self.c.update_secret.assert_called_once_with(SecretId='/dev/example',SecretString='new')

    def test_secret_history_follows_tokens_without_sdk_paginator(self):
        self.c.list_secret_version_ids.side_effect=[{'Versions':[{'VersionId':'one'}],'NextToken':'next'},{'Versions':[{'VersionId':'two'}]}]
        self.assertEqual(len(self.op('secretsmanager','history')['Versions']),2)
        self.c.list_secret_version_ids.assert_called_with(SecretId='/dev/example',IncludeDeprecated=True,NextToken='next')

    def test_history_excludes_parameter_values(self):
        self.c.get_paginator.return_value.paginate.return_value=[{'Parameters':[{'Version':1,'Value':'hidden'},{'Version':2,'Value':'also hidden'}]}]
        result=self.op('ssm','history')
        self.assertEqual(result,{'Versions':[{'Version':1},{'Version':2}]})
        self.c.get_paginator.return_value.paginate.assert_called_once_with(Name='/dev/example',WithDecryption=False)

    def test_secret_deletion_recovery_and_explicit_force(self):
        self.op('secretsmanager','delete')
        self.c.delete_secret.assert_called_with(SecretId='/dev/example',RecoveryWindowInDays=7)
        self.op('secretsmanager','delete',forceDelete=True)
        self.c.delete_secret.assert_called_with(SecretId='/dev/example',ForceDeleteWithoutRecovery=True)
        self.op('secretsmanager','restore_secret');self.c.restore_secret.assert_called_once_with(SecretId='/dev/example')

    def test_export_values_require_explicit_opt_in(self):
        with self.assertRaises(ValueError):export_selection([{'service':'ssm','resource':'/dev/example'}],'r',self.factory)
        self.factory.assert_not_called()

    def test_binary_export_restore(self):
        self.c.describe_secret.return_value={'Name':'binary','Description':'sample'}
        self.c.get_secret_value.return_value={'SecretBinary':b'\x00\xff'}
        result=export_resource('secretsmanager','binary','r',self.factory)
        params=result['create']['params']
        self.assertEqual(params['value'],'AP8=');self.assertEqual(params['valueType'],'binary')
        restore_step('secretsmanager','create',params,'r',self.factory)
        self.assertEqual(self.c.create_secret.call_args.kwargs['SecretBinary'],b'\x00\xff')

    def test_paginated_listing_and_scheduled_cleanup(self):
        self.c.can_paginate.return_value=True
        self.c.get_paginator.return_value.paginate.return_value=[{'SecretList':[{'Name':'first'}]},{'SecretList':[{'Name':'second'}]}]
        with patch('app.client',self.factory):
            self.assertEqual(len(app.execute('secretsmanager','list',{},'r')['items']),2)
            self.c.get_paginator.return_value.paginate.assert_called_once_with(IncludePlannedDeletion=True)
            result=app.execute('health','cleanup',{'selection':[{'service':'secretsmanager','resource':'first'}],'confirmation':'DELETE'},'r')
        self.assertEqual(result['results'][0]['status'],'scheduled for deletion')


if __name__=='__main__': unittest.main()
