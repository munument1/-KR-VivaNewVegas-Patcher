from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from vnvkr_plugin_text import COMPRESSED, replace_record, write_plugin


def subrecord(name, raw):
    return name.encode('ascii') + struct.pack('<H', len(raw)) + raw


def record(name, fid, body, flags=0):
    payload = struct.pack('<I', len(body)) + zlib.compress(body) if flags & COMPRESSED else body
    return struct.pack('<4sIIIIHH', name.encode('ascii'), len(payload), flags,
                       fid, 0x12345678, 15, 0) + payload


def group(body):
    return b'GRUP' + struct.pack('<I', len(body) + 24) + b'WEAP' + bytes(range(12)) + body


class OriginalByteWriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'Test.esp'
        (self.base / 'Out').mkdir()
        self.target = self.base / 'Out/Test.esp'
        self.update = {'owner': 'test.esp', 'id': '000123', 'signature': 'WEAP',
                       'field': 'FULL', 'path': 'FULL', 'source': 'Gun', 'dest': '권총'}

    def test_only_approved_string_and_sizes_change(self):
        models = (subrecord('MWD4', b'silencer.nif\0') + subrecord('MWD3', b'extended.nif\0')
                  + subrecord('WNM4', struct.pack('<I', 0x1234))
                  + subrecord('WNM3', struct.pack('<I', 0x5678)))
        inventory = subrecord('CNTO', struct.pack('<II', 90, 2)) + subrecord('CNTO', struct.pack('<II', 10, 1))
        untouched = record('CONT', 0x124, inventory)
        original_body = subrecord('FULL', b'Gun\0') + models
        expected_body = subrecord('FULL', '권총\0'.encode('utf-8')) + models
        head = record('TES4', 0, subrecord('HEDR', bytes(range(12))))
        original = head + group(group(record('WEAP', 0x123, original_body)) + untouched)
        expected = head + group(group(record('WEAP', 0x123, expected_body)) + untouched)
        self.source.write_bytes(original)
        write_plugin(self.source, self.target, [self.update], [])
        self.assertEqual(self.target.read_bytes(), expected)
        self.assertEqual(self.source.read_bytes(), original)

    def test_compressed_record_and_untouched_record(self):
        body = subrecord('FULL', b'Gun\0') + subrecord('DATA', bytes(range(32)))
        untouched = record('MISC', 0x125, subrecord('FULL', b'Other\0'), COMPRESSED)
        original = record('WEAP', 0x123, body, COMPRESSED) + untouched
        self.source.write_bytes(original)
        write_plugin(self.source, self.target, [self.update], [])
        result = self.target.read_bytes()
        size = struct.unpack_from('<I', result, 4)[0]
        payload = result[24:24 + size]
        expected = subrecord('FULL', '권총\0'.encode('utf-8')) + subrecord('DATA', bytes(range(32)))
        self.assertEqual(zlib.decompress(payload[4:]), expected)
        self.assertEqual(struct.unpack_from('<I', payload)[0], len(expected))
        self.assertEqual(result[24 + size:], untouched)

    def test_extended_subrecord(self):
        original = b'XXXX\x04\0' + struct.pack('<I', 4) + b'FULL\0\0Gun\0'
        expected = b'XXXX\x04\0' + struct.pack('<I', 7) + b'FULL\0\0' + '권총\0'.encode('utf-8')
        self.assertEqual(replace_record(original, [self.update]), expected)

    def test_extended_size_promotion(self):
        update = {**self.update, 'dest': '가' * 22000}
        result = replace_record(subrecord('FULL', b'Gun\0'), [update])
        self.assertEqual(result[:6], b'XXXX\x04\0')
        self.assertEqual(struct.unpack_from('<I', result, 6)[0], 66001)
        self.assertEqual(result[16:], ('가' * 22000 + '\0').encode('utf-8'))

    def test_cp1252_source(self):
        update = {**self.update, 'source': 'Café'}
        result = replace_record(subrecord('FULL', b'Caf\xe9\0'), [update])
        self.assertEqual(result, subrecord('FULL', '권총\0'.encode('utf-8')))

    def test_ambiguous_duplicate_slots_fail_closed(self):
        data = subrecord('FULL', b'Gun\0') * 2
        with self.assertRaises(ValueError):
            replace_record(data, [self.update])
        with self.assertRaises(ValueError):
            replace_record(data, [self.update, {**self.update, 'dest': '소총'}])
        self.assertEqual(replace_record(data, [self.update, self.update]),
                         subrecord('FULL', '권총\0'.encode('utf-8')) * 2)

    def test_no_changes_is_exact_copy(self):
        original = group(record('WEAP', 0x123, subrecord('DATA', bytes(range(32)))))
        self.source.write_bytes(original)
        write_plugin(self.source, self.target, [], [])
        self.assertEqual(self.target.read_bytes(), original)

    def test_missing_slots_and_bad_boundaries_rejected(self):
        with self.assertRaises(ValueError):
            replace_record(subrecord('FULL', b'Other\0'), [self.update])
        with self.assertRaises(ValueError):
            replace_record(b'FULL\x08\0short', [self.update])
        self.source.write_bytes(b'GRUP' + struct.pack('<I', 1000) + bytes(16))
        with self.assertRaises(ValueError):
            write_plugin(self.source, self.target, [], [])

    def test_never_replace_source_or_existing_target(self):
        self.source.write_bytes(record('WEAP', 0x123, subrecord('FULL', b'Gun\0')))
        with self.assertRaises(ValueError):
            write_plugin(self.source, self.source, [self.update], [])
        self.target.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            write_plugin(self.source, self.target, [self.update], [])
        self.assertEqual(self.target.read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
