from meshquest.game import game_rules, level_state, player_profile
from test_api import ADMIN, make_client, route, seed


def test_empty_profile_has_no_completed_missions(tmp_path):
    with make_client(tmp_path) as client:
        seed(client)
        profile = client.get('/api/v1/players/!AABBCCDD/profile?lang=it')
        assert profile.status_code == 200
        game = profile.json()
        assert game['xp'] == 0 and game['unique_outposts'] == 0
        assert game['level']['level'] == 1
        assert not any(q['completed'] for q in game['missions'])
        assert not any(chapter['unlocked'] for chapter in game['chapters'])
        assert game['language'] == 'it'
        assert 'Primo Eco' in [m['title'] for m in game['missions']]


def test_progression_observation_updates_quests_and_chapters(tmp_path):
    with make_client(tmp_path) as client:
        auth = seed(client)
        for n, name in [('!55667788', 'RPT-B'), ('!a1b2c3d4', 'RPT-C')]:
            assert client.post('/api/v1/admin/outposts', json={'node_id': n, 'name': name}, headers=ADMIN).status_code == 201
            assert client.post(f'/api/v1/admin/outposts/{n}/approve', headers=ADMIN).status_code == 200
        for ix, n in enumerate(['!11223344', '!55667788', '!a1b2c3d4']):
            result = client.post('/api/v1/observations', json=route(event_id=f'probe-game-{ix:04d}', route=[n]), headers=auth)
            assert result.status_code == 200 and result.json()['xp_awarded'] == 50
            game = client.get('/api/v1/players/!aabbccdd/profile').json()
            assert game['xp'] == (ix+1)*50
            assert sum(q['completed'] for q in game['missions']) == ix+1
            assert sum(ch['unlocked'] for ch in game['chapters']) == ix+1
        assert game['level']['level'] == 2
        assert game['level']['xp_to_next_level'] == 100
        dup = client.post('/api/v1/observations', json=route(event_id='probe-game-0002', route=['!a1b2c3d4']), headers=auth)
        assert dup.json()['duplicate'] is True
        assert client.get('/api/v1/players/!aabbccdd/profile').json()['xp'] == 150


def test_rules_bilingual_and_read_only(tmp_path):
    with make_client(tmp_path) as client:
        en = client.get('/api/v1/game/rules').json()
        it = client.get('/api/v1/game/rules?lang=it').json()
        assert en['missions'][0]['title'] == 'First Echo'
        assert it['missions'][0]['title'] == 'Primo Eco'
        assert en['outpost_first_discovery_xp'] == 50
        assert client.get('/api/v1/quests?lang=it').json() == it['missions']
        assert client.get('/api/v1/game/rules?lang=fr').status_code == 422
        assert client.get('/api/v1/players/!01010101/profile').status_code == 404


def test_pure_game_rules_reject_invalid_levels_and_track_progress():
    assert level_state(0)['level'] == 1
    assert level_state(99)['level'] == 1
    assert level_state(100)['level'] == 2
    assert level_state(249)['level'] == 2
    assert level_state(250)['level'] == 3
    profile = player_profile('!abcdef01', 'Scout', [{'node_id': '!12121212', 'name': 'One', 'xp': 50, 'discovered_at': '2026-01-01'}])
    assert profile['missions'][0]['completed']
    assert not profile['missions'][1]['completed']
    assert profile['evidence'] == 'trusted_gateway_attestation_not_independent_rf_proof'
