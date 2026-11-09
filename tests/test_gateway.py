"""Gateway tests: a Raspberry relays metadata; Pisa alone owns game state."""
import io
import json
import os
from urllib.request import Request

import pytest

from gateway_agent.agent import DiskQueue, ServerClient, normalize_packet, read_token, server_url
from test_api import ADMIN, make_client, seed


def test_token_authenticated_heartbeat_and_private_status(tmp_path):
    with make_client(tmp_path) as client:
        auth = seed(client)
        assert client.post('/api/v1/gateway/heartbeat', json={'agent_version': '0.4.0a0', 'transport': 'serial'}).status_code == 401
        good = client.post('/api/v1/gateway/heartbeat', json={'agent_version': '0.4.0a0', 'transport': 'serial'}, headers=auth)
        assert good.status_code == 200
        assert good.json()['mode'] == 'metadata_only'
        assert client.get('/api/v1/admin/gateways/status').status_code == 401
        status = client.get('/api/v1/admin/gateways/status', headers=ADMIN).json()[0]
        assert status['last_seen_at'] is not None and status['agent_version'] == '0.4.0a0'
        assert status['packet_metadata_count'] == 0


def test_packet_metadata_deduplicated_and_awards_no_xp(tmp_path):
    with make_client(tmp_path) as client:
        auth = seed(client)
        packet = {'event_id': 'radio-aabbccdd-00000001', 'observation_type': 'packet_metadata_only',
                  'sender_node_id': '!AABBCCDD', 'channel_index': 1, 'portnum': 'TEXT_MESSAGE_APP',
                  'hop_start': 4, 'hop_limit': 3, 'rx_snr': 3.2, 'rx_rssi': -96, 'via_mqtt': False}
        res = client.post('/api/v1/gateway/packets', json=packet, headers=auth)
        assert res.status_code == 200 and res.json() == {'accepted': True, 'duplicate': False, 'awarded_xp': 0}
        dupe = client.post('/api/v1/gateway/packets', json=packet, headers=auth)
        assert dupe.status_code == 200 and dupe.json()['duplicate'] is True
        for key, value in [('via_mqtt', True), ('observation_type', 'route_proof'), ('text', 'SECRET')]:
            rejected = client.post('/api/v1/gateway/packets', json={**packet, key: value}, headers=auth)
            assert rejected.status_code == 422
        assert client.post('/api/v1/gateway/packets', json=packet).status_code == 401
        assert client.get('/api/v1/players/!aabbccdd/profile').json()['xp'] == 0
        assert client.get('/api/v1/leaderboard').json()['players'][0]['xp'] == 0
        assert client.get('/api/v1/admin/gateways/status', headers=ADMIN).json()[0]['packet_metadata_count'] == 1


def test_gateway_filters_channel_mqtt_and_content():
    packet = {'channel': 1, 'fromId': '!AABBCCDD', 'id': 4242, 'rxRssi': -93,
              'decoded': {'portnum': 'TEXT_MESSAGE_APP', 'text': 'SENSITIVE-DM'}, 'viaMqtt': False}
    data = normalize_packet(packet, 1)
    assert data['sender_node_id'] == '!aabbccdd'
    assert data['event_id'] == 'radio-aabbccdd-00001092'
    assert 'SENSITIVE-DM' not in json.dumps(data) and 'text' not in data
    assert normalize_packet(packet, 2) is None
    assert normalize_packet({**packet, 'viaMqtt': True}, 1) is None
    assert normalize_packet({}, 1) is None


def test_gateway_offline_queue_is_persistent_and_bounded(tmp_path):
    path = tmp_path / 'queue.db'
    q = DiskQueue(path, limit=2)
    for id_ in ('packet-0001', 'packet-0002', 'packet-0003'):
        q.add({'event_id': id_})
    assert q.count() == 2
    assert q.first()[1]['event_id'] == 'packet-0002'
    q.close()
    q2 = DiskQueue(path, limit=2)
    assert q2.first()[1]['event_id'] == 'packet-0002'
    q2.delete(q2.first()[0])
    assert q2.count() == 1
    q2.close()


def test_gateway_enforces_https_and_private_file(tmp_path):
    assert server_url('https://example.org/') == 'https://example.org'
    assert server_url('http://localhost:8000') == 'http://localhost:8000'
    with pytest.raises(ValueError, match='HTTPS'):
        server_url('http://192.168.10.1:8000')
    path = tmp_path / 'gateway-token'
    path.write_text('a' * 50)
    path.chmod(0o644)
    with pytest.raises(ValueError, match='chmod 600'):
        read_token(path)
    path.chmod(0o600)
    assert read_token(path) == 'a' * 50


def test_gateway_http_client_sends_token_without_radio():
    sent = {}

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self, n): return b'{"accepted":true,"gateway_id":"pisa-gw"}'

    def opener(req, timeout):
        sent['req'], sent['timeout'] = req, timeout
        return FakeResponse()

    reply = ServerClient('https://meshquest.example', 't' * 48, opener=opener).post(
        '/api/v1/gateway/heartbeat', {'agent_version': '0.4.0a0', 'transport': 'test'})
    assert reply['gateway_id'] == 'pisa-gw'
    assert sent['req'].get_header('Authorization') == 'Bearer ' + 't' * 48
    assert sent['req'].full_url == 'https://meshquest.example/api/v1/gateway/heartbeat'


def test_creator_studio_and_staging_gateway_auth(tmp_path, monkeypatch):
    monkeypatch.setenv('MESHQUEST_STAGING_PASSWORD', 'staging-strong-password')
    with make_client(tmp_path) as client:
        assert client.get('/creator').status_code == 401
        staging = {'x-meshquest-staging-password': 'staging-strong-password'}
        res = client.get('/creator', headers=staging)
        assert res.status_code == 200 and 'Creator Studio' in res.text
        assert 'frame-ancestors' in res.headers['content-security-policy']
        auth = seed_staging(client, staging)
        payload = {'agent_version': '0.4.0a0', 'transport': 'test'}
        assert client.post('/api/v1/gateway/heartbeat', json=payload, headers=auth).status_code == 401
        full = {**staging, **auth}
        assert client.post('/api/v1/gateway/heartbeat', json=payload, headers=full).json()['accepted']
        assert client.get('/api/v1/admin/gateways/status', headers={**staging, **ADMIN}).status_code == 200


def seed_staging(client, staging):
    response = client.post('/api/v1/admin/gateways', json={
        'gateway_id': 'staging-gateway', 'radio_node_id': '!01020304'}, headers={**staging, **ADMIN})
    assert response.status_code == 201
    return {'authorization': 'Bearer ' + response.json()['token']}


def test_admin_revokes_individual_gateway_token(tmp_path):
    with make_client(tmp_path) as client:
        auth = seed(client)
        payload = {'agent_version': '0.4.0a0', 'transport': 'test'}
        assert client.post('/api/v1/gateway/heartbeat', json=payload, headers=auth).status_code == 200
        assert client.post('/api/v1/admin/gateways/pisa-gw/disable').status_code == 401
        result = client.post('/api/v1/admin/gateways/pisa-gw/disable', headers=ADMIN)
        assert result.status_code == 200 and result.json()['token_revoked']
        assert client.post('/api/v1/gateway/heartbeat', json=payload, headers=auth).status_code == 401
        assert client.get('/api/v1/admin/gateways/status', headers=ADMIN).json()[0]['enabled'] is False
