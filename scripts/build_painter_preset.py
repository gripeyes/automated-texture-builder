#!/usr/bin/env python3
"""Build the Painter 12.1 preset used by Automated Texture Builder."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct


SOURCE_DEFAULT = Path(
    "/Users/j7s/coding/personal-biased-ocios/texture-tools/presets/"
    "MoonRay + Arnold - Linear Rec2020 VFX.spexp"
)
ROUGHNESS_ID = bytes.fromhex("000000030000000080")
SPECULAR_WEIGHT_ID = bytes.fromhex("000000030000010000")  # ChannelType value 16
ANISOTROPY_ID = bytes.fromhex("000000030000000100")  # ChannelType value 8


def u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def put_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def array_info(data: bytes | bytearray) -> tuple[int, int, int, int]:
    marker = b"\x04\x00\x00\x00maps\x13"
    start = data.find(marker)
    if start < 0:
        raise ValueError("Painter map array was not found")
    tag = start + len(marker) - 1
    return tag, u32(data, tag + 1), tag + 5, u32(data, tag + 5)


def segments(data: bytes | bytearray) -> list[tuple[int, int]]:
    _, end, count_offset, count = array_info(data)
    cursor = count_offset + 4
    result = []
    for _ in range(count):
        if data[cursor : cursor + 2] != b"\x12\x00":
            raise ValueError(f"Bad map wrapper at {cursor}")
        segment_end = u32(data, cursor + 2)
        result.append((cursor, segment_end))
        cursor = segment_end
    if cursor != end:
        raise ValueError("Map array endpoint mismatch")
    return result


def next_uid(data: bytes | bytearray) -> int:
    marker = b"\x03\x00\x00\x00uid\x0c"
    values = []
    cursor = 0
    while True:
        cursor = data.find(marker, cursor)
        if cursor < 0:
            break
        values.append(struct.unpack_from("<Q", data, cursor + len(marker))[0])
        cursor += len(marker) + 8
    return max(values) + 1


def relocate(segment: bytes, old_start: int, new_start: int) -> bytearray:
    result = bytearray(segment)
    delta = new_start - old_start
    old_channel_marker = b"\x08\x00\x00\x00channels\x11"
    marker = result.find(old_channel_marker)
    if marker < 0:
        raise ValueError("Channel array was not found")
    endpoint_offset = marker + len(old_channel_marker)
    old_endpoint = u32(result, endpoint_offset)
    put_u32(result, endpoint_offset, old_endpoint + delta)
    wrapper = result.find(b"\x14\x00" + struct.pack("<I", old_endpoint))
    if wrapper < 0:
        raise ValueError("Channel wrapper was not found")
    put_u32(result, wrapper + 2, old_endpoint + delta)
    put_u32(result, 2, new_start + len(result))
    return result


def replace_path(segment: bytearray, old: bytes, new: bytes) -> bytearray:
    marker = b"\x04\x00\x00\x00path\x10"
    offset = segment.find(marker)
    if offset < 0:
        raise ValueError("Output path was not found")
    length_offset = offset + len(marker)
    length = u32(segment, length_offset)
    value_offset = length_offset + 4
    value = bytes(segment[value_offset : value_offset + length])
    replacement = value.replace(old, new, 1)
    if replacement == value:
        raise ValueError(f"Path token {old!r} was not found")
    segment[value_offset : value_offset + length] = replacement
    put_u32(segment, length_offset, len(replacement))
    return segment


def build(source: bytes) -> bytes:
    original_segments = segments(source)
    rough = next(bounds for bounds in original_segments if b"_Roughness(" in source[bounds[0] : bounds[1]])
    spec = next(bounds for bounds in original_segments if b"_SpecularLevel(" in source[bounds[0] : bounds[1]])
    emitted = next(bounds for bounds in original_segments if b"_Emissive(" in source[bounds[0] : bounds[1]])

    # Keep everything before emission byte-for-byte. Replace legacy SpecularLevel
    # with the Painter 12.1 SpecularWeight channel at the emission slot.
    prefix = bytearray(source[: emitted[0]])
    spec_segment = relocate(source[spec[0] : spec[1]], spec[0], len(prefix))
    if bytes.fromhex("000000030002000000") not in spec_segment:
        raise ValueError("Legacy SpecularLevel identifier was not found")
    spec_segment = bytearray(spec_segment.replace(bytes.fromhex("000000030002000000"), SPECULAR_WEIGHT_ID, 1))
    spec_segment = replace_path(spec_segment, b"_SpecularLevel(", b"_SpecularWeight(")
    put_u32(spec_segment, 2, len(prefix) + len(spec_segment))
    prefix.extend(spec_segment)

    # Clone the one-channel roughness output as specular anisotropy.
    aniso = relocate(source[rough[0] : rough[1]], rough[0], len(prefix))
    if ROUGHNESS_ID not in aniso:
        raise ValueError("Roughness identifier was not found")
    aniso = bytearray(aniso.replace(ROUGHNESS_ID, ANISOTROPY_ID, 1))
    aniso = replace_path(aniso, b"_Roughness(", b"_Anisotropy(")
    uid_marker = b"\x03\x00\x00\x00uid\x0c"
    uid_at = aniso.rfind(uid_marker)
    struct.pack_into("<Q", aniso, uid_at + len(uid_marker), next_uid(source))
    put_u32(aniso, 2, len(prefix) + len(aniso))
    prefix.extend(aniso)

    # Preserve root fields after the original map array and repair array metadata.
    _, old_array_end, count_offset, old_count = array_info(source)
    prefix.extend(source[old_array_end:])
    tag, _, new_count_offset, _ = array_info(prefix)
    put_u32(prefix, tag + 1, len(prefix) - len(source[old_array_end:]))
    put_u32(prefix, new_count_offset, old_count)  # - emission + anisotropy = unchanged
    parsed = segments(prefix)
    if len(parsed) != old_count:
        raise ValueError("Generated preset did not validate")
    required = [b"_BaseColor(", b"_Metalness(", b"_Roughness(", b"_Normal(", b"_Height(", b"_SpecularWeight(", b"_Anisotropy("]
    if not all(token in prefix for token in required) or b"_Emissive(" in prefix:
        raise ValueError("Generated material channel set is incomplete")
    return bytes(prefix)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source.expanduser().read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
