import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import vnvkr
import vnvkr_output as output


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='VNV Output 시험 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mo2 = self.root / 'MO2'
        self.game = self.root / 'Game'
        (self.game / 'Data').mkdir(parents=True)
        (self.game / 'Data/FalloutNV.esm').write_bytes(b'synthetic master')
        profile = self.mo2 / 'profiles/Extended'
        profile.mkdir(parents=True)
        (self.mo2 / 'ModOrganizer.ini').write_text(
            f'[General]\ngameName=Fallout New Vegas\ngamePath={self.game}\nselected_profile=Extended\n', encoding='utf-8')
        (profile / 'modlist.txt').write_text('+Renamed Mod\n+Low\n', encoding='utf-8')
        (profile / 'plugins.txt').write_text('FalloutNV.esm\nMod.esp\n', encoding='cp1252')
        (profile / 'loadorder.txt').write_text('FalloutNV.esm\nMod.esp\n', encoding='utf-8')
        self.mod = self.mo2 / 'mods/Renamed Mod'
        (self.mod / 'MCM/Translations').mkdir(parents=True)
        (self.mo2 / 'mods/Low/MCM/Translations').mkdir(parents=True)
        self.ini = self.mod / 'MCM/Translations/a.ini'
        self.ini.write_bytes(b'[Translations]\r\n$Old="Old %%"\r\n$New=Added after release\r\n$Changed=Changed meaning\r\n')
        (self.mo2 / 'mods/Low/MCM/Translations/a.ini').write_text('[Translations]\n$Old=low priority\n', encoding='utf-8')
        (self.mod / 'Mod.esp').write_bytes(b'synthetic updated plugin')
        self.catalog = self.root / 'catalog'
        (self.catalog / 'plugins').mkdir(parents=True)
        payload = self.catalog / 'plugins/Mod.esp'
        payload.write_bytes(b'synthetic Korean plugin')
        self.plugin = {'path': 'Mod.esp', 'kind': 'plugin-copy', 'baseline_sha256': '0' * 64,
                       'payload': 'plugins/Mod.esp', 'payload_sha256': vnvkr.sha256(payload)}
        self.mapping = {'path': 'MCM/Translations/a.ini', 'kind': 'ini', 'baseline_sha256': '0' * 64,
                        'mappings': [{'section': '[Translations]', 'key': '$Old', 'source': 'Old %%', 'dest': '기존 %%'},
                                     {'section': '[Translations]', 'key': '$Changed', 'source': 'Old meaning', 'dest': '옛 의미'}]}
        vnvkr.write_json(self.catalog / 'catalog.json', {'schema_version': 1, 'files': [self.mapping, self.plugin]})
        self.out = self.root / 'Output'

    def build(self):
        return output.build_output(vnvkr.Installation(self.mo2), self.catalog, self.out)

    def test_current_provider_mirror_and_updated_ini_preserved(self):
        before = {p: p.read_bytes() for p in self.mo2.rglob('*') if p.is_file()}
        report = self.build()
        expected = b'[Translations]\r\n$Old="' + '기존 %%'.encode() + b'"\r\n$New=Added after release\r\n$Changed=Changed meaning\r\n'
        self.assertEqual((self.out / 'mods/Renamed Mod/MCM/Translations/a.ini').read_bytes(), expected)
        self.assertEqual(report['files'][0]['translated'], 1)
        self.assertEqual(report['files'][0]['unmatched'], 2)
        self.assertEqual(report['skipped'][0]['reason'], 'updated_plugin_needs_record_backend')
        self.assertFalse((self.out / 'mods/Renamed Mod/Mod.esp').exists())
        self.assertTrue(all(p.read_bytes() == raw for p, raw in before.items()))
        self.assertTrue(self.out.with_name('Output.report.json').is_file())
        self.assertFalse((self.out / 'Output.report.json').exists())

    def test_exact_plugin_is_opaque_copy(self):
        self.plugin['baseline_sha256'] = vnvkr.sha256(self.mod / 'Mod.esp')
        vnvkr.write_json(self.catalog / 'catalog.json', {'schema_version': 1, 'files': [self.plugin]})
        report = self.build()
        self.assertEqual((self.out / 'mods/Renamed Mod/Mod.esp').read_bytes(), b'synthetic Korean plugin')
        self.assertEqual(len(report['skipped']), 0)

    def test_corrupt_plugin_is_not_published(self):
        (self.catalog / 'plugins/Mod.esp').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
            self.build()
        self.assertFalse(self.out.exists())

    def test_removed_catalog_plugin_is_skipped_before_native_backend(self):
        (self.mod / 'Mod.esp').unlink()
        plugin = {'path': 'Mod.esp', 'kind': 'plugin-records',
                  'baseline_sha256': '0' * 64, 'mappings': []}
        vnvkr.write_json(self.catalog / 'catalog.json',
                         {'schema_version': 1, 'files': [self.mapping, plugin], 'plugin_fields': {}})
        with mock.patch.object(output.vnvkr_yesman, 'merge_plugins',
                               side_effect=AssertionError('missing plugin reached native backend')):
            report = self.build()
        skipped = next(row for row in report['skipped'] if row['path'] == 'Mod.esp')
        self.assertEqual(skipped['reason'], 'not_installed')
        self.assertFalse((self.out / 'mods/Renamed Mod/Mod.esp').exists())


    def test_fixed_esm_memory_uses_only_official_master_entries(self):
        base = {'owner': 'falloutnv.esm', 'id': '123456', 'signature': 'MESG',
                'field': 'DESC', 'path': 'DESC', 'source': 'Vanilla text', 'dest': '기본 번역'}
        patch = {**base, 'dest': '패치 전용 번역'}
        catalog = {'files': [
            {'path': 'FalloutNV.esm', 'kind': 'plugin-records', 'mappings': [base]},
            {'path': 'Some Patch.esp', 'kind': 'plugin-records', 'mappings': [patch]},
        ]}
        memory = output.base_translation_memory(catalog)
        self.assertEqual(len(memory), 1)
        self.assertEqual(memory[0]['dest'], '기본 번역')

    def test_new_plugin_is_auto_inherited_and_reported(self):
        fixed = self.mod / 'FalloutNV.esm'
        fixed.write_bytes(b'fixed master current')
        new_plugin = self.mod / 'New VNV Patch.esp'
        new_plugin.write_bytes(b'new plugin current')
        profile = self.mo2 / 'profiles/Extended'
        (profile / 'plugins.txt').write_text(
            'FalloutNV.esm\nMod.esp\nNew VNV Patch.esp\n', encoding='cp1252')
        (profile / 'loadorder.txt').write_text(
            'FalloutNV.esm\nMod.esp\nNew VNV Patch.esp\n', encoding='utf-8')
        self.plugin['baseline_sha256'] = vnvkr.sha256(self.mod / 'Mod.esp')
        base_mapping = {'owner': 'falloutnv.esm', 'id': '123456', 'signature': 'MESG',
                        'field': 'DESC', 'path': 'DESC', 'source': 'Vanilla text', 'dest': '기본 번역'}
        base_entry = {'path': 'FalloutNV.esm', 'kind': 'plugin-records',
                      'baseline_sha256': vnvkr.sha256(fixed), 'mappings': [base_mapping]}
        vnvkr.write_json(self.catalog / 'catalog.json',
                         {'schema_version': 1, 'files': [self.mapping, self.plugin, base_entry],
                          'plugin_fields': {'MESG': ['DESC']}})

        def fake_merge(installation, entries, catalog, job, source_overrides=None,
                       fallback_mappings=None, inherit_targets=None, progress=None):
            self.assertEqual(inherit_targets, {'New VNV Patch.esp'})
            self.assertEqual(fallback_mappings, [base_mapping])
            translated = job / 'Translated'
            translated.mkdir(parents=True)
            stats = {}
            for entry in entries:
                if entry['path'] == 'FalloutNV.esm':
                    (translated / entry['path']).write_bytes(b'fixed master Korean')
                    stats[entry['path']] = {'translated': 1, 'inherited_translated': 0,
                                            'catalog_translated': 1, 'unmatched': 0,
                                            'unmatched_entries': [], 'records_verified': 1}
                elif entry['path'] == 'New VNV Patch.esp':
                    (translated / entry['path']).write_bytes(b'new plugin inherited Korean')
                    stats[entry['path']] = {'translated': 1, 'inherited_translated': 1,
                                            'catalog_translated': 0, 'unmatched': 0,
                                            'unmatched_entries': [], 'records_verified': 1}
                else:
                    self.fail(f'unexpected native entry: {entry["path"]}')
            return translated, stats

        with mock.patch.object(output.vnvkr_yesman, 'merge_plugins', side_effect=fake_merge):
            report = self.build()
        self.assertEqual((self.out / 'mods/Renamed Mod/New VNV Patch.esp').read_bytes(),
                         b'new plugin inherited Korean')
        inherited = next(row for row in report['plugin_outcomes']
                         if row['path'] == 'New VNV Patch.esp')
        self.assertEqual(inherited['category'], 'new_inherited')
        self.assertEqual(inherited['translated'], 1)
        text_report = Path(report['report_text'])
        self.assertTrue(text_report.is_file())
        self.assertIn('신규 플러그인 - Fixed ESM 동일 레코드 번역 상속',
                      text_report.read_text(encoding='utf-8-sig'))

    def test_plugin_outcomes_distinguish_updates_removals_and_no_match(self):
        report = {'files': [
            {'path': 'UpdatedGood.esp', 'source_updated': True, 'translated': 4, 'unmatched': 0},
            {'path': 'UpdatedPartial.esp', 'source_updated': True, 'translated': 3, 'unmatched': 2},
            {'path': 'UpdatedNone.esp', 'source_updated': True, 'translated': 0, 'unmatched': 5},
        ], 'skipped': [
            {'path': 'Removed.esp', 'reason': 'not_installed'},
            {'path': 'NewNoMatch.esp', 'reason': 'new_plugin_no_base_translation_match',
             'base_record_mismatches': 2},
        ]}
        categories = {row['path']: row['category'] for row in output.plugin_outcomes(report)}
        self.assertEqual(categories['UpdatedGood.esp'], 'updated_patched')
        self.assertEqual(categories['UpdatedPartial.esp'], 'updated_partial')
        self.assertEqual(categories['UpdatedNone.esp'], 'updated_untranslated')
        self.assertEqual(categories['Removed.esp'], 'removed')
        self.assertEqual(categories['NewNoMatch.esp'], 'new_no_match')

    def test_json_binding_survives_moved_option_new_fields_remain(self):
        before = {'modName': 'Test', 'options': {'1': {'title': 'Speed', 'vars': [{'configINI': 'Move:speed', 'default': 1}]}}}
        current = {'modName': 'Test', 'options': {
            '1': {'title': 'Speed', 'vars': [{'configINI': 'Other:speed', 'default': 99}]},
            '8': {'title': 'Speed', 'vars': [{'configINI': 'Move:speed', 'default': 3}], 'newKey': 'Keep me'},
            '9': {'title': 'New option', 'type': 5}}}
        path = self.root / 'MCM.json'
        path.write_text(json.dumps(current), encoding='utf-8')
        entry = {'kind': 'json', 'mappings': [{'source': 'Speed', 'dest': '속도',
                'context': output.stable_context(before, ['options', '1', 'title'])}]}
        raw, stats = output.merge_loose(path, entry)
        merged = json.loads(raw)
        self.assertEqual(merged['options']['8']['title'], '속도')
        self.assertEqual(merged['options']['1']['title'], 'Speed')
        self.assertEqual(merged['options']['9']['title'], 'New option')
        self.assertEqual(merged['options']['8']['newKey'], 'Keep me')
        merged['options']['8']['title'] = 'Speed'
        self.assertEqual(merged, current)
        self.assertEqual(stats['translated'], 1)

    def test_ini_duplicate_keys_and_ambiguous_mapping(self):
        self.ini.write_bytes(b'[T]\n$Name=First\n$Name=Second\n$Same=Same\n')
        entry = {'kind': 'ini', 'mappings': [
            {'section': '[T]', 'key': '$Name', 'source': 'First', 'dest': '첫째'},
            {'section': '[T]', 'key': '$Name', 'source': 'Second', 'dest': '둘째'},
            {'section': '[T]', 'key': '$Same', 'source': 'Same', 'dest': '동일'},
            {'section': '[T]', 'key': '$Same', 'source': 'Same', 'dest': '같음'}]}
        raw, stats = output.merge_loose(self.ini, entry)
        self.assertEqual(raw.decode(), '[T]\n$Name=첫째\n$Name=둘째\n$Same=Same\n')
        self.assertEqual(stats['unmatched_entries'][0]['reason'], 'ambiguous')

    def test_changed_control_token_does_not_match(self):
        self.ini.write_text('[T]\n$Label=#5|Value %g\n', encoding='utf-8')
        entry = {'kind': 'ini', 'mappings': [{'section': '[T]', 'key': '$Label', 'source': '#5|Value %g', 'dest': '#5|값 %s'}]}
        with self.assertRaisesRegex(ValueError, 'protected tokens'):
            output.merge_loose(self.ini, entry)

    def test_existing_or_live_output_rejected(self):
        self.out.mkdir()
        with self.assertRaises(FileExistsError):
            self.build()
        for bad in (self.mo2 / 'Output', self.mod / 'Output', self.game / 'Output'):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                output.build_output(vnvkr.Installation(self.mo2), self.catalog, bad)

    def test_catalog_path_escape_rejected(self):
        self.mapping['path'] = '../escape.ini'
        vnvkr.write_json(self.catalog / 'catalog.json', {'schema_version': 1, 'files': [self.mapping]})
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.out.exists())

    def test_official_pack_uses_mo2_fixed_master_not_game_data(self):
        (self.mod / 'FalloutNV.esm').write_bytes(b'synthetic fixed master')
        (self.mod / 'CaravanPack.esm').write_bytes(b'synthetic fixed caravan')
        (self.game / 'Data/CaravanPack.esm').write_bytes(b'synthetic raw game caravan')
        profile = self.mo2 / 'profiles/Extended'
        (profile / 'plugins.txt').write_text('FalloutNV.esm\nCaravanPack.esm\n', encoding='cp1252')
        (profile / 'loadorder.txt').write_text('FalloutNV.esm\nCaravanPack.esm\n', encoding='utf-8')
        plugin = {**self.plugin, 'path': 'CaravanPack.esm',
                  'baseline_sha256': vnvkr.sha256(self.mod / 'CaravanPack.esm')}
        vnvkr.write_json(self.catalog / 'catalog.json', {'schema_version': 1, 'files': [plugin]})
        self.build()
        self.assertEqual((self.out / 'mods/Renamed Mod/CaravanPack.esm').read_bytes(),
                         b'synthetic Korean plugin')
        self.assertEqual((self.game / 'Data/CaravanPack.esm').read_bytes(),
                         b'synthetic raw game caravan')

    def test_official_pack_without_fixed_esm_provider_is_rejected(self):
        (self.game / 'Data/CaravanPack.esm').write_bytes(b'synthetic raw game caravan')
        profile = self.mo2 / 'profiles/Extended'
        (profile / 'plugins.txt').write_text('FalloutNV.esm\nCaravanPack.esm\n', encoding='cp1252')
        (profile / 'loadorder.txt').write_text('FalloutNV.esm\nCaravanPack.esm\n', encoding='utf-8')
        plugin = {**self.plugin, 'path': 'CaravanPack.esm',
                  'baseline_sha256': vnvkr.sha256(self.game / 'Data/CaravanPack.esm')}
        vnvkr.write_json(self.catalog / 'catalog.json', {'schema_version': 1, 'files': [plugin]})
        with self.assertRaisesRegex(ValueError, 'Fixed ESMs'):
            self.build()
        self.assertFalse(self.out.exists())

    def test_optional_variant_copies_do_not_enable_plugins(self):
        optional = self.mo2 / 'mods/Optional'
        optional.mkdir()
        (optional / 'Mod.esp').write_bytes(b'synthetic optional version')
        plugin = {**self.plugin, 'provider': 'Optional', 'optional': True,
                  'baseline_sha256': vnvkr.sha256(optional / 'Mod.esp')}
        self.plugin['baseline_sha256'] = vnvkr.sha256(self.mod / 'Mod.esp')
        vnvkr.write_json(self.catalog / 'catalog.json', {'schema_version': 1, 'files': [self.plugin, plugin]})
        profile = self.mo2 / 'profiles/Extended'
        before = {p: p.read_bytes() for p in profile.iterdir()}
        self.build()
        self.assertTrue((self.out / 'mods/Optional/Mod.esp').is_file())
        self.assertTrue((self.out / 'mods/Renamed Mod/Mod.esp').is_file())
        self.assertTrue(all(p.read_bytes() == raw for p, raw in before.items()))

    def test_verified_delta_fast_path_skips_native_backend(self):
        target_raw = b'synthetic fast Korean plugin'
        patch_file = self.catalog / 'fast.vcdiff'
        patch_file.write_bytes(b'fixture delta')
        plugin = {'path': 'Mod.esp', 'kind': 'plugin-records',
                  'baseline_sha256': vnvkr.sha256(self.mod / 'Mod.esp'), 'mappings': [],
                  'verified_delta': {'source_sha256': vnvkr.sha256(self.mod / 'Mod.esp'),
                      'target_sha256': __import__('hashlib').sha256(target_raw).hexdigest(),
                      'target_size': len(target_raw), 'payload': 'fast.vcdiff',
                      'payload_sha256': vnvkr.sha256(patch_file), 'translated': 7,
                      'unmatched': 2, 'records_verified': 11, 'verification': 'fixture'}}
        vnvkr.write_json(self.catalog / 'catalog.json', {'schema_version': 1, 'files': [plugin]})
        def fake_delta(executable, mode, source, patch, target):
            self.assertEqual(mode, 'decode')
            target.write_bytes(target_raw)
        with mock.patch.object(output.vnvkr, 'engine', return_value=Path('xdelta3.exe')), \
             mock.patch.object(output.vnvkr, 'delta', side_effect=fake_delta), \
             mock.patch.object(output.vnvkr_yesman, 'merge_plugins', side_effect=AssertionError('slow path used')):
            report = self.build()
        self.assertEqual((self.out / 'mods/Renamed Mod/Mod.esp').read_bytes(), target_raw)
        self.assertEqual(report['files'][0]['status'], 'exact_source_verified_delta')
        self.assertEqual(report['files'][0]['translated'], 7)

    def test_already_patched_verified_plugin_skips_delta_and_native_backend(self):
        current = b'already Korean plugin'
        (self.mod / 'Mod.esp').write_bytes(current)
        patch_file = self.catalog / 'already.vcdiff'
        patch_file.write_bytes(b'fixture delta not needed for already-patched source')
        plugin = {'path': 'Mod.esp', 'kind': 'plugin-records',
                  'baseline_sha256': '1' * 64, 'mappings': [],
                  'verified_delta': {'source_sha256': '2' * 64,
                      'target_sha256': __import__('hashlib').sha256(current).hexdigest(),
                      'target_size': len(current), 'payload': 'already.vcdiff',
                      'payload_sha256': vnvkr.sha256(patch_file), 'translated': 5,
                      'unmatched': 0, 'records_verified': 9, 'verification': 'fixture'}}
        vnvkr.write_json(self.catalog / 'catalog.json', {'schema_version': 1, 'files': [plugin]})
        with mock.patch.object(output.vnvkr, 'delta', side_effect=AssertionError('delta should not run')), \
             mock.patch.object(output.vnvkr_yesman, 'merge_plugins',
                               side_effect=AssertionError('native backend should not run')):
            report = self.build()
        result = report['files'][0]
        self.assertEqual(result['status'], 'already_patched_verified')
        self.assertEqual((self.out / 'mods/Renamed Mod/Mod.esp').read_bytes(), current)
        outcome = next(row for row in report['plugin_outcomes'] if row['path'] == 'Mod.esp')
        self.assertEqual(outcome['category'], 'already_patched')

    def test_texture_follows_renamed_provider_and_keeps_original(self):
        asset = self.mod / 'Textures/terminals/english/vitomatic_page_0.dds'
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b'DDS original updated asset')
        payload = self.catalog / 'page.dds'
        payload.write_bytes(b'DDS Korean asset')
        spec = {'default_mod': 'Korean Assets', 'files': [
            {'path': 'Textures/terminals/english/vitomatic_page_0.dds',
             'payload': 'page.dds', 'payload_sha256': vnvkr.sha256(payload)}]}
        vnvkr.write_json(self.catalog / 'catalog.json', {'schema_version': 1, 'files': [], 'asset_bundle': spec})
        report = self.build()
        self.assertEqual((self.out / 'mods/Renamed Mod/Textures/terminals/english/vitomatic_page_0.dds').read_bytes(),
                         b'DDS Korean asset')
        self.assertEqual(asset.read_bytes(), b'DDS original updated asset')
        self.assertEqual(report['assets']['mods_requiring_activation'], [])

    def test_texture_without_loose_provider_uses_overlay(self):
        payload = self.catalog / 'page.dds'
        payload.write_bytes(b'DDS Korean asset')
        spec = {'default_mod': 'Korean Assets', 'files': [
            {'path': 'Textures/terminals/english/vitomatic_page_0.dds',
             'payload': 'page.dds', 'payload_sha256': vnvkr.sha256(payload)}]}
        vnvkr.write_json(self.catalog / 'catalog.json', {'schema_version': 1, 'files': [], 'asset_bundle': spec})
        report = self.build()
        self.assertTrue((self.out / 'mods/Korean Assets/Textures/terminals/english/vitomatic_page_0.dds').is_file())
        self.assertEqual(report['assets']['mods_requiring_activation'], ['Korean Assets'])


if __name__ == '__main__':
    unittest.main()
