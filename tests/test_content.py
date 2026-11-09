"""A gateway can author, but cannot self-publish or award game points."""
from copy import deepcopy

from test_api import ADMIN, make_client, seed


def pack(slug='tuscany-signal', kind='dlc'):
    return {
        'slug': slug,
        'kind': kind,
        'title': {'en': 'Lost Signal', 'it': 'Il Segnale Perduto'},
        'summary': {'en': 'Explore two gateways.', 'it': 'Esplora due gateway.'},
        'chapters': [
            {'slug': 'chapter-one',
             'title': {'en': 'The Arrival', 'it': 'Il Ritrovo'},
             'story': {'en': 'The signal awakens again.', 'it': 'Il segnale si risveglia.'},
             'missions': [
                 {'slug': 'find-relay',
                  'title': {'en': 'Find a repeater', 'it': 'Trova un ripetitore'},
                  'description': {'en': 'Discover the Poggi outpost.', 'it': "Scopri l'avamposto Poggi."},
                  'objective': {'kind': 'discover_outpost', 'outpost_node_id': '!11223344'},
                  'suggested_xp': 25},
                 {'slug': 'reach-pisa',
                  'title': {'en': 'Call Pisa', 'it': 'Chiama Pisa'},
                  'description': {'en': 'Contact a second gateway.', 'it': 'Contatta un secondo gateway.'},
                  'objective': {'kind': 'reach_gateway', 'gateway_id': 'pisa-gw'},
                  'suggested_xp': 20},
             ]},
        ],
    }


def test_create_pending_then_publish_bilingually(tmp_path):
    with make_client(tmp_path) as client:
        auth = seed(client)
        submitted = client.post('/api/v1/gateway/content-packs', json=pack(), headers=auth)
        assert submitted.status_code == 201 and submitted.json()['status'] == 'pending'
        assert client.get('/api/v1/content-packs').json() == []
        assert client.get('/api/v1/content-packs/tuscany-signal').status_code == 404
        assert client.get('/api/v1/admin/content-packs').status_code == 401
        pending = client.get('/api/v1/admin/content-packs', headers=ADMIN).json()
        assert len(pending) == 1 and pending[0]['content']['title']['it'] == 'Il Segnale Perduto'
        assert client.post('/api/v1/admin/content-packs/tuscany-signal/publish').status_code == 401
        approved = client.post('/api/v1/admin/content-packs/tuscany-signal/publish', headers=ADMIN)
        assert approved.status_code == 200
        published = client.get('/api/v1/content-packs/tuscany-signal?lang=it').json()
        assert published['title'] == 'Il Segnale Perduto'
        assert published['chapters'][0]['missions'][0]['objective']['outpost_node_id'] == '!11223344'
        assert published['chapters'][0]['missions'][0]['awarded_xp'] == 0
        assert published['playable'] is False
        assert client.get('/api/v1/content-packs?lang=en&kind=dlc').json()[0]['title'] == 'Lost Signal'
        assert client.get('/api/v1/content-packs?kind=side').json() == []
        assert client.get('/api/v1/players/!aabbccdd/profile').json()['xp'] == 0
        assert client.get('/api/v1/leaderboard').json()['players'][0]['xp'] == 0
        assert client.post('/api/v1/admin/content-packs/tuscany-signal/publish', headers=ADMIN).status_code == 409


def test_gateway_owns_submission_not_other_gateways(tmp_path):
    with make_client(tmp_path) as client:
        first = seed(client)
        second = client.post('/api/v1/admin/gateways', json={
            'gateway_id': 'other-gw', 'radio_node_id': '!cafecafe'}, headers=ADMIN)
        assert second.status_code == 201
        other = {'authorization': 'Bearer ' + second.json()['token']}
        assert client.post('/api/v1/gateway/content-packs', json=pack(), headers=first).status_code == 201
        assert len(client.get('/api/v1/gateway/content-packs', headers=first).json()) == 1
        assert client.get('/api/v1/gateway/content-packs', headers=other).json() == []
        assert client.post('/api/v1/gateway/content-packs', json=pack('tuscany-signal-2', 'main'), headers=other).status_code == 201
        assert client.get('/api/v1/content-packs?kind=main').json() == []
        assert client.post('/api/v1/gateway/content-packs', json=pack('rogue-pkg')).status_code == 401
        assert client.post('/api/v1/admin/content-packs/tuscany-signal/publish', headers=first).status_code == 401


def test_rejection_and_conflicts(tmp_path):
    with make_client(tmp_path) as client:
        auth = seed(client)
        assert client.post('/api/v1/gateway/content-packs', json=pack(), headers=auth).status_code == 201
        assert client.post('/api/v1/gateway/content-packs', json=pack(), headers=auth).status_code == 409
        assert client.post('/api/v1/admin/content-packs/tuscany-signal/reject', headers=ADMIN).json()['status'] == 'rejected'
        assert client.post('/api/v1/admin/content-packs/tuscany-signal/publish', headers=ADMIN).status_code == 409
        assert client.get('/api/v1/content-packs').json() == []
        assert client.post('/api/v1/admin/content-packs/missing/reject', headers=ADMIN).status_code == 404


def test_invalid_mission_rules_rejected(tmp_path):
    with make_client(tmp_path) as client:
        auth = seed(client)
        bad = pack()
        bad['chapters'][0]['missions'][0]['objective'] = {'kind': 'reach_gateway', 'outpost_node_id': '!11223344'}
        assert client.post('/api/v1/gateway/content-packs', json=bad, headers=auth).status_code == 422
        bad = pack()
        bad['chapters'][0]['missions'][0]['suggested_xp'] = 99999
        assert client.post('/api/v1/gateway/content-packs', json=bad, headers=auth).status_code == 422
        bad = pack()
        bad['chapters'][0]['missions'][1]['slug'] = 'find-relay'
        assert client.post('/api/v1/gateway/content-packs', json=bad, headers=auth).status_code == 422
        bad = pack()
        bad['chapters'][0]['missions'][0]['payload'] = '<script>alert(1)</script>'
        assert client.post('/api/v1/gateway/content-packs', json=bad, headers=auth).status_code == 422
        bad = pack()
        bad['kind'] = 'javascript'
        assert client.post('/api/v1/gateway/content-packs', json=bad, headers=auth).status_code == 422
        assert client.get('/api/v1/content-packs?lang=fr').status_code == 422


def test_main_proposal_must_be_approved_and_riddle_is_declarative(tmp_path):
    with make_client(tmp_path) as client:
        auth = seed(client)
        story = pack('next-global-chapter', 'main')
        story['chapters'][0]['missions'][0]['objective'] = {'kind': 'solve_riddle'}
        assert client.post('/api/v1/gateway/content-packs', json=story, headers=auth).status_code == 201
        assert client.get('/api/v1/content-packs?kind=main').json() == []
        assert client.post('/api/v1/admin/content-packs/next-global-chapter/publish', headers=ADMIN).status_code == 200
        exposed = client.get('/api/v1/content-packs/next-global-chapter').json()
        assert exposed['kind'] == 'main' and exposed['chapters'][0]['missions'][0]['objective'] == {'kind': 'solve_riddle', 'gateway_id': None, 'outpost_node_id': None, 'unique_outposts': None}
        assert client.get('/api/v1/leaderboard').json()['players'][0]['xp'] == 0
