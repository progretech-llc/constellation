import importlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_discovery import discover, memory_bindings
from memory_discovery import discover_memory
from source_controls import save_agent_controls, save_memory_node


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root, self.memory_root = self.base/'Projects', self.base/'Hindsight'
        self.root.mkdir(); self.memory_root.mkdir()
        self.memory = self.base/'memory'
        self.memory.mkdir()
        self.file = self.root/'example.py'
        self.file.write_text('example')
        self.path = self.base/'sources.json'
        self.data = {'memory': {'provider': 'json', 'directory': str(self.memory)},
                     'roots': [{'label':'Projects','path':str(self.root)},
                               {'label':'Hindsight','path':str(self.memory_root)}],
                     'agents':['lead','worker'], 'future_setting':{'preserve':True}}
        self.path.write_text(json.dumps(self.data))
        self.env = patch.dict(os.environ, {'CONSTELLATION_CONFIG':str(self.path)})
        self.env.start(); self.addCleanup(self.env.stop)

    def scene(self, selected=None, explicit=False, provider=None):
        data = dict(self.data)
        if explicit: data['display_agents'] = selected
        if provider: data['memory_node'] = {'provider':provider, 'path':''}
        self.path.write_text(json.dumps(data))
        import config, memory_map, app, wallpaper_scene
        importlib.reload(config); importlib.reload(memory_map); importlib.reload(app)
        module = importlib.reload(wallpaper_scene)
        activity=memory_map.Activity('one','worker','Example',[f'Modified {self.file}'])
        with patch.object(module,'read_activities',return_value=[activity]):
            return module.make_scene()

    def test_hiding_agents_preserves_files_and_prevents_links(self):
        default = self.scene()
        selected = self.scene(['lead'], True)
        self.assertEqual([n['id'] for n in selected['nodes'] if n['kind']=='Agent'], ['agent:lead'])
        self.assertEqual([n['id'] for n in selected['nodes'] if n['kind']=='Remembered file'],
                         [n['id'] for n in default['nodes'] if n['kind']=='Remembered file'])
        self.assertEqual(selected['links'], [])
        self.assertEqual(selected['counts']['agents'],1)
        self.assertIn('worker',selected['available_agents'])

    def test_empty_selection_hides_every_agent_without_fallback(self):
        scene = self.scene([],True)
        self.assertEqual(scene['counts']['agents'],0)
        self.assertEqual(scene['links'],[])
        self.assertEqual(scene['agent_activity'],[])
        self.assertEqual(scene['counts']['files'],1)

    def test_native_api_backend_survives_recovered_controls_and_scene(self):
        self.data['memory'] = {'provider': 'hindsight-api', 'api_url': 'http://127.0.0.1:8888',
                               'bank_id': 'shared-activity'}
        self.data['roots'] = [self.data['roots'][0]]
        scene = self.scene(['worker'], True)
        self.assertEqual(scene['memory_source']['provider'], 'hindsight-api')
        self.assertEqual(scene['memory_source']['config_path'], str(self.path))
        self.assertEqual(scene['counts']['files'], 1)
        self.assertTrue(any(node['id'] == 'root:Hindsight' for node in scene['nodes']))
        saved = save_agent_controls(self.path, [], ['worker'])
        saved = save_memory_node(self.path, {'provider': 'qdrant', 'path': ''}, None)
        self.assertEqual(saved['memory'], self.data['memory'])
        scan = discover_memory(saved, home=self.base, which=lambda _: None,
                               run=lambda *a, **kw: SimpleNamespace(stdout='[]'))
        hindsight = next(item for item in scan['systems'] if item['provider'] == 'hindsight')
        self.assertTrue(hindsight['records_supported'])

    def test_selected_quiet_client_appears_and_null_restores_automatic(self):
        scene = self.scene(['goose-worker'],True)
        self.assertEqual([n['id'] for n in scene['nodes'] if n['kind']=='Agent'],['agent:goose-worker'])
        self.assertEqual(scene['agent_activity'][0]['targets'],[])
        restored=self.scene(None,True)
        self.assertEqual(restored['counts']['agents'],2)

    def test_selected_identity_overrides_unlisted_display_fallback(self):
        self.data['unlisted_agent']='lead'
        self.data['agents']=['lead']
        scene=self.scene(['worker'],True)
        self.assertEqual(len(scene['links']),1)
        self.assertEqual(scene['nodes'][scene['links'][0]['from']]['id'],'agent:worker')

    def test_agents_and_memory_save_preserve_backend_and_each_other(self):
        saved=save_agent_controls(self.path,['worker'],None)
        saved['max_files']=21
        self.path.write_text(json.dumps(saved))
        saved=save_memory_node(self.path,{'provider':'qdrant','path':''},None)
        self.assertEqual(saved['memory'],self.data['memory'])
        self.assertEqual(saved['display_agents'],['worker'])
        self.assertEqual(saved['max_files'],21)
        self.assertEqual(saved['future_setting'],{'preserve':True})
        with self.assertRaises(ValueError): save_agent_controls(self.path,[],None)
        original=self.path.read_bytes()
        for invalid in (['worker','worker'],['bad id'],['secret/token'],[1]):
            with self.assertRaises(ValueError): save_agent_controls(self.path,invalid,['worker'])
            self.assertEqual(self.path.read_bytes(),original)
        with self.assertRaises(ValueError):
            save_memory_node(self.path,{'provider':'unknown'},saved['memory_node'])
        self.assertEqual(self.path.read_bytes(),original)

    def test_one_memory_node_replaces_hindsight_without_backend_change(self):
        scene=self.scene(provider='qdrant')
        self.assertEqual([n['id'] for n in scene['nodes'] if n['root']=='Qdrant'],['memory-system:qdrant'])
        self.assertFalse(any(n['root']=='Hindsight' for n in scene['nodes']))
        self.assertEqual(scene['counts']['memory_planets'],0)
        self.assertEqual(scene['memory_source']['provider'],'json')
        for edge in scene['links']:
            self.assertEqual(scene['nodes'][edge['from']]['kind'],'Agent')
            self.assertEqual(scene['nodes'][edge['to']]['kind'],'Remembered file')
        restored=self.scene(provider='hindsight')
        self.assertTrue(any(n['id']=='root:Hindsight' for n in restored['nodes']))
        self.assertFalse(any(n['id'].startswith('memory-system:') for n in restored['nodes']))

    def test_memory_replacement_removes_its_files_and_remaps_links(self):
        self.file=self.memory_root/'example.py'
        self.file.write_text('example')
        scene=self.scene(provider='chroma')
        self.assertEqual(scene['counts']['files'],0)
        self.assertEqual(scene['links'],[])
        self.assertTrue(all(not a['targets'] for a in scene['agent_activity']))

    def test_default_memory_deduplicates_legacy_memory_roots(self):
        old=self.base/'MemPalace'
        old.mkdir()
        self.data['roots'].append({'label':'MemPalace','path':str(old)})
        scene=self.scene()
        roots=[n for n in scene['nodes'] if n['kind']=='Directory system' and n['root'] in ('Hindsight','MemPalace')]
        self.assertEqual([n['root'] for n in roots],['Hindsight'])
        self.assertEqual(scene['memory_source']['provider'],'json')


