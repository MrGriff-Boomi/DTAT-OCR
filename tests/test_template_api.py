"""
Integration test for template API endpoints

Run the API server first:
    python -m uvicorn api:app --host 0.0.0.0 --port 8000

Then run this test:
    python test_template_api.py
"""

import requests
from requests.auth import HTTPBasicAuth

# Configuration
BASE_URL = "http://localhost:8000"
AUTH = HTTPBasicAuth('admin', 'admin')  # Update with actual credentials


def test_list_templates():
    """Test GET /templates"""
    print('='*60)
    print('TEST: GET /templates')
    print('='*60)

    response = requests.get(f"{BASE_URL}/templates")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    templates = response.json()
    assert isinstance(templates, list), "Expected list of templates"
    assert len(templates) == 4, f"Expected 4 templates, got {len(templates)}"

    print(f"[PASS] Retrieved {len(templates)} templates")
    for template in templates:
        print(f"  - {template['name']}: {template['display_name']}")


def test_get_template_by_name():
    """Test GET /templates/{name}"""
    print('\n' + '='*60)
    print('TEST: GET /templates/template-generic-invoice')
    print('='*60)

    response = requests.get(f"{BASE_URL}/templates/template-generic-invoice")
    assert response.status_code == 200

    template = response.json()
    assert template['name'] == 'template-generic-invoice'
    assert template['is_template'] == True
    assert 'fields' in template
    assert len(template['fields']) > 0

    print(f"[PASS] Retrieved template: {template['display_name']}")
    print(f"  Fields: {len(template['fields'])}")
    print(f"  Document type: {template['document_type']}")


def test_get_nonexistent_template():
    """Test GET /templates/{name} for non-existent template"""
    print('\n' + '='*60)
    print('TEST: GET /templates/non-existent (expect 404)')
    print('='*60)

    response = requests.get(f"{BASE_URL}/templates/non-existent")
    assert response.status_code == 404

    print("[PASS] Returns 404 for non-existent template")


def test_get_templates_by_type():
    """Test GET /templates/by-type/{type}"""
    print('\n' + '='*60)
    print('TEST: GET /templates/by-type/invoice')
    print('='*60)

    response = requests.get(f"{BASE_URL}/templates/by-type/invoice")
    assert response.status_code == 200

    templates = response.json()
    assert isinstance(templates, list)
    assert len(templates) == 1
    assert templates[0]['document_type'] == 'invoice'

    print(f"[PASS] Retrieved {len(templates)} invoice template(s)")


def test_instantiate_template():
    """Test POST /templates/{name}/instantiate"""
    print('\n' + '='*60)
    print('TEST: POST /templates/template-generic-invoice/instantiate')
    print('='*60)

    response = requests.post(
        f"{BASE_URL}/templates/template-generic-invoice/instantiate",
        params={"new_name": "test-acme-invoice"},
        json={
            "display_name": "Acme Corp Invoice",
            "organization_id": "org-test-123",
            "description": "Test invoice profile"
        },
        auth=AUTH
    )

    if response.status_code != 201:
        print(f"Error: {response.status_code}")
        print(f"Response: {response.text}")

    assert response.status_code == 201, f"Expected 201, got {response.status_code}"

    profile = response.json()
    assert profile['name'] == 'test-acme-invoice'
    assert profile['display_name'] == 'Acme Corp Invoice'
    assert profile['organization_id'] == 'org-test-123'
    assert profile['is_template'] == False
    assert len(profile['fields']) == 5  # Same as template

    print(f"[PASS] Created profile from template: {profile['name']}")
    print(f"  ID: {profile['id']}")
    print(f"  Display name: {profile['display_name']}")
    print(f"  Fields: {len(profile['fields'])}")

    return profile['id']


def test_list_profiles_includes_instantiated():
    """Test that instantiated profiles appear in profile list"""
    print('\n' + '='*60)
    print('TEST: GET /profiles (should include instantiated profiles)')
    print('='*60)

    response = requests.get(f"{BASE_URL}/profiles", auth=AUTH)
    assert response.status_code == 200

    profiles = response.json()
    profile_names = [p['name'] for p in profiles]

    # Should include both templates and instantiated profiles
    assert 'template-generic-invoice' in profile_names
    assert 'test-acme-invoice' in profile_names

    print(f"[PASS] Found {len(profiles)} total profiles")
    print(f"  Templates: {sum(1 for p in profiles if p['is_template'])}")
    print(f"  Custom: {sum(1 for p in profiles if not p['is_template'])}")


def test_filter_profiles_by_template_status():
    """Test filtering profiles by is_template"""
    print('\n' + '='*60)
    print('TEST: GET /profiles?is_template=true')
    print('='*60)

    # Get only templates
    response = requests.get(
        f"{BASE_URL}/profiles",
        params={"is_template": True},
        auth=AUTH
    )
    assert response.status_code == 200

    templates = response.json()
    assert all(p['is_template'] for p in templates)
    print(f"[PASS] Found {len(templates)} templates")

    # Get only custom profiles
    response = requests.get(
        f"{BASE_URL}/profiles",
        params={"is_template": False},
        auth=AUTH
    )
    assert response.status_code == 200

    custom_profiles = response.json()
    assert all(not p['is_template'] for p in custom_profiles)
    print(f"[PASS] Found {len(custom_profiles)} custom profiles")


def cleanup_test_profile():
    """Clean up test profile"""
    print('\n' + '='*60)
    print('CLEANUP: Delete test profile')
    print('='*60)

    # Get profile by name
    response = requests.get(
        f"{BASE_URL}/profiles/by-name/test-acme-invoice",
        auth=AUTH
    )

    if response.status_code == 200:
        profile = response.json()
        profile_id = profile['id']

        # Delete it
        response = requests.delete(
            f"{BASE_URL}/profiles/{profile_id}",
            auth=AUTH
        )

        if response.status_code == 200:
            print(f"[PASS] Deleted test profile (ID: {profile_id})")
        else:
            print(f"[WARN] Could not delete test profile: {response.status_code}")
    else:
        print("[INFO] Test profile not found (may have been cleaned up already)")


if __name__ == '__main__':
    try:
        test_list_templates()
        test_get_template_by_name()
        test_get_nonexistent_template()
        test_get_templates_by_type()
        test_instantiate_template()
        test_list_profiles_includes_instantiated()
        test_filter_profiles_by_template_status()

        print('\n' + '='*60)
        print('ALL API TESTS PASSED!')
        print('='*60)

    except AssertionError as e:
        print(f'\n[FAIL] Test assertion failed: {e}')
        raise

    except requests.exceptions.ConnectionError:
        print('\n[ERROR] Could not connect to API server.')
        print('Make sure the server is running:')
        print('  python -m uvicorn api:app --host 0.0.0.0 --port 8000')
        raise

    finally:
        # Clean up test data
        try:
            cleanup_test_profile()
        except:
            pass
