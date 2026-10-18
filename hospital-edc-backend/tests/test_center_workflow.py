import io
import openpyxl
from tests.conftest import auth_header
from tests.test_export import _create_patient


def test_center_filter_sort_and_isolation(client, admin_token, researcher1_token, researcher2_token, seed):
    a = _create_patient(client, researcher1_token, 'CENTERA')
    b = _create_patient(client, researcher2_token, 'CENTERB')
    headers = auth_header(researcher2_token)
    rows = client.get('/api/patients/?limit=1000&sort=center', headers=headers).json()['items']
    assert all(p['center_id'] == seed['c2'] for p in rows)
    assert client.get(f"/api/patients/{a['id']}", headers=headers).status_code == 403
    assert client.get(f"/api/patients/?center_id={seed['c1']}", headers=headers).status_code == 403
    rows = client.get('/api/patients/?limit=1000&sort=center', headers=auth_header(admin_token)).json()['items']
    assert [(p['center_code'],p['id']) for p in rows] == sorted((p['center_code'],p['id']) for p in rows)
    assert all('center_name' in p for p in rows)
    filtered = client.get(f"/api/patients/?center_id={seed['c2']}&limit=1000", headers=auth_header(admin_token)).json()['items']
    assert filtered and all(p['center_id']==seed['c2'] for p in filtered)
    for params, allowed in [(f"selected_centers={seed['c2']}", {b['patient_code']}), (f"selected_centers={seed['c1']}&selected_centers={seed['c2']}", {a['patient_code'],b['patient_code']})]:
        response = client.get('/api/export/?'+params, headers=auth_header(admin_token))
        assert response.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        codes = {row[0] for row in wb['患者主表'].iter_rows(min_row=2, values_only=True)}
        assert allowed <= codes
        if len(allowed)==1: assert a['patient_code'] not in codes
    assert client.get(f"/api/export/?selected_centers={seed['c1']}&selected_centers={seed['c2']}", headers=headers).status_code == 403
