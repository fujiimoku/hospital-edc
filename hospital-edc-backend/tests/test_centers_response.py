from tests.conftest import auth_header

def test_centers_list_serialization(client, admin_token):
    response = client.get('/api/centers/?limit=1000', headers=auth_header(admin_token))
    assert response.status_code == 200, response.text
    assert response.json()['items'][0]['center_code']
