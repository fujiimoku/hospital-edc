from tests.conftest import auth_header

def test_centers_list_serialization(client, admin_token):
    response = client.get('/api/centers/?limit=1000', headers=auth_header(admin_token))
    assert response.status_code == 200, response.text
    assert response.json()['items'][0]['center_code']


def test_center_directory_is_local_for_daily_accounts(client, researcher1_token, qc1_token, seed):
    for token in (researcher1_token, qc1_token):
        result = client.get('/api/centers/?limit=1000', headers=auth_header(token)).json()
        assert {row['id'] for row in result['items']} == {seed['c1']}
        assert client.get(f"/api/centers/{seed['c2']}", headers=auth_header(token)).status_code == 403
