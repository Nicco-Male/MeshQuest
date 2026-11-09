#!/usr/bin/env python3
"""Walk through a simulated MeshQuest game using the REAL local API/scoring code.

No LoRa devices are connected and no packets are transmitted. This executable
example is intentionally separate from the radio gateway under development.
Requires `pip install '.[test]'`.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from meshquest.app import create_app

ADMIN = {"x-admin-key": "local-demo-only-not-a-real-secret"}
PLAYER = "!aabbccdd"
OUTPOSTS = [("!11223344", "Pisa Hills"), ("!55667788", "Poggi"), ("!a1b2c3d4", "North Ridge")]


def checked(response, expected=200):
    if response.status_code != expected:
        raise RuntimeError(f"Demo request failed: HTTP {response.status_code}: {response.text}")
    return response.json()


def main(lang: str) -> None:
    print("MeshQuest simulated gameplay — NO LIVE RF / Demo di gioco — RADIO NON ATTIVA\n")
    with TemporaryDirectory(prefix="meshquest-demo-") as folder:
        app = create_app(f"sqlite:///{Path(folder) / 'demo.db'}", ADMIN["x-admin-key"])
        with TestClient(app) as client:
            checked(client.post('/api/v1/admin/players', json={'node_id': PLAYER, 'nickname': 'Explorer'}, headers=ADMIN), 201)
            for node_id, name in OUTPOSTS:
                checked(client.post('/api/v1/admin/outposts', json={'node_id': node_id, 'name': name}, headers=ADMIN), 201)
                checked(client.post(f'/api/v1/admin/outposts/{node_id}/approve', headers=ADMIN))
            gate = checked(client.post('/api/v1/admin/gateways', json={'gateway_id': 'demo-pisa', 'radio_node_id': '!99887766'}, headers=ADMIN), 201)
            auth = {'authorization': f'Bearer {gate["token"]}'}
            paths = [([OUTPOSTS[0][0]], 1), ([OUTPOSTS[0][0], OUTPOSTS[1][0]], 0), ([OUTPOSTS[2][0]], 2)]
            for i, (path, unknown) in enumerate(paths, start=1):
                event = {
                    'event_id': f'demo-route-{i:04d}', 'player_node_id': PLAYER,
                    'route_to_player': [], 'route_to_gateway': path,
                    'unknown_to_player': 0, 'unknown_to_gateway': unknown,
                    'source': 'rf_traceroute',
                }
                scored = checked(client.post('/api/v1/observations', json=event, headers=auth))
                profile = checked(client.get(f'/api/v1/players/{PLAYER}/profile?lang={lang}'))
                found = ', '.join(scored['credited_outposts']) or 'none'
                print(f'Observation {i}: route={path}, unknown_hops={unknown}, +{scored["xp_awarded"]} XP, new={found}')
                for mission in profile['missions']:
                    print(f'  {mission["title"]}: {mission["progress"]}/{mission["target_unique_outposts"]}')
                print(f'  Total: {profile["xp"]} XP | Level {profile["level"]["level"]}\n')
            board = checked(client.get('/api/v1/leaderboard'))
            print(f'Leaderboard: {board["players"][0]["nickname"]} — {board["players"][0]["xp"]} XP')
            print('All observations in this demo are deliberately fabricated test data, not verified RF routes.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MeshQuest game simulation, without any radio transmissions')
    parser.add_argument('--lang', choices=('en', 'it'), default='it')
    main(parser.parse_args().lang)
