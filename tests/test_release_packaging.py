import tempfile
import unittest
from pathlib import Path

import vnvkr
from tools.prepare_release_package import prune_koffi_platforms, strip_oversized_verified_deltas


class ReleasePackagingTests(unittest.TestCase):
    def test_oversized_delta_is_omitted_but_record_mappings_remain(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            (data / 'native-deltas').mkdir()
            large = data / 'native-deltas/large.vcdiff'
            small = data / 'native-deltas/small.vcdiff'
            large.write_bytes(b'x' * 20)
            small.write_bytes(b'y' * 4)
            catalog = {
                'schema_version': 1,
                'files': [
                    {
                        'path': 'FalloutNV.esm',
                        'kind': 'plugin-records',
                        'mappings': [{'source': 'A', 'dest': '가'}],
                        'verified_delta': {'payload': 'native-deltas/large.vcdiff'},
                    },
                    {
                        'path': 'Small.esp',
                        'kind': 'plugin-records',
                        'mappings': [{'source': 'B', 'dest': '나'}],
                        'verified_delta': {'payload': 'native-deltas/small.vcdiff'},
                    },
                ],
            }
            vnvkr.write_json(data / 'catalog.json', catalog)

            removed = strip_oversized_verified_deltas(data, limit=10)
            updated = vnvkr.read_json(data / 'catalog.json')

            self.assertEqual([row['path'] for row in removed], ['FalloutNV.esm'])
            self.assertNotIn('verified_delta', updated['files'][0])
            self.assertEqual(updated['files'][0]['mappings'], [{'source': 'A', 'dest': '가'}])
            self.assertIn('verified_delta', updated['files'][1])
            self.assertFalse(large.exists())
            self.assertTrue(small.exists())

    def test_delta_without_fallback_mappings_is_never_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            (data / 'native-deltas').mkdir()
            (data / 'native-deltas/large.vcdiff').write_bytes(b'x' * 20)
            vnvkr.write_json(data / 'catalog.json', {
                'schema_version': 1,
                'files': [{
                    'path': 'Unsafe.esp',
                    'kind': 'plugin-records',
                    'mappings': [],
                    'verified_delta': {'payload': 'native-deltas/large.vcdiff'},
                }],
            })
            with self.assertRaisesRegex(ValueError, 'without record mappings'):
                strip_oversized_verified_deltas(data, limit=10)

    def test_koffi_pruning_keeps_only_windows_x64_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            koffi = Path(temp)
            binaries = koffi / 'build/koffi'
            for platform in ('win32_x64', 'win32_ia32', 'linux_x64', 'darwin_arm64'):
                folder = binaries / platform
                folder.mkdir(parents=True)
                (folder / 'koffi.node').write_bytes(platform.encode())

            removed = prune_koffi_platforms(koffi)

            self.assertEqual(sorted(removed), ['darwin_arm64', 'linux_x64', 'win32_ia32'])
            self.assertTrue((binaries / 'win32_x64/koffi.node').is_file())
            self.assertEqual([p.name for p in binaries.iterdir()], ['win32_x64'])


if __name__ == '__main__':
    unittest.main()
