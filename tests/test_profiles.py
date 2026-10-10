from pathlib import Path
import tempfile
import unittest
from unittest import mock

import vnvkr
import vnvkr_profiles as install


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
        self.report = {'files': [], 'fonts': {'mod': 'KR Font', 'requires_priority_check': True},
                       'runtime_mods': {'mods_requiring_activation': ['KR UI'], 'plugins_requiring_activation': ['KR.esp']},
                       'output': str(self.out)}

    def prepare(self):
        install.prepare_instructions(self.inst, self.out, self.report, self.snapshot)
        return (self.out / 'INSTALL.txt').read_text(encoding='utf-8-sig')

    def test_output_only_and_source_profiles_unchanged(self):
        before = {p: p.read_bytes() for p in self.mo2.rglob('*') if p.is_file()}
        self.prepare()
        self.assertEqual(install.profile_snapshot(self.inst), self.snapshot)
        self.assertEqual({p: p.read_bytes() for p in self.mo2.rglob('*') if p.is_file()}, before)
        self.assertFalse((self.mods / 'KR Font').exists())
        self.assertFalse((self.out / 'profiles').exists())
        self.assertEqual(self.report['profile_files'], [])

    def test_manual_activation_instructions(self):
        text = self.prepare()
        self.assertIn('KR Font', text)
        self.assertIn('KR UI', text)
        self.assertIn('KR.esp', text)
        self.assertIn('원본 tNVSE보다 높은', text)
        self.assertEqual(self.report['manual_activation_mods'], ['KR Font', 'KR UI'])
        self.assertEqual(self.report['manual_activation_plugins'], ['KR.esp'])

    def test_disabled_and_optional_choices_are_unchanged(self):
        self.prepare()
        self.assertEqual((self.profile / 'modlist.txt').read_bytes(),
                         b'# MO2\r\n+Other\r\n-KR Font\r\n-Optional\r\n+tNVSE\r\n')
        self.assertEqual((self.profile / 'loadorder.txt').read_bytes(),
                         b'FalloutNV.esm\r\nOther.esp\r\nDisabled.esp\r\n')

    def test_data_overlay_is_manual(self):
        self.report['files'] = [{'output_path': 'mods/VNV Korean Translations/GameOnly.esp'}]
        text = self.prepare()
        self.assertIn('VNV Korean Translations', text)
        self.assertFalse((self.out / 'profiles').exists())

    def test_changed_profile_is_rejected(self):
        (self.profile / 'modlist.txt').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, '프로필'):
            self.prepare()
        self.assertFalse((self.out / 'INSTALL.txt').exists())

    def test_external_copy_destinations_are_documented(self):
        text = self.prepare()
        self.assertIn(str(self.inst.mods), text)
        self.assertNotIn(f'→ {self.inst.profile_dir}', text)
        self.assertIn('이전 Output의 profiles 폴더도 복사하지', text)

    def test_update_requires_new_output(self):
        self.assertIn('이전 Output을 재사용하지', self.prepare())

    def test_running_mo2_is_rejected(self):
        with mock.patch.object(install.os, 'name', 'nt'), mock.patch.object(install.subprocess, 'CREATE_NO_WINDOW', 0, create=True), mock.patch.object(install.subprocess, 'run', return_value=mock.Mock(returncode=0, stdout='"ModOrganizer.exe","123"\n')):
            with self.assertRaisesRegex(RuntimeError, 'MO2를 종료'):
                install.require_mo2_closed()


class TargetProfileTests(unittest.TestCase):
    setUp = ProfileTests.setUp

    def test_gui_reads_extended_without_producing_profile_files(self):
        from vnvkr_gui import target_installation, TARGET_PROFILE
        extended = self.profile.parent / TARGET_PROFILE
        extended.mkdir()
        for name in install.PROFILE_FILES:
            (extended / name).write_bytes((self.profile / name).read_bytes())
        inst = target_installation(self.mo2)
        self.assertEqual(inst.profile_dir, extended.resolve())
        before = {p: p.read_bytes() for p in self.profile.parent.rglob('*') if p.is_file()}
        install.prepare_instructions(inst, self.out, self.report, install.profile_snapshot(inst))
        self.assertFalse((self.out / 'profiles').exists())
        self.assertEqual(before, {p: p.read_bytes() for p in self.profile.parent.rglob('*') if p.is_file()})

    def test_gui_does_not_fall_back_to_selected_profile(self):
        from vnvkr_gui import target_installation
        with self.assertRaises(FileNotFoundError):
            target_installation(self.mo2)


if __name__ == '__main__':
    unittest.main()
