"""Prepare the confirmed CP949 key-prompt fix; retain dynamic bindings.

Only sOr and sPCControlsTextPrefix are changed. Copy the latter override
from the installed FalloutNV.esm so no record identity is guessed.
"""
from pathlib import Path
import argparse
import struct

U32 = struct.Struct('<I')
U16 = struct.Struct('<H')
VALUES = {'sOr': '또는', 'sPCControlsTextPrefix': '누르기'}
# Exact FalloutNV.esm 000ABE4A override used in the successful local test.
PREFIX_RECORD = bytes.fromhex('474d535429000000000000004abe0a00143e24000e000100'
    '454449441600735043436f6e74726f6c735465787450726566697800'
    '444154410700b4a9b8a3b1e200')


def fields(raw):
    offset = 0
    while offset < len(raw):
        size = U16.unpack_from(raw, offset + 4)[0]
        yield raw[offset:offset+4], raw[offset+6:offset+6+size]
        offset += 6 + size
    if offset != len(raw):
        raise ValueError('Invalid subrecord size')


def editor_id(record):
    return dict(fields(record[24:])).get(b'EDID', b'').rstrip(b'\0').decode('ascii')


def convert(record, key):
    if U32.unpack_from(record, 8)[0] & 0x40000:
        raise ValueError('Unexpected compressed GMST')
    body = bytearray()
    for tag, value in fields(record[24:]):
        if tag == b'DATA':
            allowed = [VALUES[key].encode('utf-8') + b'\0']
            if key == 'sPCControlsTextPrefix':
                allowed.append(b'\0')  # Nuclear Sunset v1.0.2
            if value not in allowed:
                raise ValueError(f'Unexpected original value for {key}')
            value = VALUES[key].encode('cp949') + b'\0'
        body.extend(tag + U16.pack(len(value)) + value)
    header = bytearray(record[:24])
    U32.pack_into(header, 4, len(body))
    return bytes(header + body)


def source_prefix(path):
    found = []
    with path.open('rb') as f:
        end = path.stat().st_size
        while f.tell() < end:
            header = f.read(24)
            size = U32.unpack_from(header, 4)[0]
            if header[:4] == b'GRUP':
                continue
            if header[:4] != b'GMST':
                f.seek(size, 1)
                continue
            record = header + f.read(size)
            if editor_id(record) == 'sPCControlsTextPrefix':
                found.append(record)
    if len(found) != 1 or U32.unpack_from(found[0], 12)[0] >> 24:
        raise ValueError('Expected unique FalloutNV-owned prefix record')
    return convert(found[0], 'sPCControlsTextPrefix')


def prepare(plugin, master, output):
    original = plugin.read_bytes()
    prefix = source_prefix(master) if master else PREFIX_RECORD
    has_prefix = b'sPCControlsTextPrefix\0' in original
    header_fields = dict(fields(original[24:24 + U32.unpack_from(original, 4)[0]]))
    if b'FalloutNV.esm\0' not in original[:24 + U32.unpack_from(original, 4)[0]]:
        raise ValueError('FalloutNV.esm master missing')
    # Inserted override uses master slot 0, matching the confirmed VNV bundle.
    masters = [v for k, v in fields(original[24:24 + U32.unpack_from(original, 4)[0]]) if k == b'MAST']
    if not has_prefix and masters[0] != b'FalloutNV.esm\0':
        raise ValueError('Unexpected FalloutNV.esm master slot')
    changed, added = 0, 0

    def walk(data):
        nonlocal changed, added
        result = bytearray()
        offset = 0
        while offset < len(data):
            header = bytearray(data[offset:offset+24])
            size = U32.unpack_from(header, 4)[0]
            tag = header[:4]
            if tag == b'GRUP':
                body = walk(data[offset+24:offset+size])
                if not has_prefix and header[8:12] == b'GMST' and U32.unpack_from(header, 12)[0] == 0:
                    body += prefix
                    added += 1
                U32.pack_into(header, 4, 24 + len(body))
                result.extend(header + body)
                offset += size
                continue
            record = data[offset:offset+24+size]
            if tag == b'GMST':
                key = editor_id(record)
                if key in VALUES:
                    record = convert(record, key)
                    changed += 1
            elif tag == b'TES4':
                body = bytearray()
                for field, value in fields(record[24:]):
                    if field == b'HEDR':
                        value = bytearray(value)
                        U32.pack_into(value, 4, U32.unpack_from(value, 4)[0] + int(not has_prefix))
                    body.extend(field + U16.pack(len(value)) + value)
                record = bytes(header + body)
            result.extend(record)
            offset += 24 + size
        if offset != len(data):
            raise ValueError('Invalid record/group size')
        return bytes(result)

    revised = walk(original)
    if (changed, added) != ((2, 0) if has_prefix else (1, 1)):
        raise ValueError(f'Unexpected edits: {changed}, {added}')
    # Reparse and compare every other complete record byte-for-byte.
    def records(data):
        result = {}
        offset = 0
        while offset < len(data):
            size = U32.unpack_from(data, offset+4)[0]
            tag = data[offset:offset+4]
            if tag == b'GRUP':
                result.update(records(data[offset+24:offset+size]))
                offset += size
            else:
                record = data[offset:offset+24+size]
                result[(tag, U32.unpack_from(record, 12)[0])] = record
                offset += 24+size
        return result
    old, new = records(original), records(revised)
    assert len(new) == len(old) + int(not has_prefix)
    for key, record in old.items():
        if key[0] == b'TES4' or key[0] == b'GMST' and editor_id(record) in VALUES:
            continue
        assert new[key] == record
    for record in new.values():
        if record[:4] == b'GMST' and editor_id(record) in VALUES:
            key = editor_id(record)
            assert dict(fields(record[24:]))[b'DATA'] == VALUES[key].encode('cp949') + b'\0'
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as f:
        f.write(revised)
    print('PASS: two key-prompt GMST values use CP949; other records preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('plugin', type=Path)
    parser.add_argument('master', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    prepare(args.plugin, args.master, args.output)
