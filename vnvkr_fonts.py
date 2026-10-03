"""Merge a bundled font configuration into an isolated manual-copy Output."""
from copy import deepcopy
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import vnvkr
from tools.loose_translation import decode


def merge_ini(text, overrides):
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines(keepends=True)
    section = ''
    found = set()
    lookup = {(s.casefold(), k.casefold()): str(value)
              for s, values in overrides.items() for k, value in values.items()}
    result = []
    for line in lines:
        header = re.match(r'^\s*\[([^]]+)\]', line)
        if header:
            section = header[1].casefold()
        match = re.match(r'^(\s*([^;#=\s][^=]*?)\s*=\s*)([^;\r\n]*)(;[^\r\n]*)?(\r?\n)?$', line)
        if match:
            identity = (section, match[2].strip().casefold())
            if identity in lookup:
                found.add(identity)
                line = match[1] + lookup[identity] + (' ' + match[4] if match[4] else '') + (match[5] or '')
        result.append(line)
    # Repeating a section is supported by Windows INI consumers inconsistently;
    # insert absent keys into the existing section instead.
    for section_name, values in overrides.items():
        missing = [f'{key} = {value}{newline}' for key, value in values.items()
                   if (section_name.casefold(), key.casefold()) not in found]
        if not missing:
            continue
        start = next((i for i, line in enumerate(result)
                      if re.match(r'^\s*\[' + re.escape(section_name) + r'\]\s*(?:;.*)?$', line.strip(), re.I)), None)
        if start is None:
            if result and not result[-1].endswith(('\n', '\r')):
                result[-1] += newline
            result.extend([newline, f'[{section_name}]{newline}', *missing])
        else:
            end = next((i for i in range(start + 1, len(result)) if re.match(r'^\s*\[', result[i])), len(result))
            if end and not result[end - 1].endswith(('\n', '\r')):
                result[end - 1] += newline
            result[end:end] = missing
    return ''.join(result)


def parse_xml(raw):
    return ET.fromstring(raw, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))


def merge_xml(current, planned):
    root, patch = parse_xml(current), parse_xml(planned)
    if root.tag != 'tNVSE' or patch.tag != 'tNVSE':
        raise ValueError('Unexpected tNVSE font XML root')
    fonts = root.find('fonts')
    if fonts is None:
        fonts = ET.SubElement(root, 'fonts')
    managed_tags = {'face', 'fallback', 'singleByte', 'doubleByte', 'glow', 'outline', 'shadow'}
    for wanted in patch.findall('fonts/font'):
        matches = [node for node in fonts.findall('font') if node.get('id') == wanted.get('id')]
        merged = deepcopy(matches[-1]) if matches else ET.Element('font')
        merged.attrib.update(wanted.attrib)
        for child in list(merged):
            if child.tag in managed_tags:
                merged.remove(child)
        merged.extend(deepcopy(list(wanted)))
        for old in matches:
            fonts.remove(old)
        fonts.append(merged)
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def payload(catalog_dir, item):
    source = vnvkr.contained(catalog_dir, item['payload'])
    if vnvkr.sha256(source) != item['payload_sha256']:
        raise ValueError(f'Font payload integrity mismatch: {item["payload"]}')
    return source


