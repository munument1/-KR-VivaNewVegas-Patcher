import hashlib
from pathlib import Path
import tempfile
import unittest

import vnvkr_output


class DummyInstallation:
    def __init__(self, enabled=()):
        self.mods_enabled = list(enabled)


class RuntimeModsTests(unittest.TestCase):
    def test_runtime_mods_copy_and_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = root / 'catalog'
            stage = root / 'stage'
            catalog.mkdir()
            stage.mkdir()
            payload = catalog / 'runtime-payloads/Test Mod/NVSE/Plugins/test.dll'
            payload.parent.mkdir(parents=True)
            payload.write_bytes(b'abc')
            spec = [{'mod': 'Test Mod', 'plugins': ['Test.esp'], 'files': [{
                'path': 'NVSE/Plugins/test.dll',
                'payload': 'runtime-payloads/Test Mod/NVSE/Plugins/test.dll',
                'payload_sha256': hashlib.sha256(b'abc').hexdigest(),
            }]}]
            files, status = vnvkr_output.build_runtime_mods(DummyInstallation(), catalog, spec, stage, set())
            self.assertEqual((stage / 'mods/Test Mod/NVSE/Plugins/test.dll').read_bytes(), b'abc')
            self.assertEqual(files[0]['status'], 'runtime_mod_copy')
            self.assertEqual(status['mods_requiring_activation'], ['Test Mod'])
            self.assertEqual(status['plugins_requiring_activation'], ['Test.esp'])

    def test_enabled_runtime_mod_needs_no_mod_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = root / 'catalog'
            stage = root / 'stage'
            catalog.mkdir()
            stage.mkdir()
            payload = catalog / 'x.bin'
            payload.write_bytes(b'x')
            spec = [{'mod': 'Already Enabled', 'plugins': [], 'files': [{
                'path': 'x.bin', 'payload': 'x.bin',
                'payload_sha256': hashlib.sha256(b'x').hexdigest(),
            }]}]
            _, status = vnvkr_output.build_runtime_mods(DummyInstallation(['Already Enabled']), catalog, spec, stage, set())
            self.assertEqual(status['mods_requiring_activation'], [])


if __name__ == '__main__':
    unittest.main()
