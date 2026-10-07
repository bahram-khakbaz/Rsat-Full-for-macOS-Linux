"""Run with Debian Python to test the real packaged Samba bindings offline."""
from pathlib import Path
import importlib.util
import io
import json
import unittest
from unittest.mock import patch,Mock
spec=importlib.util.spec_from_file_location('helper',str(Path(__file__).resolve().parents[1]/'app/samba_dns_rpc.py'))
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)

class SambaTests(unittest.TestCase):
    def test_bind_retries_before_any_operation(self):
        rpc=Mock()
        with patch.object(helper.dnsserver,'dnsserver',side_effect=[RuntimeError(0xc000000d),rpc]) as factory:
            self.assertIs(helper.connect('dc.example.com',None,None),rpc)
            self.assertEqual(factory.call_count,2)
            rpc.DnssrvUpdateRecord2.assert_not_called()
    def test_bind_access_denied_is_not_retried(self):
        with patch.object(helper.dnsserver,'dnsserver',side_effect=RuntimeError(5)) as factory:
            with self.assertRaises(RuntimeError):helper.connect('dc.example.com',None,None)
            self.assertEqual(factory.call_count,1)
    def test_failed_write_is_never_repeated(self):
        rpc=Mock();rpc.DnssrvUpdateRecord2.side_effect=RuntimeError(5)
        body={'host':'dc.example.com','zone':'example.com','name':'example','type':'A','value':'192.0.2.10','ttl':123,'operation':'add'}
        with patch.object(helper,'connect',return_value=rpc),patch.object(helper,'Credentials'),patch.dict(helper.os.environ,{'KRB5CCNAME':'FILE:/private/test'}),patch('sys.stdin',io.StringIO(json.dumps(body))):
            with self.assertRaises(RuntimeError):helper.main()
        rpc.DnssrvUpdateRecord2.assert_called_once()
        self.assertEqual(rpc.DnssrvUpdateRecord2.call_args.args[-2].rec.dwTtlSeconds,123)
        self.assertIsNone(rpc.DnssrvUpdateRecord2.call_args.args[-1])
    def test_read_probe_sends_no_update(self):
        rpc=Mock();body={'host':'dc.example.com','zone':'example.com','operation':'probe'}
        with patch.object(helper,'connect',return_value=rpc),patch.object(helper,'Credentials'),patch.dict(helper.os.environ,{'KRB5CCNAME':'FILE:/private/test'}),patch('sys.stdin',io.StringIO(json.dumps(body))),patch('sys.stdout',io.StringIO()):helper.main()
        rpc.DnssrvEnumRecords2.assert_called_once();rpc.DnssrvUpdateRecord2.assert_not_called()

    def test_update_replaces_only_selected_value_in_one_rpc(self):
        rpc=Mock();body={'host':'dc.example.com','zone':'example.com','name':'example','type':'A','value':'192.0.2.2','ttl':1200,'old_value':'192.0.2.1','old_ttl':0,'operation':'update'}
        with patch.object(helper,'connect',return_value=rpc),patch.object(helper,'Credentials'),patch.dict(helper.os.environ,{'KRB5CCNAME':'FILE:/private/test'}),patch('sys.stdin',io.StringIO(json.dumps(body))),patch('sys.stdout',io.StringIO()):helper.main()
        rpc.DnssrvUpdateRecord2.assert_called_once()
        args=rpc.DnssrvUpdateRecord2.call_args.args
        self.assertEqual(args[-2].rec.data,'192.0.2.2')
        self.assertEqual(args[-1].rec.data,'192.0.2.1')
        self.assertEqual(args[-2].rec.dwTtlSeconds,1200)
        self.assertEqual(args[-1].rec.dwTtlSeconds,0)

    def test_extended_record_constructors_use_real_samba_types(self):
        cases=[('NS','ns.example.com',2),('MX','10 mx.example.com',15),('SRV','1 2 443 service.example.com',33),('TXT','"text with spaces" "second segment"',16)]
        for kind,value,type_number in cases:
            with self.subTest(kind=kind):
                r=helper.record(kind,value,1200)
                self.assertEqual(r.wType,type_number)
                self.assertEqual(r.dwTtlSeconds,1200)
                buffer=helper.dnsserver.DNS_RPC_RECORD_BUF();buffer.rec=r
                self.assertEqual(buffer.rec.wType,type_number)
        txt=helper.record('TXT','"text with spaces" "second segment"',1200)
        self.assertEqual(txt.data.count,2)
        self.assertEqual([x.str for x in txt.data.str],['text with spaces','second segment'])

unittest.main()
