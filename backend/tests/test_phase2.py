"""Phase 2 feature tests: Export Reports, Notifications, Audit Module"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

ADMIN_EMAIL = "admin@twenty20wariyad.com"
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "")
AUDITOR_EMAIL = "auditor@twenty20wariyad.com"
AUDITOR_PASS = "Auditor@123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def auditor_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": AUDITOR_EMAIL, "password": AUDITOR_PASS})
    assert r.status_code == 200, f"Auditor login failed: {r.text}"
    return s


# ── Export Reports ──────────────────────────────────────────────────────────

class TestExportReports:
    """GET /api/reports/export/excel and /api/reports/export/pdf"""

    def test_export_excel_returns_200_with_xlsx(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/reports/export/excel?year=2026")
        assert r.status_code == 200, f"Excel export failed: {r.text}"
        ct = r.headers.get("content-type", "")
        assert "spreadsheetml" in ct or "octet-stream" in ct, f"Unexpected content-type: {ct}"
        # xlsx magic bytes: PK
        assert r.content[:2] == b'PK', "Response is not a valid xlsx (missing PK header)"

    def test_export_pdf_returns_200_with_pdf(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/reports/export/pdf?year=2026")
        assert r.status_code == 200, f"PDF export failed: {r.text}"
        ct = r.headers.get("content-type", "")
        assert "pdf" in ct or "octet-stream" in ct, f"Unexpected content-type: {ct}"
        assert r.content[:4] == b'%PDF', "Response is not a valid PDF"

    def test_export_excel_unauthenticated_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/reports/export/excel?year=2026")
        assert r.status_code == 401


# ── Notifications ────────────────────────────────────────────────────────────

class TestNotifications:
    """GET /api/notifications/defaulters and POST /api/notifications/send-reminders"""

    def test_get_defaulters_returns_200(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/notifications/defaulters?month=1&year=2026")
        assert r.status_code == 200
        data = r.json()
        assert "total_active" in data
        assert "total_paid" in data
        assert "total_defaulters" in data
        assert "defaulters" in data
        assert "twilio_enabled" in data
        assert data["twilio_enabled"] == False, "Expected mock mode (twilio_enabled=false)"

    def test_get_defaulters_has_month_year(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/notifications/defaulters?month=2&year=2025")
        assert r.status_code == 200
        data = r.json()
        assert data["month"] == 2
        assert data["year"] == 2025

    def test_send_reminders_mock_mode(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/notifications/send-reminders",
                               json={"month": 1, "year": 2026})
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] in ["mock", "none"], f"Expected mock mode, got: {data['mode']}"

    def test_send_reminders_mock_results_structure(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/notifications/send-reminders",
                               json={"month": 1, "year": 2026})
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert "message" in data
        # In mock mode, each result should have sms=mock, whatsapp=mock
        for result in data.get("results", []):
            assert result.get("sms") == "mock"
            assert result.get("whatsapp") == "mock"

    def test_notifications_unauthenticated_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/notifications/defaulters?month=1&year=2026")
        assert r.status_code == 401


# ── Audit Module ─────────────────────────────────────────────────────────────

class TestAudit:
    """GET /api/audit/report, GET /api/audit/sign-offs, POST /api/audit/sign-off"""

    def test_get_audit_report_returns_200(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/audit/report?year=2026")
        assert r.status_code == 200
        data = r.json()
        assert "year" in data
        assert "active_members" in data
        assert "total_contributions" in data
        assert "closing_balance" in data

    def test_audit_report_has_monthly_breakdown(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/audit/report?year=2026")
        assert r.status_code == 200
        data = r.json()
        assert "monthly_breakdown" in data
        assert isinstance(data["monthly_breakdown"], list)

    def test_get_sign_offs_returns_list(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/audit/sign-offs")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_super_admin_cannot_sign_off(self, admin_session):
        """super_admin should get 403 on sign-off endpoint"""
        r = admin_session.post(f"{BASE_URL}/api/audit/sign-off",
                               json={"year": 2026, "remarks": "Admin trying to sign off"})
        assert r.status_code == 403, f"Expected 403 for super_admin sign-off, got {r.status_code}"

    def test_auditor_can_sign_off(self, auditor_session):
        """Auditor can sign off (will succeed or 400 if already signed)"""
        r = auditor_session.post(f"{BASE_URL}/api/audit/sign-off",
                                 json={"year": 2099, "remarks": "TEST_audit sign-off for year 2099"})
        # Either 200 (success) or 400 (already signed)
        assert r.status_code in [200, 400], f"Unexpected status: {r.status_code} {r.text}"

    def test_auditor_cannot_sign_off_twice(self, auditor_session):
        """Signing off twice for same year returns 400"""
        year = 2098
        # First sign-off
        r1 = auditor_session.post(f"{BASE_URL}/api/audit/sign-off",
                                   json={"year": year, "remarks": "TEST_first sign-off"})
        if r1.status_code == 200:
            # Second sign-off should fail
            r2 = auditor_session.post(f"{BASE_URL}/api/audit/sign-off",
                                       json={"year": year, "remarks": "TEST_second sign-off"})
            assert r2.status_code == 400, f"Expected 400 for duplicate sign-off, got {r2.status_code}"
        else:
            # Already signed for this year from a prior run
            assert r1.status_code == 400

    def test_audit_report_unauthenticated_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/audit/report?year=2026")
        assert r.status_code == 401

    def test_auditor_can_access_audit_report(self, auditor_session):
        r = auditor_session.get(f"{BASE_URL}/api/audit/report?year=2026")
        assert r.status_code == 200