class DiscoveryTests(unittest.TestCase):
    def test_binding_formats_are_explicit_and_do_not_expose_config(self):
        forms=[{'mcp_servers':{'x':{'command':'/example/factory-memory-mcp','args':['--agent','worker','--project','Example'],'env':{'TOKEN':'not-output'}}}},
               {'mcp':{'x':{'command':['/example/factory-memory-mcp','--agent','worker','--project','Example']}}},
               {'extensions':{'x':{'cmd':'/example/factory-memory-mcp','args':['--agent','worker','--project','Example'],'enabled':True}}}]
        for data in forms:
            self.assertEqual(memory_bindings(data),[{'id':'worker','project':'Example'}])
            self.assertNotIn('not-output',json.dumps(memory_bindings(data)))
        self.assertEqual(memory_bindings({'mcp':{'x':{'command':['not-memory','--agent','made-up']}}}),[])
        self.assertEqual(memory_bindings({'mcp':{'x':{'command':['factory-memory-mcp','--agent','worker'],'enabled':False}}}),[])

    def test_sources_merge_same_identity_and_installed_is_not_running(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)
            path=home/'.config/opencode/opencode.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'mcp':{'factory':{'command':['/example/factory-memory-mcp','--agent','factory-worker']}}}))
            calls=[]
            def run(args,**kwargs):
                calls.append(args)
                if args[0]=='systemctl': return SimpleNamespace(stdout=json.dumps([
                    {'unit':'openclaw-gateway.service','active':'active','sub':'running'},
                    {'unit':'broken-gateway.service','active':'activating','sub':'auto-restart'}]))
                return SimpleNamespace(stdout=json.dumps([{'id':'main','name':'Rend','token':'not-output'}, {'id':'codex','identityName':'Odexi'}]))
            result=discover({'agents':['rend'],'agent_aliases':{}},home=home,run=run,
                            which=lambda name:'/bin/'+name if name in ('openclaw','opencode','goose') else None,
                            activity_reader=lambda:[SimpleNamespace(author='factory-worker')])
            ids=[item['id'] for item in result['agents']]
            self.assertEqual(ids.count('factory-worker'),1)
            self.assertIn('rend',ids)
            self.assertNotIn('main',ids)
            goose=next(item for item in result['sources'] if item['name']=='Goose')
            self.assertIn('installed',goose['status'])
            self.assertNotIn('not-output',json.dumps(result))
            self.assertTrue(all(args[0] in ('systemctl','openclaw') for args in calls))
            self.assertEqual(next(x['status'] for x in result['sources'] if x['name']=='broken-gateway.service'),'not running')

    def test_failed_sources_keep_saved_agents_and_return_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            def failure(*args,**kwargs): raise subprocess.TimeoutExpired('metadata',1)
            result=discover({'agents':['codex']},home=Path(temp),run=failure,which=lambda _:None,activity_reader=failure)
            self.assertEqual([item['id'] for item in result['agents']],['codex'])
            self.assertEqual(len(result['warnings']),2)

    def test_memory_scan_reports_metadata_only_for_other_systems(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)
            runtime=home/'hindsight'
            (runtime/'config').mkdir(parents=True)
            (runtime/'config/client.json').write_text('{}')
            cli=home/'hindsight-cli'; cli.write_text('example'); cli.chmod(0o700)
            config={'memory':{'provider':'hindsight','cli':str(cli)},'roots':[{'label':'Hindsight','path':str(runtime)}]}
            def run(*args,**kwargs):
                return SimpleNamespace(stdout=json.dumps([{'unit':'qdrant.service','active':'active','sub':'running'}]))
            result=discover_memory(config,home=home,run=run,which=lambda _:None)
            systems={item['provider']:item for item in result['systems']}
            self.assertEqual(set(systems),{'hindsight','qdrant'})
            self.assertTrue(systems['hindsight']['records_supported'])
            self.assertFalse(systems['qdrant']['records_supported'])
            self.assertEqual(systems['qdrant']['path'],'')
            self.assertEqual(config['memory']['provider'],'hindsight')

class WriteMetadataTests(unittest.TestCase):
    def test_write_targets_use_per_agent_writes_not_reads_or_other_authors(self):
        import wallpaper_scene
        files=[SimpleNamespace(path=f'/project/{i}.py',root='Project',agent_ranks={'lead':i},
                               agent_write_ranks=({'lead':i} if i%2==0 else {'other':i})) for i in range(20)]
        nodes={'id':['agent:lead','root:Project',*[f'file:{f.path}' for f in files]],
               'orbit_parent':['','',*['root:Project']*20]}
        activity=wallpaper_scene.agent_movement_metadata(files,nodes)[0]
        self.assertEqual(activity['write_targets'],[2,4,6,8,10,12,14])
        self.assertEqual(len(activity['targets']),7)
