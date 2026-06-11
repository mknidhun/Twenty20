"""Tests for new features: CSV import, PDF receipt, demo seed"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def auth_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@twenty20wariyad.com",
        "password": "Admin@20W20"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    s.headers.pop("Content-Type", None)
    return s

class TestDemoSeed:
    """Test demo data seeding endpoint"""

    def test_demo_seed_returns_200(self, auth_session):
        resp = auth_session.post(f"{BASE_URL}/api/demo/seed",
                                 headers={"Content-Type": "application/json"})
        assert resp.status_code == 200, f"Seed failed: {resp.text}"
        data = resp.json()
        assert "message" in data or "members_created" in data or "contributions_created" in data

    def test_members_count_after_seed(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/members")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 15, f"Expected 15+ members, got {len(data)}"

    def test_contributions_exist_after_seed(self, auth_session):
        import datetime
        now = datetime.datetime.now()
        resp = auth_session.get(f"{BASE_URL}/api/contributions/status/{now.year}/{now.month}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0, "No contributions found after seeding"

    def test_dashboard_shows_fund_balance(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("fund_balance", 0) > 0, "Fund balance should be > 0 after seeding"
        assert data.get("total_members", 0) >= 15


class TestCSVImport:
    """Test CSV/Excel import endpoint"""

    def test_import_template_download(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/members/import-template")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("Content-Type", "")
        assert "name" in resp.text and "mobile" in resp.text

    def test_import_csv_members(self, auth_session):
        csv_content = (
            "name,mobile,address,joining_date,status\n"
            "TEST_Import User1,9000000001,\"Test Address 1 Wariyad\",2024-01-01,active\n"
            "TEST_Import User2,9000000002,\"Test Address 2 Wariyad\",2024-02-01,active\n"
        )
        files = {"file": ("test_import.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = auth_session.post(f"{BASE_URL}/api/members/import", files=files)
        assert resp.status_code == 200, f"Import failed: {resp.text}"
        data = resp.json()
        assert data.get("imported", 0) >= 2 or data.get("skipped", 0) > 0, f"Response: {data}"

    def test_import_invalid_file_type(self, auth_session):
        files = {"file": ("test.txt", io.BytesIO(b"some text"), "text/plain")}
        resp = auth_session.post(f"{BASE_URL}/api/members/import", files=files)
        assert resp.status_code == 400

    def test_import_missing_columns(self, auth_session):
        csv_content = "fullname,phone\nTest User,1234567890\n"
        files = {"file": ("bad_columns.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = auth_session.post(f"{BASE_URL}/api/members/import", files=files)
        assert resp.status_code == 400


class TestPDFReceipt:
    """Test PDF receipt download"""

    def test_receipt_for_paid_contribution(self, auth_session):
        import datetime
        now = datetime.datetime.now()
        # Get contributions for current month
        resp = auth_session.get(f"{BASE_URL}/api/contributions/status/{now.year}/{now.month}")
        assert resp.status_code == 200
        entries = resp.json()
        # Find a paid contribution
        paid = [e for e in entries if e.get("status") == "paid" and e.get("contribution_id")]
        assert len(paid) > 0, "No paid contributions found to test receipt download"
        contrib_id = paid[0]["contribution_id"]
        # Download receipt
        receipt_resp = auth_session.get(f"{BASE_URL}/api/contributions/{contrib_id}/receipt")
        assert receipt_resp.status_code == 200, f"Receipt download failed: {receipt_resp.text}"
        assert receipt_resp.headers.get("Content-Type", "").startswith("application/pdf")
        assert len(receipt_resp.content) > 100, "PDF content seems too small"

    def test_receipt_invalid_id(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/contributions/000000000000000000000000/receipt")
        assert resp.status_code == 404


class TestBenefitsAndMedical:
    """Test benefits workflow"""

    def test_benefits_list(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/benefits")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_medical_aid_list(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/medical-aid")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_cashbook_entries_exist(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/cashbook")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0, "Cashbook should have entries after seeding"
