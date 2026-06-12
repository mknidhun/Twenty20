"""Backend API tests for Twenty20 Wariyad Charity Management Platform"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s

ADMIN_EMAIL = "admin@twenty20wariyad.com"
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "")

@pytest.fixture(scope="session")
def auth_session(session):
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASS
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return session

# -- Auth Tests --
class TestAuth:
    """Authentication flow tests"""

    def test_login_success(self, session):
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASS
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "super_admin"
        assert "email" in data

    def test_login_invalid(self, session):
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@test.com", "password": "wrongpass"
        })
        assert resp.status_code == 401

    def test_me_endpoint(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "super_admin"

# -- Dashboard Tests --
class TestDashboard:
    """Dashboard stats tests"""

    def test_dashboard_stats(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_members" in data
        assert "fund_balance" in data
        assert "monthly_collection" in data
        assert "pending_benefits" in data

    def test_recent_activity(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/dashboard/recent-activity")
        assert resp.status_code == 200
        data = resp.json()
        assert "recent_contributions" in data
        assert "recent_benefits" in data

    def test_monthly_collections(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/dashboard/monthly-collections")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 12  # 12 months

# -- Members Tests --
class TestMembers:
    """Member CRUD tests"""
    member_id = None

    def test_list_members(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/members")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_member(self, auth_session):
        resp = auth_session.post(f"{BASE_URL}/api/members", json={
            "name": "TEST_John Doe",
            "mobile": "9876543210",
            "address": "123 Test Street",
            "joining_date": "2024-01-01",
            "status": "active"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "member_id" in data
        assert data["member_id"].startswith("TW-")
        assert data["name"] == "TEST_John Doe"
        TestMembers.member_id = data["id"]

    def test_get_member(self, auth_session):
        if not TestMembers.member_id:
            pytest.skip("No member created")
        resp = auth_session.get(f"{BASE_URL}/api/members/{TestMembers.member_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "TEST_John Doe"

    def test_update_member(self, auth_session):
        if not TestMembers.member_id:
            pytest.skip("No member created")
        resp = auth_session.put(f"{BASE_URL}/api/members/{TestMembers.member_id}", json={
            "address": "Updated Address"
        })
        assert resp.status_code == 200

# -- Contributions Tests --
class TestContributions:
    """Contribution tests"""

    def test_list_contributions(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/contributions")
        assert resp.status_code == 200

    def test_contribution_status(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/contributions/status/2025/1")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_record_contribution(self, auth_session):
        if not TestMembers.member_id:
            pytest.skip("No member available")
        resp = auth_session.post(f"{BASE_URL}/api/contributions", json={
            "member_id": TestMembers.member_id,
            "month": 6, "year": 2024,
            "amount": 100.0, "payment_method": "cash"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "receipt_number" in data
        assert data["receipt_number"].startswith("RCP-")

# -- Benefits Tests --
class TestBenefits:
    """Benefits tests"""

    def test_list_benefits(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/benefits")
        assert resp.status_code == 200

    def test_apply_benefit(self, auth_session):
        if not TestMembers.member_id:
            pytest.skip("No member available")
        resp = auth_session.post(f"{BASE_URL}/api/benefits", json={
            "member_id": TestMembers.member_id,
            "benefit_type": "marriage",
            "event_date": "2024-06-15",
            "notes": "Test benefit"
        })
        assert resp.status_code in [200, 400]  # 400 if already applied

# -- Medical Aid Tests --
class TestMedicalAid:
    """Medical aid tests"""

    def test_list_medical_aid(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/medical-aid")
        assert resp.status_code == 200

    def test_apply_medical_aid(self, auth_session):
        resp = auth_session.post(f"{BASE_URL}/api/medical-aid", json={
            "applicant_name": "TEST_Patient",
            "contact": "9876543210",
            "address": "Test Address",
            "medical_condition": "Fever",
            "hospital": "Test Hospital",
            "estimated_expense": 5000.0,
            "notes": "Test medical aid"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"

# -- Death Assistance Tests --
class TestDeathAssistance:
    """Death assistance tests"""

    def test_list_death_assistance(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/death-assistance")
        assert resp.status_code == 200

    def test_create_death_assistance(self, auth_session):
        resp = auth_session.post(f"{BASE_URL}/api/death-assistance", json={
            "deceased_name": "TEST_Deceased",
            "family_details": "Wife and 2 kids",
            "address": "Test Address",
            "contact_person": "TEST_Contact",
            "date_of_death": "2024-06-01"
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

# -- Cashbook Tests --
class TestCashbook:
    """Cashbook tests"""

    def test_list_cashbook(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/cashbook")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Check running_balance field
        for entry in data:
            assert "running_balance" in entry

    def test_create_cashbook_entry(self, auth_session):
        resp = auth_session.post(f"{BASE_URL}/api/cashbook", json={
            "entry_type": "credit",
            "category": "donation",
            "description": "TEST_Donation entry",
            "amount": 1000.0,
            "date": "2024-06-01"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "voucher_number" in data

# -- Committee Tests --
class TestCommittee:
    """Committee tests"""

    def test_list_committees(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/committee")
        assert resp.status_code == 200

    def test_create_committee(self, auth_session):
        resp = auth_session.post(f"{BASE_URL}/api/committee", json={
            "year": 2024,
            "positions": [{"title": "President", "member_name": "TEST_Member"}],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        })
        assert resp.status_code == 200

# -- Meetings Tests --
class TestMeetings:
    """Meetings tests"""

    def test_list_meetings(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/meetings")
        assert resp.status_code == 200

    def test_create_meeting(self, auth_session):
        resp = auth_session.post(f"{BASE_URL}/api/meetings", json={
            "meeting_type": "general",
            "title": "TEST_General Meeting",
            "scheduled_date": "2024-07-15",
            "agenda": "Discuss contributions and benefits"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "scheduled"

# -- Users Tests --
class TestUsers:
    """User management tests"""

    def test_list_users(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/users")
        assert resp.status_code == 200

    def test_create_user(self, auth_session):
        import time
        ts = int(time.time())
        resp = auth_session.post(f"{BASE_URL}/api/users", json={
            "name": "TEST_New User",
            "email": f"test_user_{ts}@twenty20.com",
            "password": "Test@1234",
            "role": "member"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "member"

# -- Reports Tests --
class TestReports:
    """Reports tests"""

    def test_members_report(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/reports/members")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data

    def test_contributions_report(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/reports/contributions/2024")
        assert resp.status_code == 200
        data = resp.json()
        assert "year" in data
        assert "monthly" in data

    def test_benefits_report(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/reports/benefits")
        assert resp.status_code == 200
        data = resp.json()
        assert "marriage_count" in data

# -- Cleanup --
class TestCleanup:
    """Cleanup test data"""

    def test_delete_test_member(self, auth_session):
        if not TestMembers.member_id:
            pytest.skip("No member to delete")
        resp = auth_session.delete(f"{BASE_URL}/api/members/{TestMembers.member_id}")
        assert resp.status_code == 200
