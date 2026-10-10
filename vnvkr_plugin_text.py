"""Write approved TES4 strings into original bytes, without xEdit serialization."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import struct
import zlib

U32 = struct.Struct('<I')
U16 = struct.Struct('<H')
COMPRESSED = 0x00040000


def replace_record(data, updates):
    """Require exact field/source/count correspondence; ambiguous slots fail closed."""
    replacements = defaultdict(list)
    for row in updates:
        replacements[(row['field'].encode('ascii'), row['source'])].append(row['dest'])
    for destinations in replacements.values():
        if len(set(destinations)) != 1:
            raise ValueError('Different destinations for indistinguishable binary string slots')
    matched = Counter()
    result = bytearray()
    offset = 0
    while offset < len(data):
        start = offset
        if offset + 6 > len(data):
            raise ValueError('Truncated subrecord header')
        field = data[offset:offset + 4]
        size = U16.unpack_from(data, offset + 4)[0]
        offset += 6
        extended = field == b'XXXX'
        if extended:
            if size != 4 or offset + 10 > len(data):
                raise ValueError('Invalid extended subrecord header')
            size = U32.unpack_from(data, offset)[0]
            offset += 4
            field = data[offset:offset + 4]
            offset += 6
        end = offset + size
        if end > len(data):
            raise ValueError('Truncated subrecord payload')
        raw = data[offset:end]
        candidates = []
        for key in replacements:
            code, source = key
            if code != field:
                continue
            encodings = [source.encode('utf-8') + b'\0']
            try:
                encodings.append(source.encode('cp1252') + b'\0')
            except UnicodeEncodeError:
                pass
            if raw in encodings:
                candidates.append(key)
        if len(candidates) > 1:
            raise ValueError('Ambiguous binary source encoding')
        if not candidates:
            result.extend(data[start:end])
        else:
            key = candidates[0]
            matched[key] += 1
            dest = replacements[key][0].encode('utf-8') + b'\0'
            if extended:
                header = bytearray(data[start:offset])
                U32.pack_into(header, 6, len(dest))
                result.extend(header)
            elif len(dest) > 65535:
                result.extend(b'XXXX' + U16.pack(4) + U32.pack(len(dest)))
                result.extend(field + U16.pack(0))
            else:
                result.extend(field + U16.pack(len(dest)))
            result.extend(dest)
        offset = end
    expected = Counter({key: len(rows) for key, rows in replacements.items()})
    if matched != expected:
        raise ValueError('Binary string slots do not exactly match approved native changes')
    return bytes(result)


def write_plugin(source: Path, target: Path, updates, masters):
    """Stream untouched records verbatim; update only string and size bytes."""
    if source.resolve() == target.resolve():
        raise ValueError('Plugin output must not replace its source')
    by_record = defaultdict(list)
    for row in updates:
        identity = row['owner'].casefold(), row['id'].casefold(), row['signature']
        by_record[identity].append(row)
    applied = set()
    owner_names = [name.casefold() for name in masters] + [source.name.casefold()]
    with source.open('rb') as reader, target.open('xb') as writer:
        file_end = source.stat().st_size

        def copy(size):
            while size:
                chunk = reader.read(min(size, 1024 * 1024))
                if not chunk:
                    raise ValueError('Truncated plugin data')
                writer.write(chunk)
                size -= len(chunk)

        def walk(end):
            while reader.tell() < end:
                header = reader.read(24)
                if len(header) != 24:
                    raise ValueError('Truncated record/group header')
                signature = header[:4]
                size = U32.unpack_from(header, 4)[0]
                if signature == b'GRUP':
                    if size < 24 or reader.tell() + size - 24 > end:
                        raise ValueError('Invalid group size')
                    group_end = reader.tell() + size - 24
                    position = writer.tell()
                    writer.write(header)
                    walk(group_end)
                    final = writer.tell()
                    writer.seek(position + 4)
                    writer.write(U32.pack(final - position))
                    writer.seek(final)
                    continue
                if reader.tell() + size > end:
                    raise ValueError('Record crosses its containing group')
                fid = U32.unpack_from(header, 12)[0]
                owner_index = fid >> 24
                owner = owner_names[owner_index] if owner_index < len(owner_names) else None
                identity = owner, f'{fid & 0xffffff:06x}', signature.decode('ascii')
                rows = by_record.get(identity)
                if not rows:
                    writer.write(header)
                    copy(size)
                    continue
                if identity in applied:
                    raise ValueError('Duplicate changed record identity')
                applied.add(identity)
                raw = reader.read(size)
                flags = U32.unpack_from(header, 8)[0]
                if flags & COMPRESSED:
                    if len(raw) < 4:
                        raise ValueError('Truncated compressed record')
                    data = zlib.decompress(raw[4:])
                    if len(data) != U32.unpack_from(raw)[0]:
                        raise ValueError('Compressed record length mismatch')
                    changed = replace_record(data, rows)
                    payload = U32.pack(len(changed)) + zlib.compress(changed)
                else:
                    payload = replace_record(raw, rows)
                updated_header = bytearray(header)
                U32.pack_into(updated_header, 4, len(payload))
                writer.write(updated_header)
                writer.write(payload)
            if reader.tell() != end:
                raise ValueError('Plugin boundary mismatch')

        walk(file_end)
        if applied != by_record.keys():
            raise ValueError('Native changes refer to missing original records')
