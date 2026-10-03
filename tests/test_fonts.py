import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import vnvkr
import vnvkr_output


class FontOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mo2 = self.root / 'MO2'
        self.game = self.root / 'Game'
        (self.game / 'Data').mkdir(parents=True)
        (self.game / 'Data/FalloutNV.esm').write_bytes(b'fixture master')
        profile = self.mo2 / 'profiles/Test'
        profile.mkdir(parents=True)
        (self.mo2 / 'ModOrganizer.ini').write_text(
            f'[General]\ngameName=New Vegas\ngamePath={self.game}\nselected_profile=Test\n', encoding='utf-8')
        (profile / 'modlist.txt').write_text('+Installed tNVSE\n', encoding='utf-8')
        (profile / 'plugins.txt').write_text('FalloutNV.esm\n', encoding='utf-8')
        (profile / 'loadorder.txt').write_text('FalloutNV.esm\n', encoding='utf-8')
        self.mod = self.mo2 / 'mods/Installed tNVSE'
        (self.mod / 'NVSE/plugins').mkdir(parents=True)
        self.catalog = self.root / 'catalog'
        self.catalog.mkdir()

        def store(name, raw):
            p = self.catalog / name
            p.write_bytes(raw)
            return {'payload': name, 'payload_sha256': vnvkr.sha256(p)}

        xml = '<tNVSE><fonts>' + ''.join(
            f'<font id="{i}" pixelSize="20"><face path="Data/NVSE/plugins/fonts/KO.ttf"/></font>'
            for i in (1, 2, 3, 4, 5, 6, 7, 8, 42)) + '</fonts></tNVSE>'
        self.spec = {'default_mod': 'VNV Korean Fonts - tNVSE',
                     'ini': store('default.ini', b'[FreeTypeFont]\nbEnableFreeTypeFontRendering=0\n'),
                     'xml': store('fonts.xml', xml.encode()),
                     'assets': [{'path': 'NVSE/plugins/fonts/KO.ttf', **store('KO.ttf', b'fixture font')}],
                     'ini_overrides': {'FreeTypeFont': {'bEnableFreeTypeFontRendering': '1'},
                                       'Multibyte': {'uiEncoding': '4', 'bUTF8': '1'}}}
        vnvkr.write_json(self.catalog / 'catalog.json', {'schema_version': 1, 'files': [], 'font_bundle': self.spec})

    def test_updated_settings_and_extended_fonts_survive_in_output(self):
        ini = self.mod / 'NVSE/plugins/tnvse.ini'
        ini.write_bytes(b'; custom settings\r\n[FreeTypeFont]\r\nbEnableFreeTypeFontRendering=0 ; note\r\n'
                        b'uiFreeTypeFontMemoryCacheMB=256\r\n[Future]\r\naddedOption=keep\r\n')
        xml = self.mod / 'NVSE/plugins/tnvse_fonts.xml'
        xml.write_text('<tNVSE><Future value="keep"/><fonts><!--custom--><font id="1" futureAttr="keep">'
                       '<futureSetting value="keep"/><face path="old.ttf"/></font>'
                       '<font id="89" pixelSize="99"><face path="custom.ttf"/></font></fonts></tNVSE>', encoding='utf-8')
        before = {p: p.read_bytes() for p in self.mo2.rglob('*') if p.is_file()}
        out = self.root / 'Output'
        report = vnvkr_output.build_output(vnvkr.Installation(self.mo2), self.catalog, out)
        merged_ini = (out / 'mods/Installed tNVSE/NVSE/plugins/tnvse.ini').read_text()
        self.assertIn('bEnableFreeTypeFontRendering=1 ; note', merged_ini)
        self.assertIn('uiFreeTypeFontMemoryCacheMB=256', merged_ini)
        self.assertIn('addedOption=keep', merged_ini)
        self.assertIn('uiEncoding = 4', merged_ini)
        merged_xml = ET.parse(out / 'mods/Installed tNVSE/NVSE/plugins/tnvse_fonts.xml').getroot()
        self.assertEqual(merged_xml.find('Future').get('value'), 'keep')
        self.assertEqual(merged_xml.find("fonts/font[@id='89']/face").get('path'), 'custom.ttf')
        self.assertEqual(merged_xml.find("fonts/font[@id='1']").get('futureAttr'), 'keep')
        self.assertEqual(merged_xml.find("fonts/font[@id='1']/futureSetting").get('value'), 'keep')
        self.assertEqual(merged_xml.find("fonts/font[@id='1']/face").get('path'), 'Data/NVSE/plugins/fonts/KO.ttf')
        self.assertFalse(report['fonts']['requires_activation'])
        self.assertTrue(all(p.read_bytes() == raw for p, raw in before.items()))

    def test_absent_tnvse_generates_separate_mod_and_activation_notice(self):
        out = self.root / 'Output'
        report = vnvkr_output.build_output(vnvkr.Installation(self.mo2), self.catalog, out)
        self.assertTrue(report['fonts']['requires_activation'])
        self.assertTrue((out / 'mods/VNV Korean Fonts - tNVSE/NVSE/plugins/fonts/KO.ttf').is_file())
        self.assertFalse(any(out.rglob('*.dll')))
        self.assertFalse((self.mod / 'NVSE/plugins/tnvse.ini').exists())

    def test_tampered_font_publishes_no_output(self):
        (self.catalog / 'KO.ttf').write_bytes(b'tampered')
        out = self.root / 'Output'
        with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
            vnvkr_output.build_output(vnvkr.Installation(self.mo2), self.catalog, out)
        self.assertFalse(out.exists())
        self.assertFalse(out.with_name('Output.report.json').exists())


if __name__ == '__main__':
    unittest.main()
