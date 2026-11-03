"""Authored package tests: run only under the root-reviewed CPU admission job."""
import concurrent.futures
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from . import api

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('_portable_solver_test_only', HERE / 'solver.py')
solver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(solver)


def identity_task():
    return {'train': [{'input': [[1, 0]], 'output': [[1, 0]]},
                      {'input': [[2, 0]], 'output': [[2, 0]]},
                      {'input': [[3, 0]], 'output': [[3, 0]]}],
            'test': [{'input': [[4, 0]]}]}


class IdentityBackend:
    def __init__(self, memorize=False):
        self.fits, self.memorize = [], memorize
    def fit(self, arm, retained, check):
        self.fits.append(copy.deepcopy(retained))
        return {'seen': [p['input'] for p in retained], 'cost': {}, 'fit_number': len(self.fits)}, {'retained_count': len(retained)}
    def predict(self, state, query, check):
        check()
        return copy.deepcopy(query) if not self.memorize or query in state['seen'] else None


class PackageTests(unittest.TestCase):
    def test_each_LOO_fold_is_resynthesized_fresh(self):
        backend = IdentityBackend()
        task = identity_task()
        predictions, report = solver.solve(task, lambda: None, backend)
        self.assertEqual(predictions, [[[4, 0]]])
        self.assertEqual(report['fit_invocations'], 4)
        self.assertEqual(len(backend.fits), 4)
        self.assertEqual(backend.fits[0], task['train'])
        for index, retained in enumerate(backend.fits[1:]):
            self.assertEqual(retained, [p for i, p in enumerate(task['train']) if i != index])
            self.assertNotIn(task['train'][index], retained)
        self.assertTrue(report['arms'][0]['accepted'])

    def test_memorized_full_fit_fails_genuine_LOO(self):
        backend = IdentityBackend(memorize=True)
        values, report = solver.solve(identity_task(), lambda: None, backend)
        self.assertEqual(values, [None])
        self.assertFalse(any(a['accepted'] for a in report['arms']))
        self.assertFalse(report['LOO_fits_cache_reused'])

    def test_fewer_than_two_demos(self):
        task = identity_task(); task['train'] = task['train'][:1]
        values, report = api.candidates_with_report(task, 1.0, 1.0)
        self.assertEqual(values, [None])
        self.assertEqual(report['status'], 'INSUFFICIENT_VALIDATION_EVIDENCE')

    def test_caps_reject_nan_inf_bool_and_nonpositive(self):
        for value in (float('nan'), float('inf'), -1, 0, True, '1'):
            for cpu, wall in ((value, 1.0), (1.0, value)):
                values, report = api.candidates_with_report(identity_task(), cpu, wall)
                self.assertEqual(values, [None]); self.assertEqual(report['status'], 'ABSTAIN')

    def test_metadata_is_ignored_and_answer_fields_rejected(self):
        class Unreadable:
            def __str__(self): raise AssertionError('identity value read')
            def __repr__(self): raise AssertionError('identity value read')
        task = identity_task(); task['id'] = Unreadable(); task['task_id'] = Unreadable()
        self.assertEqual(api._clean_task(task), identity_task())
        for changed in ({**identity_task(), 'answer': Unreadable()},
                        {**identity_task(), 'test': [{'input': [[1]], 'output': Unreadable()}]}):
            self.assertEqual(api.candidates(changed, 1, 1), [None])
        bad = identity_task(); bad['train'][0]['input'] = [[True]]
        self.assertEqual(api.candidates(bad, 1, 1), [None])

    def _copy(self, directory, solver_source, reseal=True):
        target = Path(directory) / 'portable'
        shutil.copytree(HERE, target, ignore=shutil.ignore_patterns('__pycache__', 'runs', 'reports'))
        (target / 'solver.py').write_text(solver_source)
        if reseal:
            manifest = json.loads((target / 'MANIFEST.json').read_text())
            manifest['files']['solver.py'] = hashlib.sha256((target / 'solver.py').read_bytes()).hexdigest()
            (target / 'MANIFEST.json').write_text(json.dumps(manifest))
        return target

    def _offthread(self, target, cpu, wall):
        with patch.object(api, 'HERE', target), concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(api.candidates_with_report, identity_task(), cpu, wall).result(timeout=wall + 3)

    def test_running_CPU_cap_off_main_thread(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self._copy(directory, 'def solve(task,check):\n while True: pass\n')
            started = time.monotonic()
            values, report = self._offthread(target, .15, 2.0)
            self.assertEqual(values, [None]); self.assertEqual(report['status'], 'ABSTAIN')
            self.assertLess(time.monotonic()-started, 1.5)
            self.assertLess(report['waited_child_CPU_s'], .30)

    def test_running_wall_cap_off_main_thread(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self._copy(directory, 'import time\ndef solve(task,check):\n time.sleep(60)\n')
            started = time.monotonic()
            values, report = self._offthread(target, 1.0, .15)
            self.assertEqual(values, [None]); self.assertEqual(report['status'], 'ABSTAIN')
            self.assertLess(time.monotonic()-started, 1.0)

    def test_manifest_mismatch_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self._copy(directory, "raise AssertionError('should never import')\n", reseal=False)
            values, report = self._offthread(target, 1.0, 2.0)
            self.assertEqual(values, [None]); self.assertEqual(report['status'], 'ABSTAIN')

    def test_external_lifecycle_cancellation_propagates_after_cleanup(self):
        class ExternalTimeout(TimeoutError): pass
        real_stop = api._stop
        for cancellation in (KeyboardInterrupt('cancel'), SystemExit('stop'), ExternalTimeout('outer resource guard')):
            with patch.object(api, '_wait', side_effect=cancellation), patch.object(api, '_stop', wraps=real_stop) as cleanup:
                with self.assertRaises(type(cancellation)) as caught:
                    api.candidates_with_report(identity_task(), 1.0, 2.0)
                self.assertIs(caught.exception, cancellation)
                proc = cleanup.call_args[0][0]
                self.assertIsNotNone(proc)
                self.assertIsNotNone(proc.returncode)

    def test_actual_portable_hflip_is_deterministic(self):
        xs = [[[1,0,2],[0,3,0]], [[2,1,0],[3,0,1]], [[0,2,3],[1,0,2]]]
        task = {'train': [{'input': x, 'output': [row[::-1] for row in x]} for x in xs],
                'test': [{'input': [[2,3,0],[0,0,1]]}]}
        one, r1 = api.candidates_with_report(task, 10.0, 20.0)
        two, r2 = api.candidates_with_report(task, 10.0, 20.0)
        self.assertEqual(one, [[[0,3,2],[1,0,0]]]); self.assertEqual(one, two)
        self.assertEqual(r1['status'], 'ACCEPTED_FULL_AND_FRESH_LOO')
        self.assertEqual(r1['selected_arms'], r2['selected_arms'])
        self.assertTrue(r1['arms'][0]['full_replay_exact'])
        self.assertTrue(all(f['held_exact'] for f in r1['arms'][0]['folds']))

if __name__ == '__main__':
    unittest.main()
