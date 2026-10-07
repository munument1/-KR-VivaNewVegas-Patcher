from pathlib import Path
import tempfile
import unittest
from unittest import mock

import vnvkr
import vnvkr_install as install
import vnvkr_output as output


class InstallTests(unittest.TestCase):
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
                       'report_json': str(self.root / 'Output.report.json'), 'report_text': str(self.root / 'Output.report.txt')}
        Path(self.report['report_text']).write_text('report', encoding='utf-8')

    def row(self, path, raw=b'Korean', source=None):
        target = self.out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        row = {'output_path': path, 'output_sha256': vnvkr.sha256(target)}
        if source:
            row.update(source_path=str(source), source_sha256=vnvkr.sha256(source))
        self.report['files'].append(row)

    def test_external_paths_activation_and_exact_restore(self):
        original = self.mods / 'Other/a.ini'
        original.parent.mkdir(parents=True)
        original.write_bytes(b'original')
        self.row('mods/Other/a.ini', source=original)
        self.row('mods/KR Font/NVSE/Plugins/tnvse.dll')
        self.row('mods/KR UI/KR.esp')
        self.row('mods/Optional/Optional.esp')
        result = install.install_output(self.inst, self.out, self.report, self.snapshot)
        self.assertEqual(original.read_bytes(), b'Korean')
        mods = (self.profile / 'modlist.txt').read_text()
        self.assertTrue(mods.startswith('+KR Font\n+KR UI\n'))
        self.assertIn('-Optional\n', mods)
        self.assertIn('+Other\n', mods)
        self.assertIn('KR.esp', (self.profile / 'plugins.txt').read_text())
        self.assertEqual((self.profile / 'loadorder.txt').read_text().splitlines(),
                         ['FalloutNV.esm', 'Other.esp', 'Disabled.esp', 'KR.esp'])
        self.assertFalse((self.mo2 / 'mods').exists())
        install.restore_backup(result['backup'])
        self.assertEqual(original.read_bytes(), b'original')
        self.assertFalse((self.mods / 'KR UI/KR.esp').exists())
        self.assertEqual(install.profile_snapshot(self.inst), self.snapshot)

    def test_game_and_overwrite_plugins_use_overlay(self):
        game = self.data / 'GameOnly.esp'
        game.write_bytes(b'game')
        self.assertEqual(output.destination(self.inst, game, game.name), 'mods/VNV Korean Translations/GameOnly.esp')
        overwrite = self.inst.overwrite / 'Overwrite.esp'
        overwrite.parent.mkdir(parents=True)
        overwrite.write_bytes(b'overwrite')
        relative = output.destination(self.inst, overwrite, overwrite.name)
        self.assertEqual(relative, 'mods/VNV Korean Translations/Overwrite.esp')
        self.row(relative, source=overwrite)
        result = install.install_output(self.inst, self.out, self.report, self.snapshot)
        self.assertFalse(overwrite.exists())
        self.assertEqual(game.read_bytes(), b'game')
        self.assertIn('+VNV Korean Translations', (self.profile / 'modlist.txt').read_text())
        install.restore_backup(result['backup'])
        self.assertEqual(overwrite.read_bytes(), b'overwrite')

    def test_profile_change_prevents_writes(self):
        self.row('mods/KR UI/KR.esp')
        (self.profile / 'modlist.txt').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, '프로필'):
            install.install_output(self.inst, self.out, self.report, self.snapshot)
        self.assertFalse((self.mods / 'KR UI').exists())

    def test_failure_rolls_back_files_and_profile(self):
        original = self.mods / 'Other/a.ini'
        original.parent.mkdir(parents=True)
        original.write_bytes(b'original')
        self.row('mods/Other/a.ini', source=original)
        self.row('mods/KR UI/KR.esp')
        copy = install._atomic_copy
        def fail(source, target):
            if target.name == 'plugins.txt' and 'profile-new' in str(source):
                raise OSError('synthetic failure')
            copy(source, target)
        with mock.patch.object(install, '_atomic_copy', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'synthetic'):
                install.install_output(self.inst, self.out, self.report, self.snapshot)
        self.assertEqual(original.read_bytes(), b'original')
        self.assertEqual(install.profile_snapshot(self.inst), self.snapshot)
        self.assertFalse((self.mods / 'KR UI/KR.esp').exists())

    def test_tamper_and_source_change_are_rejected(self):
        source = self.data / 'GameOnly.esp'
        source.write_bytes(b'original')
        self.row('mods/VNV Korean Translations/GameOnly.esp', source=source)
        source.write_bytes(b'updated')
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            install.install_output(self.inst, self.out, self.report, self.snapshot)
        source.write_bytes(b'original')
        (self.out / self.report['files'][0]['output_path']).write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            install.install_output(self.inst, self.out, self.report, self.snapshot)

    def test_game_destination_is_rejected(self):
        self.row('StockGame/Data/GameOnly.esp')
        with self.assertRaisesRegex(ValueError, 'MO2 destination'):
            install.install_output(self.inst, self.out, self.report, self.snapshot)

    def test_running_mo2_is_rejected(self):
        with mock.patch.object(install.os, 'name', 'nt'), mock.patch.object(install.subprocess, 'CREATE_NO_WINDOW', 0, create=True), mock.patch.object(install.subprocess, 'run', return_value=mock.Mock(returncode=0, stdout='"ModOrganizer.exe","123"\n')):
            with self.assertRaisesRegex(RuntimeError, 'MO2를 종료'):
                install.require_mo2_closed()

    def test_repeat_activation_preserves_unrelated_order(self):
        changes, _, _ = install.profile_updates(self.inst, self.report, self.snapshot)
        next_snapshot = dict(self.snapshot)
        next_snapshot.update({str(p): raw for p, raw in changes.items()})
        second, _, _ = install.profile_updates(self.inst, self.report, next_snapshot)
        self.assertEqual(changes, second)
        self.assertEqual(changes[self.inst.profile_dir / 'modlist.txt'].decode().count('+KR Font'), 1)


if __name__ == '__main__':
    unittest.main()
