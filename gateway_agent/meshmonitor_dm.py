"""Send one MeshQuest DM via MeshMonitor's source-scoped v1 API.

TX is only called by an explicitly enabled MQTT pilot. This module has no
Meshtastic TCP connection of its own and never logs bearer credentials.
"""
import ipaddress
import json
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def validate_base_url(base_url, allow_http_lan=False):
    parts = urlsplit(base_url)
    if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Invalid MeshMonitor URL")
    if parts.scheme == "https":
        return base_url.rstrip("/")
    if parts.scheme == "http" and parts.hostname in ("localhost", "127.0.0.1", "::1"):
        return base_url.rstrip("/")
    try:
        ip = ipaddress.ip_address(parts.hostname)
    except ValueError:
        ip = None
    if (parts.scheme == "http" and allow_http_lan and ip is not None
            and ip.is_private and not ip.is_loopback):
        return base_url.rstrip("/")
    raise ValueError("MeshMonitor requires HTTPS; for private-IP HTTP pilot pass --allow-http-lan")


class MeshMonitorDM:
    def __init__(self, base_url, source_id, token, allow_http_lan=False, opener=urlopen):
        self.base_url = validate_base_url(base_url, allow_http_lan)
        if not isinstance(source_id, str) or len(source_id) != 36 or any(
            ch not in "0123456789abcdef-" for ch in source_id.lower()
        ):
            raise ValueError("Invalid MeshMonitor source UUID")
        if not isinstance(token, str) or not token:
            raise ValueError("MeshMonitor API token required")
        self.source_id = source_id
        self.token = token
        self.opener = opener

    def send(self, to_node_id, message):
        from gateway_agent.mqtt_pilot import node_id, BROADCAST, MAX_REPLY

        dest = node_id(to_node_id)
        if dest is None or dest == BROADCAST:
            raise ValueError("DM destination must be a concrete node")
        if not isinstance(message, str) or not message or len(message.encode("utf-8")) > MAX_REPLY:
            raise ValueError("DM message must fit in 150 UTF-8 bytes")

        url = self.base_url + "/api/v1/sources/" + self.source_id + "/messages"
        body = json.dumps({"toNodeId": dest, "text": message}, separators=(",", ":")).encode()
        req = Request(url, data=body, headers={
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
        }, method="POST")
        with self.opener(req, timeout=10) as response:
            if response.status != 201:
                raise ValueError("MeshMonitor did not accept a single-message DM")
            data = json.loads(response.read(8192))
        if not (isinstance(data, dict) and data.get("success") is True
                and data.get("data", {}).get("toNodeId") == dest
                and data.get("data", {}).get("deliveryState") == "pending"
                and data.get("data", {}).get("messageCount") == 1):
            raise ValueError("Unexpected MeshMonitor DM acceptance response")
        return data["data"]["requestId"]