def build_fonts(installation, catalog_dir, spec, stage, seen):
    ini_path, xml_path = 'NVSE/plugins/tnvse.ini', 'NVSE/plugins/tnvse_fonts.xml'
    default_mod = vnvkr.virtual_path(spec['default_mod'])
    if '/' in default_mod:
        raise ValueError('Invalid font mod folder')
    # Prefer the active font configuration's provider; otherwise the INI's.
    provider = None
    for path in (xml_path, ini_path):
        chain = installation.providers.get(path.casefold())
        if chain:
            physical = Path(chain[-1]['physical']).resolve()
            if physical.is_relative_to(installation.mods):
                provider = physical.relative_to(installation.mods).parts[0]
                break
    provider = provider or default_mod
    prefix = f'mods/{provider}/'
    new_mod = provider not in installation.mods_enabled
    files = []

    def write(relative, raw, kind, source=None):
        relative = vnvkr.virtual_path(relative)
        if relative.casefold() in seen:
            raise ValueError(f'Duplicate physical output: {relative}')
        seen.add(relative.casefold())
        target = vnvkr.contained(stage, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        row = {'path': relative.split('/', 2)[-1], 'output_path': relative,
               'provider': provider, 'status': kind, 'output_sha256': vnvkr.sha256(target)}
        if source:
            row['source_sha256'] = vnvkr.sha256(source)
        files.append(row)

    font_assets = {vnvkr.virtual_path(item['path']).casefold() for item in spec['assets']}
    planned = payload(catalog_dir, spec['xml']).read_bytes()
    patch_root = parse_xml(planned)
    ids = [font.get('id') for font in patch_root.findall('fonts/font')]
    if set(ids) != {'1', '2', '3', '4', '5', '6', '7', '8', '42'} or len(ids) != 9:
        raise ValueError('Invalid managed Korean font slots')
    for face in patch_root.iter():
        if face.tag not in {'face', 'fallback'}:
            continue
        path = face.get('path', '').replace('\\', '/')
        if not path.startswith('Data/') or path[5:].casefold() not in font_assets:
            raise ValueError('Font XML refers to an unbundled face')
    for config_path, entry, kind in ((ini_path, spec['ini'], 'font_ini_merged'),
                                     (xml_path, spec['xml'], 'font_xml_merged')):
        chain = installation.providers.get(config_path.casefold())
        source = Path(chain[-1]['physical']) if chain else None
        before = vnvkr.sha256(source) if source else None
        baseline = source or payload(catalog_dir, entry)
        payload(catalog_dir, entry)
        if kind == 'font_ini_merged':
            text, encoding = decode(baseline)
            raw = merge_ini(text, spec['ini_overrides']).encode(encoding)
        else:
            raw = merge_xml(baseline.read_bytes(), planned)
        if source and source.resolve().is_relative_to(installation.root):
            relative = source.resolve().relative_to(installation.root).as_posix()
        else:
            relative = prefix + config_path
        write(relative, raw, kind, source)
        if source and vnvkr.sha256(source) != before:
            raise ValueError('tNVSE source changed during font generation')
    for item in spec['assets']:
        write(prefix + vnvkr.virtual_path(item['path']), payload(catalog_dir, item).read_bytes(), 'font_asset')
    note = ('VNV Korean Fonts - tNVSE\n\n'
            'Output의 mods 폴더를 VNV MO2 폴더로 복사하세요.\n'
            + (f'MO2를 새로 고침하고 "{provider}" 모드를 체크한 뒤 tNVSE보다 아래에 배치하세요.\n' if new_mod else '')
            + 'tNVSE 71 및 선행 모드는 별도로 설치해야 합니다. 이 묶음에는 tNVSE DLL이 없습니다.\n'
            '처음 실행할 때 폰트 준비가 완료될 때까지 기다리세요.\n'
            '대화/HUD/Pip-Boy/터미널/MCM/Stewie 메뉴 표시 검증은 아직 수행하지 않았습니다.\n')
    write(prefix + 'NVSE/plugins/fonts/VNV_KR_FONT_README.txt', note.encode('utf-8-sig'), 'font_instructions')
    tnvse_installed = any(path.is_file() for path in
                          [installation.data / 'NVSE/plugins/tnvse.dll',
                           installation.overwrite / 'NVSE/plugins/tnvse.dll',
                           *(installation.mods / name / 'NVSE/plugins/tnvse.dll'
                             for name in installation.mods_enabled)])
    return files, {'mod': provider, 'requires_activation': new_mod,
                   'tnvse_installed': tnvse_installed, 'tnvse_dll_included': False,
                   'required_tnvse_version': 71, 'game_validation': 'not_run', 'slots': ids}
