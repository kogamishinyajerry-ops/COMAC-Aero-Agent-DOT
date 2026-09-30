import http.client
import json
import threading
from http.server import ThreadingHTTPServer
import unittest
from aerolab.server import Handler


class CadApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def request(self,method,path,body=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=60)
        c.request(method,path,body=json.dumps(body) if body is not None else None)
        r=c.getresponse(); data=r.read(); status=r.status; headers=r.headers; c.close()
        return status,data,headers

    def test_catalog_and_evaluation(self):
        status,data,_=self.request('GET','/api/cad/catalog')
        self.assertEqual(status,200)
        self.assertEqual(len(json.loads(data)['presets']),3)
        status,data,_=self.request('POST','/api/cad/evaluate',{})
        result=json.loads(data)
        self.assertEqual(status,200)
        self.assertEqual(result['cad']['verification'],'verified_brep')
        self.assertIn('<svg',result['preview_svg'])
        self.assertTrue(result['thermal']['within_model_limits'])

    def test_comparison_and_step_identity(self):
        status,data,_=self.request('POST','/api/cad/compare',{'geometry':{'fin_count':31,'fin_height_mm':32,'base_thickness_mm':5}})
        result=json.loads(data)
        self.assertEqual(status,200)
        self.assertLess(result['delta']['mass_kg'],0)
        self.assertNotEqual(result['reference']['input_hash'],result['candidate']['input_hash'])
        status,step,headers=self.request('POST','/api/cad/step',{'geometry':result['candidate']['geometry']})
        self.assertEqual(status,200)
        self.assertTrue(step.startswith(b'ISO-10303-21;'))
        self.assertEqual(headers['Content-Type'],'model/step')

    def test_linked_mission_and_invalid_geometry(self):
        status,data,_=self.request('POST','/api/run',{'scenario_id':'nominal','cad_geometry':{}})
        self.assertEqual(status,200)
        result=json.loads(data)
        self.assertEqual(result['meta']['model_kind'],'cad_controller_motor_split')
        self.assertIn('controller_temperature_c',result['trace'][0])
        for body in ({'geometry':{'fin_count':2.5}}, {'geometry':{'width_mm':40,'fin_thickness_mm':5}}, {'boundary':{'mass_flow_kg_s':float('inf')}}, {'untrusted':1}, {'geometry':{'fin_count':10**400}}, {'boundary':{'heat_w':10**400}}):
            self.assertEqual(self.request('POST','/api/cad/evaluate',body)[0],400)

    def test_no_unbounded_generic_exports(self):
        self.assertEqual(self.request('POST','/api/cad/step',{'geometry':{},'path':'/tmp/anything'})[0],400)
        self.assertEqual(self.request('GET','/cad/manifest.json')[0],404)
