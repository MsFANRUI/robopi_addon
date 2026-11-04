#!/usr/bin/env python3
"""Offline checks for the packaged PMIC candidates and serial OTA framing."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pmic_ota", ROOT / "scripts/robopi-pmic-ota.py")
OTA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OTA)


class FakePort:
    def __init__(self, bad_ack=False):
        self.rx = bytearray()
        self.commands = []
        self.bad_ack = bad_ack

    def reset_input_buffer(self):
        self.rx.clear()

    def write(self, data):
        command = data.decode("ascii")
        self.commands.append(command)
        if command.startswith("OTA_BEGIN:"):
            self.rx.extend(b"OTA_READY;")
        elif command.startswith("OTA_DATA:"):
            offset, payload = command[9:-1].split(",", 1)
            next_offset = int(offset) + len(bytes.fromhex(payload))
            if self.bad_ack:
                next_offset += 1
            self.rx.extend(f"OTA_ACK:{next_offset};".encode("ascii"))
        elif command.startswith("OTA_END:"):
            self.rx.extend(b"OTA_DONE;")
        return len(data)

    def flush(self):
        pass

    def read(self, size):
        if not self.rx:
            return b""
        data = bytes(self.rx[:size])
        del self.rx[:size]
        return data


class PmicOtaTest(unittest.TestCase):
    def test_both_bundles_are_complete_and_distinct(self):
        bundles = {}
        for layout in ("left", "right"):
            path = ROOT / "firmware/pmic/candidate" / layout / "manifest.json"
            manifest, images = OTA.load_bundle(path)
            self.assertEqual(manifest["layout"], layout)
            self.assertEqual(manifest["release_status"], "engineering-candidate")
            self.assertEqual(manifest["ota_supported"], layout == "right")
            bundles[layout] = images
        self.assertNotEqual(bundles["left"]["app"], bundles["right"]["app"])

    def test_corrupted_bundle_is_rejected(self):
        source = ROOT / "firmware/pmic/candidate/right"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for name in ("manifest.json", "boot.bin", "ChargeBAT.bin"):
                (target / name).write_bytes((source / name).read_bytes())
            with (target / "ChargeBAT.bin").open("r+b") as image:
                image.seek(20)
                image.write(b"\0")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                OTA.load_bundle(target / "manifest.json")

    def test_wrong_layout_in_manifest_is_rejected(self):
        source = ROOT / "firmware/pmic/candidate/right"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for name in ("manifest.json", "boot.bin", "ChargeBAT.bin"):
                (target / name).write_bytes((source / name).read_bytes())
            manifest = json.loads((target / "manifest.json").read_text())
            manifest["layout"] = "left"
            (target / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "bundle version"):
                OTA.load_bundle(target / "manifest.json")

    def test_transfer_checks_each_offset_and_crc(self):
        port = FakePort()
        payload = bytes(range(135))
        OTA.transfer(port, payload, 0.05)
        self.assertEqual(len([c for c in port.commands if c.startswith("OTA_DATA:")]), 3)
        self.assertEqual(port.commands[-1], "OTA_END:1;")

    def test_bad_ack_aborts_before_next_chunk(self):
        port = FakePort(bad_ack=True)
        with self.assertRaisesRegex(RuntimeError, "expected"):
            OTA.transfer(port, b"test", 0.05)
        self.assertEqual(port.commands[-1], "OTA_ABORT:1;")


if __name__ == "__main__":
    unittest.main()
