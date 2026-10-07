from pathlib import Path
import tempfile
import unittest
from unittest import mock

import vnvkr
import vnvkr_profiles as install
import vnvkr_output as output


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.mo2 = self.root / 'MO2'
        self.game = self.mo2 / 'StockGame'
        self.data = self.game / 'Data'
        self.data.mkdir(parents=True)
        (self.data / 'FalloutNV.esm').write_bytes(b'game master')
        self.mods = self.root / 'External Mods'
        self.mods.mkdir()
        self.profile = self.root / 'External Profiles/Main'
        self.profile.mkdir(parents=True)
        (self.mo2 / 'ModOrganizer.ini').write_text(
            f'[General]\ngameName=Fallout New Vegas\ngamePath={self.game}\nselected_profile=Main\n'
            f'[Settings]\nmod_directory={self.mods}\nprofiles_directory={self.profile.parent}\n', encoding='utf-8')
        (self.profile / 'modlist.txt').write_bytes(b'# MO2\r\n+Other\r\n-KR Font\r\n-Optional\r\n+tNVSE\r\n')
        (self.profile / 'plugins.txt').write_bytes(b'# MO2\r\nFalloutNV.esm\r\nOther.esp\r\n')
        (self.profile / 'loadorder.txt').write_bytes(b'FalloutNV.esm\r\nOther.esp\r\nDisabled.esp\r\n')
        self.inst = vnvkr.Installation(self.mo2)
        self.snapshot = install.profile_snapshot(self.inst)
        self.out = self.root / 'Output'
        self.out.mkdir()
        self.report = {'files': [], 'profile': 'Main', 'fonts': {'mod': 'KR Font', 'requires_priority_check': True},
                       'runtime_mods': {'mods_requiring_activation': ['KR UI'], 'plugins_requiring_activation': ['KR.esp']},
                       'output': str(self.out), 'report_json': str(self.root / 'Output.report.json'), 'report_text': str(self.root / 'Output.report.txt')}
        Path(self.report['report_text']).write_text('report', encoding='utf-8')

    def prepare(self):
        install.prepare_profiles(self.inst, self.out, self.report, self.snapshot)
        return self.out / 'profiles/Main'

    def test_output_only_and_source_profiles_unchanged(self):
        before = {p: p.read_bytes() for p in self.mo2.rglob('*') if p.is_file()}
        self.prepare()
        self.assertEqual(install.profile_snapshot(self.inst), self.snapshot)
        self.assertEqual({p: p.read_bytes() for p in self.mo2.rglob('*') if p.is_file()}, before)
        self.assertFalse((self.mods / 'KR Font').exists())
        self.assertEqual(self.report['install_state'], 'manual_copy_required')

    def test_activation_and_existing_plugin_order(self):
        out = self.prepare()
        self.assertTrue((out / 'modlist.txt').read_text().startswith('+KR Font\n+KR UI\n'))
        self.assertEqual((out / 'loadorder.txt').read_text().splitlines(),
                         ['FalloutNV.esm','Other.esp','Disabled.esp','KR.esp'])
        self.assertIn('KR.esp', (out / 'plugins.txt').read_text())

    def test_disabled_optional_mod_is_preserved(self):
        out = self.prepare()
        self.assertIn('-Optional', (out / 'modlist.txt').read_text())

    def test_data_overlay_is_enabled_in_template(self):
        self.report['files'] = [{'output_path': 'mods/VNV Korean Translations/GameOnly.esp'}]
        out = self.prepare()
        self.assertIn('+VNV Korean Translations', (out / 'modlist.txt').read_text())

    def test_changed_profile_is_rejected(self):
        (self.profile / 'modlist.txt').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, '프로필'):
            self.prepare()
        self.assertFalse((self.out / 'profiles').exists())

    def test_external_copy_destinations_are_documented(self):
        self.prepare()
        text = (self.out / 'INSTALL.txt').read_text(encoding='utf-8-sig')
        self.assertIn(str(self.inst.mods), text)
        self.assertIn(str(self.inst.profile_dir), text)
        self.assertTrue(all(Path(row['destination']).parent == self.inst.profile_dir for row in self.report['profile_files']))

    def test_activation_is_idempotent(self):
        changes, _, _ = install.profile_updates(self.inst, self.report, self.snapshot)
        next_snapshot = dict(self.snapshot)
        next_snapshot.update({str(p): raw for p, raw in changes.items()})
        second, _, _ = install.profile_updates(self.inst, self.report, next_snapshot)
        self.assertEqual(changes, second)

    def test_running_mo2_is_rejected(self):
        with mock.patch.object(install.os, 'name', 'nt'), mock.patch.object(install.subprocess, 'CREATE_NO_WINDOW', 0, create=True), mock.patch.object(install.subprocess, 'run', return_value=mock.Mock(returncode=0, stdout='"ModOrganizer.exe","123"\n')):
            with self.assertRaisesRegex(RuntimeError, 'MO2를 종료'):
                install.require_mo2_closed()


class TargetProfileTests(ProfileTests):
    def test_gui_targets_extended_even_when_other_profile_selected(self):
        from vnvkr_gui import target_installation, TARGET_PROFILE
        extended = self.profile.parent / TARGET_PROFILE
        extended.mkdir()
        for name in install.PROFILE_FILES:
            (extended / name).write_bytes((self.profile / name).read_bytes())
        inst = target_installation(self.mo2)
        self.assertEqual(inst.profile_dir, extended)
        report = dict(self.report, profile=TARGET_PROFILE)
        before = {p: p.read_bytes() for p in self.profile.parent.rglob('*') if p.is_file()}
        install.prepare_profiles(inst, self.out, report, install.profile_snapshot(inst))
        self.assertTrue((self.out / 'profiles' / TARGET_PROFILE / 'modlist.txt').is_file())
        self.assertEqual(before, {p: p.read_bytes() for p in self.profile.parent.rglob('*') if p.is_file()})
        self.assertIn(str(extended), (self.out / 'INSTALL.txt').read_text(encoding='utf-8-sig'))

    def test_gui_does_not_fall_back_to_selected_profile(self):
        from vnvkr_gui import target_installation
        with self.assertRaises(FileNotFoundError):
            target_installation(self.mo2)
