import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

import vnvkr_yesman as backend


class PluginFormatTests(unittest.TestCase):
    def row(self, source, dest):
        return dict(owner='falloutnv.esm', id='123456', signature='MESG', field='DESC',
                    path='DESC', source=source, dest=dest)

    def test_percentage_and_actor_directions_are_prose(self):
        backend.validate_mapping(self.row('{Barter Check} +1% to earned XP <Lie>', '경험치 획득 +1% <거짓말>'))

    def test_printf_and_font_markup_preserved(self):
        backend.validate_mapping(self.row('<font face="1">Value: %.2f, %g %%</font>',
                                          '<font face="1">값: %.2f, %g %%</font>'))
        for source, dest in [('Value %.2f', '값 %g'), ('Chance 50%%', '확률 50%'),
                             ('<font face="1">Name</font>', '<font face="2">이름</font>')]:
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'protected tokens'):
                backend.validate_mapping(self.row(source, dest))


class PipelinePlanningTests(unittest.TestCase):
    def test_active_targets_use_only_required_load_order_prefix(self):
        installation = SimpleNamespace(active=[
            'FalloutNV.esm', 'DeadMoney.esm', 'YUP.esm', 'Late Patch.esp'])
        self.assertEqual(
            backend._session_plugins(installation, [{'path': 'FalloutNV.esm'}], {}),
            ['FalloutNV.esm'])
        self.assertEqual(
            backend._session_plugins(installation, [{'path': 'YUP.esm'}], {}),
            ['FalloutNV.esm', 'DeadMoney.esm', 'YUP.esm'])
        self.assertEqual(
            backend._session_plugins(installation, [{'path': 'Missing.esp'}], {}),
            installation.active)

    def test_optional_override_keeps_conservative_full_active_set(self):
        installation = SimpleNamespace(active=['FalloutNV.esm', 'YUP.esm'])
        plugins = backend._session_plugins(
            installation, [{'path': 'Optional.esp'}], {'Optional.esp': Path('optional')})
        self.assertEqual(plugins, ['FalloutNV.esm', 'YUP.esm', 'Optional.esp'])

    def test_inheritance_memory_is_apply_only_and_counted_separately(self):
        with tempfile.TemporaryDirectory(prefix='VNV inheritance plan ') as temp:
            root = Path(temp)
            sources = root / 'sources'
            sources.mkdir()
            (sources / 'FalloutNV.esm').write_bytes(b'base')
            (sources / 'NewPatch.esp').write_bytes(b'new')
            installation = SimpleNamespace(
                active=['FalloutNV.esm', 'NewPatch.esp'],
                source=lambda name: sources / name)
            entries = [{'path': 'NewPatch.esp', 'mappings': []}]
            fallback = [self._inheritance_row()]
            phases = []

            def fake_adapter(request, job, phase):
                phases.append((phase, copy.deepcopy(request)))
                common = {'plugin': 'NewPatch.esp', 'masters': ['FalloutNV.esm'],
                          'headerHash': 'header', 'rows': [], 'beforeHashes': [
                              {'owner': 'falloutnv.esm', 'id': '123456',
                               'signature': 'MESG', 'hash': '0' * 64}]}
                if phase == 'legacy-before':
                    return {'files': [common]}
                if phase == 'apply':
                    translated = Path(request['outDir'])
                    translated.mkdir(parents=True, exist_ok=True)
                    (translated / 'NewPatch.esp').write_bytes(b'new translated')
                    return {'files': [{**common, 'changed': [{**fallback[0],
                                      'mappingOrigin': 'base_inherited'}], 'missing': []}]}
                return {'files': [common]}

            with mock.patch.object(backend, 'runtime'), mock.patch.object(
                    backend, 'run_adapter', side_effect=fake_adapter):
                translated, stats = backend.merge_plugins(
                    installation, entries, {'plugin_fields': {'MESG': ['DESC']}},
                    root / 'job', fallback_mappings=fallback,
                    inherit_targets={'NewPatch.esp'})
            by_phase = {phase: request for phase, request in phases}
            self.assertNotIn('fallbackMappings', by_phase['legacy-before'])
            self.assertEqual(by_phase['legacy-before']['inheritTargets'], ['NewPatch.esp'])
            self.assertTrue(by_phase['legacy-before']['legacyFallbackRecordKeys'])
            self.assertEqual(by_phase['apply']['fallbackMappings'], fallback)
            self.assertEqual(by_phase['apply']['inheritTargets'], ['NewPatch.esp'])
            self.assertNotIn('fallbackMappings', by_phase['verify'])
            self.assertEqual(stats['NewPatch.esp']['translated'], 1)
            self.assertEqual(stats['NewPatch.esp']['inherited_translated'], 1)
            self.assertEqual(stats['NewPatch.esp']['catalog_translated'], 0)
            self.assertTrue((translated / 'NewPatch.esp').is_file())

    @staticmethod
    def _inheritance_row():
        return {'owner': 'falloutnv.esm', 'id': '123456', 'signature': 'MESG',
                'field': 'DESC', 'path': 'DESC', 'source': 'Vanilla text',
                'dest': '기본 번역'}

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
            self.assertIn(f'-P:{isolation / "plugins.txt"}', args)
            self.assertTrue((isolation / 'Temp').is_dir())
            self.assertTrue((isolation / 'Cache').is_dir())


class NativeUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.fixture = cls.root / 'staging/yesman_update_fixture'
        if not (cls.fixture / 'current/Data/MercenaryPack.esm').is_file():
            raise unittest.SkipTest('Local official-library fixture has not been prepared')
        try:
            backend.runtime()
        except FileNotFoundError as error:
            raise unittest.SkipTest(str(error))

    def test_updated_records_remain_and_known_texts_translate(self):
        with tempfile.TemporaryDirectory(prefix='VNV native update 시험 ') as temp:
            job = Path(temp)
            game = job / 'Game'
            shutil.copytree(self.fixture / 'current', game)
            request = json.loads((self.fixture / 'apply-v2-request.json').read_text(encoding='utf-8'))
            request.update(game=str(game), output=str(job / 'apply.json'), outDir=str(job / 'Translated'))
            applied = backend.run_adapter(request, job, 'apply')['files'][0]
            self.assertEqual(len(applied['changed']), 3)
            self.assertEqual(len(applied['missing']), 2)
            english = {row['source'] for row in applied['missing']}
            self.assertEqual(english, {'Extra updated English description!', 'New untranslated upstream note'})
            shutil.copyfile(job / 'Translated/MercenaryPack.esm', game / 'Data/MercenaryPack.esm')
            request.update(mode='verify', output=str(job / 'verify.json'),
                           expected={applied['plugin']: applied['beforeHashes']},
                           changes={applied['plugin']: applied['changed']})
            request.pop('outDir')
            verified = backend.run_adapter(request, job, 'verify')['files'][0]
            self.assertEqual(len(verified['rows']), 5)
            self.assertIn('★ 가벼운 금속 갑옷', {row['source'] for row in verified['rows']})
            message = {row['field']: row['source'] for row in verified['rows']
                       if row['signature'] == 'MESG' and row['id'] == '174776'}
            # A changed description does not prevent translating another field
            # of the same record, nor other records in the same plugin.
            self.assertEqual(message['FULL'], '용병 팩')
            self.assertEqual(message['DESC'], 'Extra updated English description!')
            self.assertEqual(next(row['source'] for row in verified['rows'] if row['signature'] == 'NOTE'),
                             'New untranslated upstream note')
            # Native structure hashes include the changed armor Weight=43.5.
            # Require all copied records, not merely records that were translated.
            broken = copy.deepcopy(request)
            broken['expected'][applied['plugin']].append(dict(owner='mercenarypack.esm', id='abcdef', signature='NOTE', hash='0'*64))
            broken['output'] = str(job / 'missing-record.json')
            with self.assertRaisesRegex(ValueError, 'Records missing from readback'):
                backend.run_adapter(broken, job, 'missing-record')
            broken = copy.deepcopy(request)
            broken['changes'][applied['plugin']][0]['dest'] = 'Incorrect readback'
            broken['output'] = str(job / 'wrong-translation.json')
            with self.assertRaisesRegex(ValueError, 'Translation readback mismatch'):
                backend.run_adapter(broken, job, 'wrong-translation')

    def test_native_file_handles_do_not_mix_master_ownership(self):
        probe = self.root / 'staging/yesman_probe/VNVKR_EncodingProbe.esp'
        if not probe.is_file():
            self.skipTest('Encoding probe not prepared')
        with tempfile.TemporaryDirectory(prefix='VNV native owner 시험 ') as temp:
            job = Path(temp)
            game = job / 'Game'
            shutil.copytree(self.fixture / 'current', game)
            shutil.copyfile(probe, game / 'Data/probe.esp')
            request = {'game': str(game), 'plugins': ['MercenaryPack.esm', 'probe.esp'],
                       'fields': {'NOTE': ['FULL']}, 'output': str(job / 'ownership.json')}
            result = backend.run_adapter(request, job, 'ownership')
            self.assertEqual(result['files'][0]['rows'][0]['owner'], 'mercenarypack.esm')
            self.assertEqual(result['files'][1]['rows'][0]['owner'], 'probe.esp')

    def test_merge_pipeline_checks_both_codepages(self):
        source = self.fixture / 'current/Data/MercenaryPack.esm'
        request = json.loads((self.fixture / 'apply-v2-request.json').read_text(encoding='utf-8'))
        installation = SimpleNamespace(active=['FalloutNV.esm', 'MercenaryPack.esm'],
                                       source=lambda name: self.fixture / 'current/Data' / name)
        entries = [{'path': 'MercenaryPack.esm', 'mappings': request['mappings']['MercenaryPack.esm']}]
        with tempfile.TemporaryDirectory(prefix='VNV dual codepage ') as temp:
            job = Path(temp) / 'NativeJob'
            translated, stats = backend.merge_plugins(installation, entries, {'plugin_fields': request['fields']}, job)
            self.assertTrue((translated / 'MercenaryPack.esm').is_file())
            self.assertEqual(stats['MercenaryPack.esm']['translated'], 3)
            self.assertEqual(stats['MercenaryPack.esm']['unmatched'], 2)
            self.assertIn('CP1252', stats['MercenaryPack.esm']['verification'])
            before = json.loads((job / 'legacy-before.json').read_text(encoding='utf-8'))
            after = json.loads((job / 'legacy-verify.json').read_text(encoding='utf-8'))
            self.assertEqual(before['acp'], 1252)
            self.assertEqual(after['acp'], 1252)


if __name__ == '__main__':
    unittest.main()
