#!/usr/bin/env python3
"""Offline PMIC monitor protocol and forwarding checks."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pmic_monitor", ROOT / "scripts/robopi-pmic-monitor.py")
MONITOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MONITOR)
REPLY = (b"CHRG_SN:0669FF555553787287104058;SW_DATE:;FW_VER:0.1.8-left;"
         b"CHRG_V:19.9V;CHRG_I:1.2A;BAT_V:51.3V;ICTRL:70;CHG_EN:1;")


class FakeSerial:
    def __init__(self, data):
        self.data = data
        self.written = b""

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.written += data

    def flush(self):
        pass

    def read(self, size):
        part, self.data = self.data[:size], self.data[size:]
        return part


class MonitorTest(unittest.TestCase):
    def test_query_uses_read_only_command_and_parses_charge(self):
        port = FakeSerial(REPLY)
        data = MONITOR.query(port, 0.1)
        self.assertEqual(port.written, b"CHRG_INFO:1;")
        self.assertEqual(data["charge_state"], "charging")
        self.assertEqual(data["input_voltage_v"], 19.9)
        self.assertIsNone(data["mcu_fault"])

    def test_optional_mcu_fault_is_not_inferred_from_enable(self):
        reply = REPLY.replace(b"CHG_EN:1;", b"CHG_FAULT:1;CHG_EN:1;")
        data = MONITOR.parse_reply(reply)
        self.assertTrue(data["mcu_fault"])
        self.assertEqual(data["charge_state"], "fault")
        no_pd = MONITOR.parse_reply(REPLY.replace(b"CHRG_V:19.9V;", b"CHRG_V:5.1V;")
                                      .replace(b"CHG_EN:1;", b"CHG_EN:0;"))
        self.assertEqual(no_pd["charge_state"], "no_pd_input")
        self.assertIsNone(no_pd["mcu_fault"])

    def test_plain_semver_and_historical_suffix(self):
        plain = MONITOR.parse_reply(REPLY.replace(b"0.1.8-left", b"0.1.10"))
        self.assertEqual(plain["firmware_version"], "0.1.10")
        historical = MONITOR.parse_reply(REPLY)
        self.assertEqual(historical["firmware_version"], "0.1.8-left")

    def test_incomplete_and_invalid_reply_rejected(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            MONITOR.parse_reply(REPLY.replace(b"CHRG_I:1.2A;", b""))
        with self.assertRaisesRegex(ValueError, "invalid PMIC measurement"):
            MONITOR.parse_reply(REPLY.replace(b"CHRG_I:1.2A;", b"CHRG_I:nanA;"))

    def test_s7_forwarding_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "bms_daemon"
            config.write_text("FORWARD_ENABLE=1\nFORWARD_PORT_B=/dev/ttyS7\n")
            with self.assertRaisesRegex(RuntimeError, "BMS forward destination"):
                MONITOR.check_forward_conflict("/dev/ttyS7", config)
            config.write_text("FORWARD_ENABLE=0\nFORWARD_PORT_B=/dev/ttyS7\n")
            MONITOR.check_forward_conflict("/dev/ttyS7", config)
            config.unlink()
            with self.assertRaisesRegex(RuntimeError, "BMS forward destination"):
                MONITOR.check_forward_conflict("/dev/ttyS7", config)

    def test_published_error_drops_stale_measurements(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status.json"
            MONITOR.publish(path, MONITOR.status_at("/dev/ttyS7", data=MONITOR.parse_reply(REPLY)))
            MONITOR.publish(path, MONITOR.status_at("/dev/ttyS7", error="disconnected"))
            status = json.loads(path.read_text())
            self.assertFalse(status["connected"])
            self.assertEqual(status["communication_fault"], "disconnected")
            self.assertIsNone(status["input_voltage_v"])
            self.assertIsNone(status["mcu_fault"])


if __name__ == "__main__":
    unittest.main()
