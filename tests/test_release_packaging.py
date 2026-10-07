import unittest
from pathlib import Path
import tempfile
import vnvkr
from tools.prepare_tnvse_patch import restore_resource_declarations

from tools.prepare_release_package import validate_catalog


class ReleasePackagingTests(unittest.TestCase):
    def test_direct_sst_plugin_is_valid(self):
        catalog = {'files': [{
            'path': 'Goodies.esp',
            'kind': 'plugin-records',
            'mappings': [{'source': 'A', 'dest': '가'}],
        }]}
        self.assertEqual(len(validate_catalog(catalog)), 1)

    def test_fallback_only_plugin_is_valid(self):
        catalog = {'files': [{
            'path': 'Patch.esp',
            'kind': 'plugin-records',
            'mappings': [],
            'fallback_only': True,
        }]}
        self.assertEqual(len(validate_catalog(catalog)), 1)

    def test_plugin_without_sst_or_fallback_is_rejected(self):
        catalog = {'files': [{
            'path': 'Unsafe.esp',
            'kind': 'plugin-records',
            'mappings': [],
        }]}
        with self.assertRaisesRegex(ValueError, 'neither direct SST nor fallback policy'):
            validate_catalog(catalog)

    def test_packaged_runtime_and_texture_declarations_are_restored(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            files = ['runtime-payloads/VNV Korean UI Strings/VNVKR UI Strings.esp',
                     'runtime-payloads/VNV Korean Radio Captions/NVSE/Plugins/MojaveRadioCaptions.dll',
                     'asset-payloads/Textures/terminals/english/test.dds']
            for name in files:
                path = data / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            catalog = {'font_bundle': {'default_mod': 'KR Font'}}
            restore_resource_declarations(data, catalog)
            self.assertEqual(len(catalog['runtime_mods']), 2)
            self.assertEqual(catalog['runtime_mods'][0]['plugins'], ['VNVKR UI Strings.esp'])
            for spec in [*catalog['runtime_mods'], catalog['asset_bundle']]:
                for row in spec['files']:
                    self.assertEqual(vnvkr.sha256(data / row['payload']), row['payload_sha256'])

    def test_missing_runtime_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Missing packaged'):
                restore_resource_declarations(Path(tmp), {'font_bundle': {'default_mod': 'KR Font'}})


if __name__ == '__main__':
    unittest.main()
