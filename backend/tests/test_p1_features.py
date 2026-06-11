"""
P1 Feature Tests: QR Card, Meeting Minutes PDF, Committee Handovers
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@twenty20wariyad.com"
ADMIN_PASS = "Admin@20W20"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    resp = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return s


@pytest.fixture(scope="module")
def member_id(session):
    resp = session.get(f"{BASE_URL}/api/members")
    assert resp.status_code == 200
    members = resp.json()
    if not members:
        pytest.skip("No members in DB to test QR card")
    return members[0]["id"]


@pytest.fixture(scope="module")
def meeting_id(session):
    resp = session.get(f"{BASE_URL}/api/meetings")
    assert resp.status_code == 200
    meetings = resp.json()
    if not meetings:
        pytest.skip("No meetings in DB to test minutes PDF")
    return meetings[0]["id"]


class TestQRCard:
    """QR Card PDF endpoint tests"""

    def test_qr_card_returns_200(self, session, member_id):
        resp = session.get(f"{BASE_URL}/api/members/{member_id}/qr-card")
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"

    def test_qr_card_content_type_pdf(self, session, member_id):
        resp = session.get(f"{BASE_URL}/api/members/{member_id}/qr-card")
        assert "application/pdf" in resp.headers.get("content-type", "")

    def test_qr_card_has_content(self, session, member_id):
        resp = session.get(f"{BASE_URL}/api/members/{member_id}/qr-card")
        assert len(resp.content) > 1000, "PDF content seems too small"

    def test_qr_card_404_for_invalid_id(self, session):
        resp = session.get(f"{BASE_URL}/api/members/000000000000000000000000/qr-card")
        assert resp.status_code == 404


class TestMinutesPDF:
    """Meeting Minutes PDF endpoint tests"""

    def test_minutes_pdf_returns_200(self, session, meeting_id):
        resp = session.get(f"{BASE_URL}/api/meetings/{meeting_id}/minutes-pdf")
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"

    def test_minutes_pdf_content_type(self, session, meeting_id):
        resp = session.get(f"{BASE_URL}/api/meetings/{meeting_id}/minutes-pdf")
        assert "application/pdf" in resp.headers.get("content-type", "")

    def test_minutes_pdf_has_content(self, session, meeting_id):
        resp = session.get(f"{BASE_URL}/api/meetings/{meeting_id}/minutes-pdf")
        assert len(resp.content) > 1000

    def test_minutes_pdf_404_for_invalid(self, session):
        resp = session.get(f"{BASE_URL}/api/meetings/000000000000000000000000/minutes-pdf")
        assert resp.status_code == 404


class TestMeetingResolutions:
    """Meeting resolutions_list persistence tests"""

    def test_update_meeting_with_resolutions_list(self, session, meeting_id):
        resolutions = [
            {"text": "TEST resolution 1 - passed", "status": "passed"},
            {"text": "TEST resolution 2 - failed", "status": "failed"},
            {"text": "TEST resolution 3 - tabled", "status": "tabled"},
        ]
        resp = session.put(f"{BASE_URL}/api/meetings/{meeting_id}",
                           json={"resolutions_list": resolutions, "status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        assert "resolutions_list" in data
        assert len(data["resolutions_list"]) == 3

    def test_resolutions_persist_on_get(self, session, meeting_id):
        resp = session.get(f"{BASE_URL}/api/meetings")
        assert resp.status_code == 200
        meetings = resp.json()
        meeting = next((m for m in meetings if m["id"] == meeting_id), None)
        assert meeting is not None
        assert meeting.get("resolutions_list") is not None
        assert len(meeting["resolutions_list"]) >= 1


class TestHandovers:
    """Committee Handover CRUD tests"""
    _created_id = None

    def test_list_handovers_returns_200(self, session):
        resp = session.get(f"{BASE_URL}/api/committee/handovers")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_handover(self, session):
        payload = {
            "from_year": 2023,
            "to_year": 2024,
            "handover_date": "2024-01-15",
            "fund_balance": 50000.0,
            "documents_checklist": [
                {"item": "Minutes Book", "checked": True},
                {"item": "Membership Register", "checked": True},
                {"item": "Cashbook Register", "checked": False},
                {"item": "Bank Passbook / Statement", "checked": True},
                {"item": "Benefit Applications File", "checked": False},
                {"item": "Receipt Book", "checked": True},
                {"item": "Voucher Files", "checked": True},
                {"item": "Previous Audit Reports", "checked": False},
            ],
            "registers_checklist": [
                {"item": "Member Photo Register", "checked": True},
                {"item": "Meeting Register", "checked": True},
                {"item": "Benefit Register", "checked": False},
                {"item": "Medical Aid Register", "checked": True},
                {"item": "Death Assistance Register", "checked": False},
                {"item": "Collection Register", "checked": True},
            ],
            "outstanding_items": "TEST outstanding items",
            "notes": "TEST handover notes",
        }
        resp = session.post(f"{BASE_URL}/api/committee/handovers", json=payload)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data["from_year"] == 2023
        assert data["to_year"] == 2024
        assert data["fund_balance"] == 50000.0
        assert len(data["documents_checklist"]) == 8
        assert len(data["registers_checklist"]) == 6
        assert "id" in data
        TestHandovers._created_id = data["id"]

    def test_handover_in_list_after_create(self, session):
        resp = session.get(f"{BASE_URL}/api/committee/handovers")
        assert resp.status_code == 200
        items = resp.json()
        if TestHandovers._created_id:
            ids = [h["id"] for h in items]
            assert TestHandovers._created_id in ids

    def test_handover_checklist_count(self, session):
        """Verify the newly created handover has correct checklist counts"""
        resp = session.get(f"{BASE_URL}/api/committee/handovers")
        items = resp.json()
        if TestHandovers._created_id:
            h = next((x for x in items if x["id"] == TestHandovers._created_id), None)
            assert h is not None, "Created handover not found in list"
            assert len(h.get("documents_checklist", [])) == 8
            assert len(h.get("registers_checklist", [])) == 6
