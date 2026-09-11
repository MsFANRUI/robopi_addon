import csv
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analyze_ethercan_pcap import (  # noqa: E402
    GS_CAN_FLAG_BRS,
    GS_CAN_FLAG_FD,
    analyse,
)


def usbmon_packet(urb_type, endpoint, device, bus, payload):
    header = bytearray(64)
    header[8] = ord(urb_type)
    header[9] = 3  # bulk
    header[10] = endpoint
    header[11] = device
    struct.pack_into("<H", header, 12, bus)
    struct.pack_into("<I", header, 36, len(payload))
    return bytes(header) + payload


def gs_frame(can_id, data, *, echo_id=0, channel=0, flags=0, dlc=None):
    if dlc is None:
        dlc = len(data)
    width = 64 if flags & GS_CAN_FLAG_FD else 8
    return (struct.pack("<IIBBBB", echo_id, can_id, dlc, channel, flags, 0)
            + data.ljust(width, b"\0"))


def write_pcap(path, packets, start_second=100):
    with path.open("wb") as stream:
        stream.write(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0,
                                 65535, 220))
        for index, packet in enumerate(packets):
            stream.write(struct.pack("<IIII", start_second + index, 0,
                                     len(packet), len(packet)))
            stream.write(packet)


class AnalysePcapTest(unittest.TestCase):
    def test_decodes_classic_and_fd_frames(self):
        classic = usbmon_packet("S", 0x01, 5, 3,
                                gs_frame(0x123, b"\x11\x22\x33"))
        fd = usbmon_packet(
            "C", 0x81, 5, 3,
            gs_frame(0x456, bytes(range(12)), dlc=9,
                     flags=GS_CAN_FLAG_FD | GS_CAN_FLAG_BRS),
        )
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "sample.pcap"
            write_pcap(capture, [classic, fd])
            result = analyse(capture)

        self.assertEqual(result["frames"], 2)
        self.assertEqual(result["tx_frames"], 1)
        self.assertEqual(result["rx_frames"], 1)
        self.assertEqual(result["fd_frames"], 1)
        self.assertEqual(result["brs_frames"], 1)
        self.assertEqual(result["data_bytes"], 15)

    def test_filters_usb_location_endpoint_and_urb(self):
        wanted = usbmon_packet("C", 0x81, 5, 3,
                               gs_frame(0x123, b"\x01"))
        wrong_device = usbmon_packet("C", 0x81, 6, 3,
                                     gs_frame(0x321, b"\x02"))
        wrong_stage = usbmon_packet("S", 0x81, 5, 3,
                                    gs_frame(0x222, b"\x03"))
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "filtered.pcap"
            write_pcap(capture, [wanted, wrong_device, wrong_stage])
            result = analyse(capture, bus=3, device=5, endpoints={0x81},
                             urb_types={"C"})

        self.assertEqual(result["frames"], 1)
        self.assertEqual(result["top_ids"][0]["can_id"], "0x123")
        self.assertEqual(result["filters"]["endpoints"], ["0x81"])

    def test_snapshot_directory_is_merged_in_timestamp_order(self):
        older = usbmon_packet("S", 0x01, 5, 3,
                              gs_frame(0x100, b"\x01"))
        newer = usbmon_packet("C", 0x81, 5, 3,
                              gs_frame(0x200, b"\x02"))
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            write_pcap(snapshot / "usbcan.pcap0", [newer], start_second=200)
            write_pcap(snapshot / "usbcan.pcap1", [older], start_second=100)
            csv_path = snapshot / "frames.csv"
            result = analyse(snapshot, csv_path)
            with csv_path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))

        self.assertEqual(result["frames"], 2)
        self.assertTrue(result["inputs"][0].endswith("usbcan.pcap1"))
        self.assertTrue(result["inputs"][1].endswith("usbcan.pcap0"))
        self.assertEqual([row["can_id"] for row in rows], ["0x100", "0x200"])
        self.assertEqual(result["usb_locations"][0]["bus"], 3)


if __name__ == "__main__":
    unittest.main()
