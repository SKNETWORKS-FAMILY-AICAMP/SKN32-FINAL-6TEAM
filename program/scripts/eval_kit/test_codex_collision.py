from pathlib import Path
import importlib.util,json,subprocess,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('percall',ROOT/'codex_percall.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
SCHEMA={'type':'object','properties':{'answer':{'type':'string'}}}
class CollisionRegression(unittest.TestCase):
    def test_requests_get_distinct_files_when_clock_does_not_advance(self):
        # Low clock resolution is legal; no real CLI or network is called.
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            seen=[]
            def failed_run(args,**kwargs):
                seen.append((args[args.index('--output-schema')+1],args[args.index('-o')+1],kwargs['stdin'].name))
                return subprocess.CompletedProcess(args,1,b'',b'controlled failure')
            with patch.object(mod.time,'time_ns',return_value=123),patch.object(mod.subprocess,'run',side_effect=failed_run):
                for text in ('first trip question','second trip question'):
                    result=mod.call('test-model',text,SCHEMA,work=work,retries=0)
                    self.assertIsNone(result[0])
            self.assertEqual(len(set(path for group in seen for path in group)),6,
                             'independent requests reused schema/output/prompt files at the same clock tick')
    def test_success_keeps_output_schema_and_cleans_owned_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            def successful_run(args,**kwargs):
                schema=json.loads(Path(args[args.index('--output-schema')+1]).read_text(encoding='utf8'))
                self.assertFalse(schema['additionalProperties'])
                self.assertEqual(schema['required'],['answer'])
                self.assertEqual(kwargs['stdin'].read(),b'Seoul trip')
                Path(args[args.index('-o')+1]).write_text('{"answer":"Seoul"}',encoding='utf8')
                return subprocess.CompletedProcess(args,0,b'',b'')
            with patch.object(mod.subprocess,'run',side_effect=successful_run):
                result=mod.call('test-model','Seoul trip',SCHEMA,work=work,retries=0)
            self.assertEqual(result[0],{'answer':'Seoul'});self.assertIsNone(result[2])
            self.assertEqual(list(Path(work).iterdir()),[])
    def test_timeout_retries_same_owned_request_files_and_reports_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            paths=[]
            def timed_out(args,**kwargs):
                paths.append(args[args.index('-o')+1])
                raise subprocess.TimeoutExpired(args,kwargs['timeout'])
            with patch.object(mod.subprocess,'run',side_effect=timed_out):
                result=mod.call('test-model','Seoul',SCHEMA,work=work,retries=1)
            self.assertEqual(len(paths),2);self.assertEqual(paths[0],paths[1]);self.assertEqual(result[2],'timeout')
    def test_parallel_requests_never_share_artifact_paths(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            barrier=threading.Barrier(8);seen=[];lock=threading.Lock()
            def failed_run(args,**kwargs):
                with lock:seen.append(args[args.index('-o')+1])
                barrier.wait(timeout=5)
                return subprocess.CompletedProcess(args,1,b'',b'controlled failure')
            with patch.object(mod.time,'time_ns',return_value=123),patch.object(mod.subprocess,'run',side_effect=failed_run):
                with ThreadPoolExecutor(max_workers=8) as pool:
                    results=list(pool.map(lambda i:mod.call('test-model',str(i),SCHEMA,work=work,retries=0),range(8)))
            self.assertEqual(len(set(seen)),8);self.assertTrue(all(r[0] is None for r in results))
if __name__=='__main__':unittest.main(verbosity=2)
