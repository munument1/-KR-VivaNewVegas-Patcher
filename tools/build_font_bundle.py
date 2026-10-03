"""Create a new catalog with reviewed Korean font assets and tNVSE settings."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vnvkr
import vnvkr_fonts


def main():
    from fontTools.ttLib import TTFont
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-catalog', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    root = Path(__file__).resolve().parents[1]
    candidates = root / 'staging/font-source-candidates'
    desktop = candidates / 'desktop-tnvse'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.font-bundle-', dir=args.output.parent) as tmp:
        stage = Path(tmp) / 'catalog'
        shutil.copytree(args.base_catalog, stage)
        payload_dir = stage / 'font-payloads'
        if payload_dir.exists():
            shutil.rmtree(payload_dir)
        payload_dir.mkdir()

        def store(name, raw):
            path = payload_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            return {'payload': path.relative_to(stage).as_posix(), 'payload_sha256': vnvkr.sha256(path)}

        fonts = [
            ('Pretendard-Bold.ttf', desktop / 'Pretendard-Bold.ttf'),
            ('NanumSquareEB.ttf', desktop / 'NanumSquareEB.ttf'),
            ('TmonMonsorI.ttf', desktop / 'TmonMonsorI.ttf'),
            ('NeoDunggeunmoPro-Regular.ttf', desktop / 'NeoDunggeunmoPro-Regular.ttf'),
        ]
        assets = []
        for name, source in fonts:
            with TTFont(source) as font:
                if not all(code in font.getBestCmap() for code in range(0xAC00, 0xD7A4)):
                    raise ValueError(f'Incomplete Korean face: {name}')
            assets.append({'path': 'NVSE/plugins/fonts/' + name, **store(name, source.read_bytes())})
        for name, source in [
            ('Pretendard-LICENSE.txt', desktop / 'Pretendard-LICENSE.txt'),
            ('NeoDunggeunmoPro-LICENSE.txt', desktop / 'NeoDunggeunmoPro-LICENSE.txt'),
            ('NAVER-font-license.html', candidates / 'NanumSquare/NAVER-license-source.html'),
            ('TMON-author-license.html', candidates / 'source-pages/tmon-author.html'),
            ('TMON-license-notice.html', candidates / 'source-pages/tmon.html'),
        ]:
            assets.append({'path': 'NVSE/plugins/fonts/licenses/' + name, **store(name, source.read_bytes())})
        attribution = ('Font sources and attribution\n\n'
                       'Pretendard Bold: Kil Hyung-jin / Pretendard contributors. SIL OFL 1.1; see Pretendard-LICENSE.txt.\n'
                       'https://github.com/orioncactus/pretendard\n\n'
                       'NanumSquare ExtraBold: NAVER Corporation. See NAVER-font-license.html.\n'
                       'https://hangeul.naver.com/fonts/search?f=nanum\n\n'
                       'NeoDunggeunmo Pro: Eunbin Jeong (Dalgona). SIL OFL 1.1; see NeoDunggeunmoPro-LICENSE.txt.\n'
                       'https://github.com/neodgm/neodgm-pro\n\n'
                       'TmonMonsori Black: TICKETMONSTER / FONTRIX Inc.\n'
                       'See TMON-author-license.html and TMON-license-notice.html.\n'
                       'TMON uses its own published terms; do not assume a generic OFL license.\n\n'
                       'No Monofonto font software or tNVSE DLL is included.\n')
        assets.append({'path': 'NVSE/plugins/fonts/FONT_SOURCES.txt',
                       **store('FONT_SOURCES.txt', attribution.encode('utf-8'))})
        xml = ET.parse(desktop / 'tnvse_fonts.xml')
        container = xml.getroot().find('fonts')
        if container is None:
            raise ValueError('Desktop tNVSE font config has no <fonts> node')
        for parent in container.iter():
            for child in list(parent):
                if child.tag == 'fallback' and not child.get('path'):
                    parent.remove(child)
        configured = [node for node in container.findall('font') if node.get('id') in {'1','2','3','4','5','6','7','8'}]
        if {node.get('id') for node in configured} != {'1','2','3','4','5','6','7','8'}:
            raise ValueError('Desktop tNVSE font config is missing a managed slot')
        slot2 = next(node for node in configured if node.get('id') == '2')
        slot42 = deepcopy(slot2)
        slot42.set('id', '42')
        slot42.set('pixelSize', '20')
        container.append(slot42)
        ET.indent(xml, space='  ')
        xml_entry = store('tnvse_fonts.xml', ET.tostring(xml.getroot(), encoding='utf-8', xml_declaration=True))
        ini_overrides = {'FreeTypeFont': {'bEnableFreeTypeFontRendering': '1',
                                          'bEnableFreeTypeFontRenderingLog': '0'},
                         'Multibyte': {'bEnableMultibyteFontHook': '1', 'uiEncoding': '4', 'bUTF8': '1'},
                         'Dictionary': {'bEnableDictionaryTranslation': '0',
                                        'bDisableDictionaryTranslationInConsole': '0',
                                        'bEnableDictionaryTranslationLog': '0',
                                        'bEnableMuxQuestPromptTranslation': '0',
                                        'bEnableDictionaryPerkDescriptionTranslation': '0',
                                        'bEnableDictionaryItemEffectTranslation': '0',
                                        'bEnableDictionaryMultiplierTextTranslation': '0',
                                        'bEnableDictionaryWildcardTranslation': '0',
                                        'bEnableDictionaryRegexTranslation': '0',
                                        'bEnableDictionaryMixedSourceTranslation': '0',
                                        'bEnableDictionaryBeforeLinebreakTranslation': '0',
                                        'bEnableDictionaryShrinkFuzzyTranslation': '0',
                                        'bEnableDictionaryTrimBypassFuzzyTranslation': '0'}}
        ini_text = (desktop / 'tnvse.ini').read_text(encoding='utf-8')
        ini_entry = store('tnvse.ini', vnvkr_fonts.merge_ini(ini_text, ini_overrides).encode('utf-8'))
        metadata = vnvkr.read_json(stage / 'catalog.json')
        metadata['font_bundle'] = {'default_mod': 'VNV Korean Fonts - tNVSE', 'ini': ini_entry,
            'xml': xml_entry, 'assets': assets, 'ini_overrides': ini_overrides}
        vnvkr.write_json(stage / 'catalog.json', metadata)
        stage.rename(args.output)
    print(f'Font catalog prepared: {args.output}')


if __name__ == '__main__':
    main()
