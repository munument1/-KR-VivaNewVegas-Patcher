import copy
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

import vnvkr_xedit as backend
from vnvkr_xedit_worker import select_destination


class PluginFormatTests(unittest.TestCase):
    def row(self, source, dest):
        return dict(owner='falloutnv.esm', id='123456', signature='MESG',
                    field='DESC', path='DESC', source=source, dest=dest)

    def test_printf_and_markup_are_preserved(self):
        backend.validate_mapping(self.row(
            '<font face="1">Value: %.2f, %g %%</font>',
            '<font face="1">값: %.2f, %g %%</font>'))
        for source, dest in [
            ('Value %.2f', '값 %g'),
            ('Chance 50%%', '확률 50%'),
            ('<font face="1">Name</font>', '<font face="2">이름</font>'),
        ]:
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'protected tokens'):
                backend.validate_mapping(self.row(source, dest))


class MappingPriorityTests(unittest.TestCase):
    def test_direct_sst_wins_over_fallback(self):
        item = {'field': 'FULL', 'path': 'FULL', 'source': 'Gambler'}
        direct = [{'field': 'FULL', 'path': 'FULL', 'source': 'Gambler', 'dest': '도박꾼'}]
        fallback = [{'field': 'FULL', 'path': 'FULL', 'source': 'Gambler', 'dest': '갬블러'}]
        values, origin = select_destination(item, direct, fallback)
        self.assertEqual(values, {'도박꾼'})
        self.assertEqual(origin, 'sst_direct')

    def test_fallback_requires_exact_path(self):
        item = {'field': 'FULL', 'path': r'XMRK\FULL', 'source': 'Door'}
        fallback = [{'field': 'FULL', 'path': 'FULL', 'source': 'Door', 'dest': '문'}]
        values, origin = select_destination(item, [], fallback)
        self.assertEqual(values, set())
        self.assertIsNone(origin)


class PipelinePlanningTests(unittest.TestCase):
    def test_active_targets_use_required_load_order_prefix(self):
        installation = SimpleNamespace(active=[
            'FalloutNV.esm', 'DeadMoney.esm', 'YUP.esm', 'Late Patch.esp'])
        self.assertEqual(
            backend._session_plugins(installation, [{'path': 'YUP.esm'}], {}),
            ['FalloutNV.esm', 'DeadMoney.esm', 'YUP.esm'])

    def test_xedit_paths_are_isolated_inside_job(self):
        with tempfile.TemporaryDirectory(prefix='VNV xEdit isolation ') as temp:
            job = Path(temp)
            game = job / 'Game'
            request = {'game': str(game), 'plugins': ['FalloutNV.esm', 'YUP.esm']}
            args = backend._xedit_isolation_args(request, job)
            isolation = job / 'XEditIsolation'
            self.assertEqual(
                (isolation / 'plugins.txt').read_text(encoding='cp1252'),
                'FalloutNV.esm\nYUP.esm\n')
            self.assertIn(f'-D:{game / "Data"}', args)
            self.assertIn(f'-M:{isolation}{__import__("os").sep}', args)

    def test_pipeline_has_only_apply_and_verify_passes(self):
        with tempfile.TemporaryDirectory(prefix='VNV SST plan ') as temp:
            root = Path(temp)
            sources = root / 'sources'
            sources.mkdir()
            (sources / 'FalloutNV.esm').write_bytes(b'base')
            (sources / 'NewPatch.esp').write_bytes(b'new')
            installation = SimpleNamespace(
                active=['FalloutNV.esm', 'NewPatch.esp'],
                source=lambda name: sources / name)
            direct = {'owner': 'falloutnv.esm', 'id': '123456', 'signature': 'MESG',
                      'field': 'FULL', 'path': 'FULL', 'source': 'Vanilla',
                      'dest': '직접 번역'}
            fallback = [{**direct, 'dest': '폴백 번역'}]
            entries = [{'path': 'NewPatch.esp', 'mappings': [direct]}]
            phases = []

            def fake_worker(request, job, phase):
                phases.append((phase, copy.deepcopy(request)))
                common = {
                    'plugin': 'NewPatch.esp',
                    'masters': ['FalloutNV.esm'],
                    'headerHash': 'header',
                    'recordIndexHash': 'index',
                    'recordCount': 1,
                    'rows': [],
                }
                if phase == 'apply':
                    translated = Path(request['outDir'])
                    translated.mkdir(parents=True, exist_ok=True)
                    (translated / 'NewPatch.esp').write_bytes(b'translated')
                    changed = [{**direct, 'mappingOrigin': 'sst_direct'}]
                    return {'files': [{**common, 'beforeHashes': [
                        {'owner': 'falloutnv.esm', 'id': '123456',
                         'signature': 'MESG', 'hash': '0' * 64}],
                        'changed': changed, 'missing': []}]}
                return {'files': [{**common, 'beforeHashes': [], 'changed': [], 'missing': []}]}

            with mock.patch.object(backend, 'runtime'), mock.patch.object(
                    backend, 'run_worker', side_effect=fake_worker):
                translated, stats = backend.merge_plugins(
                    installation, entries, {'plugin_fields': {'MESG': ['FULL']}},
                    root / 'job', fallback_mappings=fallback,
                    fallback_targets={'NewPatch.esp'})

            self.assertEqual([phase for phase, _ in phases], ['apply', 'verify'])
            self.assertIn('fallbackMappings', phases[0][1])
            self.assertNotIn('fallbackMappings', phases[1][1])
            self.assertEqual(stats['NewPatch.esp']['direct_sst_translated'], 1)
            self.assertEqual(stats['NewPatch.esp']['fallback_translated'], 0)
            self.assertNotIn('CP1252', stats['NewPatch.esp']['verification'])
            self.assertTrue((translated / 'NewPatch.esp').is_file())


if __name__ == '__main__':
    unittest.main()
