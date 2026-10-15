import os
import sys

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda"))

from app import strip_exif  # noqa: E402

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"


def segment(marker, payload):
    return b"\xff" + bytes([marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


JFIF = segment(0xE0, b"JFIF\x00\x01\x02\x00\x00\x01\x00\x01\x00\x00")
EXIF = segment(0xE1, b"Exif\x00\x00II*\x00camera-and-gps-data")
XMP = segment(0xE1, b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta/>")
SOS = segment(0xDA, b"\x01\x01\x00\x00\x3f\x00")
SCAN = b"\x12\x34\xff\x00\x56"


def test_removes_exif_segment():
    source = SOI + JFIF + EXIF + SOS + SCAN + EOI
    assert strip_exif(source) == SOI + JFIF + SOS + SCAN + EOI


def test_keeps_non_exif_app1_segment():
    source = SOI + XMP + SOS + SCAN + EOI
    assert strip_exif(source) == source


def test_escaped_ff_bytes_in_scan_data_are_preserved():
    source = SOI + JFIF + SOS + SCAN + EOI
    assert strip_exif(source) == source


def test_removes_exif_between_scans():
    source = SOI + SOS + SCAN + EXIF + SOS + SCAN + EOI
    assert strip_exif(source) == SOI + SOS + SCAN + SOS + SCAN + EOI


def test_rejects_data_that_is_not_a_jpeg():
    with pytest.raises(ValueError):
        strip_exif(b"not a jpeg")


def test_rejects_truncated_segment():
    with pytest.raises(ValueError):
        strip_exif(SOI + b"\xff\xe1\x00\x10abc")
