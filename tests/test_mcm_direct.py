import json
from pathlib import Path
import unittest

import vnvkr
import vnvkr_output


ROOT = Path(__file__).resolve().parents[1]


class MCMDirectMappingTests(unittest.TestCase):
    def test_reviewed_mcm_direct_mapping_file(self):
        spec = vnvkr.read_json(ROOT / 'data/mcm_direct_mappings.json')
        self.assertEqual(spec['schema_version'], 1)
        self.assertEqual(len(spec['files']), 3)
        self.assertEqual(sum(len(item['mappings']) for item in spec['files']), 45)
        keys = set()
        for item in spec['files']:
            self.assertRegex(item['baseline_sha256'], r'^[0-9a-f]{64}$')
            for row in item['mappings']:
                vnvkr_output.check_pair(row['source'], row['dest'])
                key = (item['provider'].casefold(), item['path'].casefold(),
                       row['context'], row['source'])
                self.assertNotIn(key, keys)
                keys.add(key)

    def test_goodies_direct_strings_are_reviewed(self):
        spec = vnvkr.read_json(ROOT / 'data/mcm_direct_mappings.json')
        goodies = next(item for item in spec['files'] if item['path'] == 'MCM/Goodies.json')
        translations = {(row['source'], row['dest']) for row in goodies['mappings']}
        self.assertIn(('Pew Pew Burst Fire', '뿅 뿅 점사'), translations)
        self.assertIn(('The Thorn Performance Mode', '쏜 성능 모드'), translations)
        self.assertIn(('Service Rifle Mod', '제식 소총 개조'), translations)


if __name__ == '__main__':
    unittest.main()
