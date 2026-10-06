"""SSU8/SSU9 xTranslator SST reader used by the VNV Korean patcher.

The binary layout handling is adapted from the user's SST2XML project.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
import struct


class SstParseError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class SstEntry:
    offset: int
    form_id: int
    rec: str
    layout: str
    rec_id: int
    rec_id_max: int
    string_id: int
    flags: int
    source: str
    dest: str
    tail: bytes


@dataclasses.dataclass(frozen=True)
class SstFile:
    format: str
    plugins: list[str]
    entries: list[SstEntry]


def _read_u16(data: bytes, pos: int) -> tuple[int, int]:
    if pos + 2 > len(data):
        raise SstParseError(f"unexpected EOF while reading uint16 at 0x{pos:X}")
    return struct.unpack_from("<H", data, pos)[0], pos + 2


def _read_u32(data: bytes, pos: int) -> tuple[int, int]:
    if pos + 4 > len(data):
        raise SstParseError(f"unexpected EOF while reading uint32 at 0x{pos:X}")
    return struct.unpack_from("<I", data, pos)[0], pos + 4


def _decode_utf16le(raw: bytes, pos: int) -> str:
    try:
        return raw.decode("utf-16le").rstrip("\x00")
    except UnicodeDecodeError as exc:
        raise SstParseError(f"invalid UTF-16LE text near 0x{pos:X}: {exc}") from exc


def _is_record_signature(raw: bytes) -> bool:
    if len(raw) != 8:
        return False
    return all(
        0x30 <= ch <= 0x39 or 0x41 <= ch <= 0x5A or ch in (0x2A, 0x5F)
        for ch in raw
    )


def _record_layout_at(data: bytes, pos: int) -> str | None:
    if pos + 31 <= len(data) and _is_record_signature(data[pos + 4 : pos + 12]):
        return "standard"
    if pos + 35 <= len(data) and _is_record_signature(data[pos + 8 : pos + 16]):
        return "extended"
    return None


def _looks_like_record(data: bytes, pos: int) -> bool:
    return _record_layout_at(data, pos) is not None


def _find_record_start(data: bytes, pos: int) -> int:
    for candidate in range(pos, min(len(data), pos + 64)):
        if _looks_like_record(data, candidate):
            return candidate
    raise SstParseError(f"expected SST record at 0x{pos:X}")


def read_sst(path: Path) -> SstFile:
    data = path.read_bytes()
    plugins: list[str] = []
    if len(data) < 14 or data[:3] != b"SSU" or data[3] not in (ord("8"), ord("9")):
        raise SstParseError("not a supported SSU8/SSU9 SST file")

    file_format = data[:4].decode("ascii")
    if file_format == "SSU9":
        pos = 5
        plugin_count, pos = _read_u32(data, pos)
        for _ in range(plugin_count):
            length, pos = _read_u32(data, pos)
            if pos + length > len(data):
                raise SstParseError(f"plugin name length exceeds file size at 0x{pos:X}")
            plugins.append(_decode_utf16le(data[pos : pos + length], pos))
            pos += length
        if pos < len(data):
            pos = _find_record_start(data, pos)
    else:
        pos = _find_record_start(data, 14)

    entries: list[SstEntry] = []
    while pos < len(data):
        layout = _record_layout_at(data, pos)
        if layout is None:
            raise SstParseError(f"expected SST record at 0x{pos:X}")

        offset = pos
        form_id, pos = _read_u32(data, pos)
        if layout == "extended":
            _, pos = _read_u32(data, pos)

        rec_raw = data[pos : pos + 8]
        if not _is_record_signature(rec_raw):
            raise SstParseError(f"invalid REC signature at 0x{pos:X}")
        rec = rec_raw.decode("ascii")
        pos += 8

        rec_id, pos = _read_u16(data, pos)
        rec_id_max, pos = _read_u16(data, pos)
        string_id, pos = _read_u32(data, pos)
        flags, pos = _read_u16(data, pos)

        source_len, pos = _read_u32(data, pos)
        if pos + source_len > len(data):
            raise SstParseError(f"source length exceeds file size at 0x{offset:X}")
        source = _decode_utf16le(data[pos : pos + source_len], pos)
        pos += source_len

        dest_len, pos = _read_u32(data, pos)
        if pos + dest_len > len(data):
            raise SstParseError(f"dest length exceeds file size at 0x{offset:X}")
        dest = _decode_utf16le(data[pos : pos + dest_len], pos)
        pos += dest_len

        tail = b""
        if pos + 5 <= len(data) and _looks_like_record(data, pos + 5):
            tail = data[pos : pos + 5]
            pos += 5
        elif pos + 5 == len(data):
            tail = data[pos : pos + 5]
            pos += 5

        entries.append(SstEntry(
            offset=offset,
            form_id=form_id,
            rec=rec,
            layout=layout,
            rec_id=rec_id,
            rec_id_max=rec_id_max,
            string_id=string_id,
            flags=flags,
            source=source,
            dest=dest,
            tail=tail,
        ))

    return SstFile(format=file_format, plugins=plugins, entries=entries)


def custom_text_mapping(sst: SstFile) -> dict[str, str]:
    """Return unambiguous source->dest mappings from custom TXT SST entries."""
    mapping: dict[str, str] = {}
    conflicts: dict[str, set[str]] = {}
    for entry in sst.entries:
        if entry.rec != "********":
            continue
        if not entry.source or entry.source == entry.dest:
            continue
        previous = mapping.get(entry.source)
        if previous is None:
            mapping[entry.source] = entry.dest
        elif previous != entry.dest:
            conflicts.setdefault(entry.source, {previous}).add(entry.dest)
    if conflicts:
        sample = next(iter(conflicts.items()))
        raise SstParseError(
            f"ambiguous custom-text SST mapping for {sample[0]!r}: {sorted(sample[1])!r}"
        )
    return mapping
