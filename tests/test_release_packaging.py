import unittest

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


if __name__ == '__main__':
    unittest.main()
