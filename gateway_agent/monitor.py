#!/usr/bin/env python3
"""Read-only Meshtastic packet metadata monitor (Python 3.9+, Raspberry Pi Zero W ARMv6).

This tool does NOT execute radio game commands, create score observations or transmit
traceroutes. It never logs decoded chat contents or secret channel keys.
"""
import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone


def pick(packet, *keys):
    for key in keys:
        if key in packet:
            return packet[key]
    return None


def metadata(packet):
    """Return only safe, JSON-compatible metadata, never the decoded packet payload."""
    decoded = packet.get("decoded")
    port = decoded.get("portnum") if isinstance(decoded, dict) else None
    return {
        "observation_type": "packet_metadata_only",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "packet_id": pick(packet, "id"),
        "sender": pick(packet, "fromId", "from"),
        "destination": pick(packet, "toId", "to"),
        "portnum": port,
        "channel_index": pick(packet, "channel"),
        "rx_rssi": pick(packet, "rxRssi", "rx_rssi"),
        "rx_snr": pick(packet, "rxSnr", "rx_snr"),
        "hop_start": pick(packet, "hopStart", "hop_start"),
        "hop_limit": pick(packet, "hopLimit", "hop_limit"),
        "via_mqtt": pick(packet, "viaMqtt", "via_mqtt"),
        "verified_rf_path": False,
        "xp_awarded": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="MeshQuest lightweight radio monitor (no RF transmissions)")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--serial", metavar="DEVICE", help="Local Meshtastic USB serial radio")
    source.add_argument("--tcp", metavar="HOST", help="Existing local TCP Meshtastic radio")
    parser.add_argument("--tcp-port", type=int, default=4403)
    parser.add_argument("--self-test", action="store_true", help="Synthetic packet test: no radio required")
    args = parser.parse_args(argv)
    if args.self_test:
        test_packet = {"id": 123, "fromId": "!11223344", "viaMqtt": False,
                       "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "PRIVATE!"}}
        print(json.dumps(metadata(test_packet), ensure_ascii=False), flush=True)
        return 0
    if not args.serial and not args.tcp:
        parser.error("Specify --serial DEVICE, --tcp HOST, or --self-test")
    try:
        from pubsub import pub
        from meshtastic.serial_interface import SerialInterface
        from meshtastic.tcp_interface import TCPInterface
    except ImportError as exc:
        parser.error("Install optional radio dependencies on this device: pip install meshtastic. " + str(exc))

    def on_receive(packet, interface=None):
        if isinstance(packet, dict):
            print(json.dumps(metadata(packet), ensure_ascii=False), flush=True)

    pub.subscribe(on_receive, "meshtastic.receive")
    device = None
    try:
        # Explicit device selection. No sendText(), sendData(), sendTraceRoute() or RF commands.
        if args.serial:
            device = SerialInterface(devPath=args.serial)
        else:
            device = TCPInterface(hostname=args.tcp, portNumber=args.tcp_port)
        print("Listening to metadata only (Ctrl+C to stop).", file=sys.stderr)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        return 0
    finally:
        if device is not None:
            device.close()


if __name__ == "__main__":
    sys.exit(main())
