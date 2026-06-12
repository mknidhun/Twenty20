"""
Security fixes test suite - covering 14 security fixes:
- Privilege escalation prevention
- IDOR protection
- Brute-force lockout
- Aadhaar masking
- Disabled account enforcement
- Secretary role restrictions
- Self-deletion prevention
- ObjectId safety (400 vs 500)
- Password length validation
- Email validation
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@twenty20wariyad.com"
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "")
SEC_EMAIL = "sectest@test.com"
SEC_PASS = "SecPass@123"


@pytest.fixture(scope="module")
def admin_session():
    """Login as super_admin, return session with cookies."""
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def secretary_session():
    """Login as secretary, return session with cookies."""
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": SEC_EMAIL, "password": SEC_PASS})
    if r.status_code != 200:
        pytest.skip(f"Secretary login failed: {r.text}")
    return s


# ── 1. Register with role=super_admin must return role=member ─────────────────
class TestRegisterPrivilegeEscalation:
    """Registration always creates member role regardless of requested role"""

    def test_register_with_super_admin_role_creates_member(self):
        unique_email = f"test_reg_{uuid.uuid4().hex[:8]}@test.com"
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Test Priv Escalation",
            "email": unique_email,
            "password": "TestPass@123",
            "role": "super_admin"
        })
        assert r.status_code == 200, f"Register failed: {r.text}"
        data = r.json()
        assert data["role"] == "member", f"Expected role=member but got role={data['role']}"
        print(f"PASS: Register with role=super_admin returned role={data['role']}")

    def test_register_with_president_role_creates_member(self):
        unique_email = f"test_reg2_{uuid.uuid4().hex[:8]}@test.com"
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Test President Escalation",
            "email": unique_email,
            "password": "TestPass@123",
            "role": "president"
        })
        assert r.status_code == 200, f"Register failed: {r.text}"
        data = r.json()
        assert data["role"] == "member", f"Expected role=member but got role={data['role']}"
        print(f"PASS: Register with role=president returned role={data['role']}")


# ── 2. Brute-force lockout ────────────────────────────────────────────────────
class TestBruteForce:
    """5 wrong attempts → 429 on attempt 6"""

    def test_brute_force_lockout(self):
        # Use unique email to avoid affecting other tests
        target_email = f"bf_target_{uuid.uuid4().hex[:6]}@test.com"
        for i in range(5):
            r = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": target_email,
                "password": "WrongPassword123"
            })
            assert r.status_code in (401, 422), f"Attempt {i+1} expected 401/422, got {r.status_code}: {r.text}"
            print(f"Attempt {i+1}: {r.status_code}")

        # 6th attempt must return 429
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": target_email,
            "password": "WrongPassword123"
        })
        assert r.status_code == 429, f"Expected 429 on attempt 6, got {r.status_code}: {r.text}"
        print(f"PASS: Brute force lockout triggered on attempt 6, status={r.status_code}")


# ── 3. Disabled user login must return 403 ────────────────────────────────────
class TestDisabledAccount:
    """Disabled users cannot login or use token"""

    def test_disabled_user_login_returns_403(self, admin_session):
        # Create a user then disable it
        unique_email = f"test_disabled_{uuid.uuid4().hex[:8]}@test.com"
        r = admin_session.post(f"{BASE_URL}/api/users", json={
            "name": "Disabled Test User",
            "email": unique_email,
            "password": "TestPass@123",
            "role": "member"
        })
        assert r.status_code == 200, f"User creation failed: {r.text}"
        uid = r.json()["id"]

        # Disable user
        r = admin_session.put(f"{BASE_URL}/api/users/{uid}", json={"is_active": False})
        assert r.status_code == 200, f"Disable user failed: {r.text}"

        # Login as disabled user → 403
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": "TestPass@123"
        })
        assert r.status_code == 403, f"Expected 403 for disabled user login, got {r.status_code}: {r.text}"
        print(f"PASS: Disabled user login returned {r.status_code}")

        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/users/{uid}")

    def test_disabled_user_token_returns_403_on_me(self, admin_session):
        # Create user, login to get token, then disable
        unique_email = f"test_tok_dis_{uuid.uuid4().hex[:8]}@test.com"
        r = admin_session.post(f"{BASE_URL}/api/users", json={
            "name": "Token Disabled User",
            "email": unique_email,
            "password": "TestPass@123",
            "role": "member"
        })
        assert r.status_code == 200
        uid = r.json()["id"]

        # Login to get cookies
        user_session = requests.Session()
        r = user_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": "TestPass@123"
        })
        assert r.status_code == 200, f"Login failed: {r.text}"

        # Disable user
        admin_session.put(f"{BASE_URL}/api/users/{uid}", json={"is_active": False})

        # Use existing token → 403
        r = user_session.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 403, f"Expected 403 for disabled token, got {r.status_code}: {r.text}"
        print(f"PASS: Disabled user token returned {r.status_code} on /me")

        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/users/{uid}")


# ── 4. Secretary role restrictions ───────────────────────────────────────────
class TestSecretaryRestrictions:
    """Secretary cannot assign privileged roles"""

    def test_secretary_cannot_create_super_admin(self, secretary_session):
        unique_email = f"test_sec_priv_{uuid.uuid4().hex[:8]}@test.com"
        r = secretary_session.post(f"{BASE_URL}/api/users", json={
            "name": "Secretary Priv Test",
            "email": unique_email,
            "password": "TestPass@123",
            "role": "super_admin"
        })
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print(f"PASS: Secretary cannot create super_admin user, got {r.status_code}")

    def test_secretary_can_create_member(self, secretary_session, admin_session):
        unique_email = f"test_sec_mem_{uuid.uuid4().hex[:8]}@test.com"
        r = secretary_session.post(f"{BASE_URL}/api/users", json={
            "name": "Secretary Member Test",
            "email": unique_email,
            "password": "TestPass@123",
            "role": "member"
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        uid = r.json()["id"]
        print(f"PASS: Secretary can create member user")

        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/users/{uid}")


# ── 5. Self-deletion prevention ───────────────────────────────────────────────
class TestSelfDeletion:
    """Super admin cannot delete own account"""

    def test_super_admin_cannot_delete_self(self, admin_session):
        me = admin_session.get(f"{BASE_URL}/api/auth/me")
        assert me.status_code == 200
        admin_id = me.json()["id"]

        r = admin_session.delete(f"{BASE_URL}/api/users/{admin_id}")
        assert r.status_code == 400, f"Expected 400 for self-deletion, got {r.status_code}: {r.text}"
        print(f"PASS: Self-deletion prevented, got {r.status_code}")


# ── 6. Aadhaar masking ────────────────────────────────────────────────────────
class TestAadhaarMasking:
    """Aadhaar masked for non-super_admin, unmasked for super_admin"""

    def test_aadhaar_masked_for_non_super_admin(self, secretary_session, admin_session):
        # Create a member with aadhaar
        r = admin_session.post(f"{BASE_URL}/api/members", json={
            "name": "Aadhaar Test Member",
            "mobile": "9876543210",
            "address": "Test Address",
            "joining_date": "2024-01-01",
            "status": "active",
            "aadhaar": "123456789012"
        })
        assert r.status_code == 200, f"Member creation failed: {r.text}"
        member_id = r.json()["id"]

        # Fetch as secretary
        r = secretary_session.get(f"{BASE_URL}/api/members")
        assert r.status_code == 200
        members = r.json()
        test_member = next((m for m in members if m["id"] == member_id), None)
        assert test_member is not None, "Test member not found in list"
        assert test_member.get("aadhaar") is not None
        assert "XXXX" in test_member["aadhaar"], f"Aadhaar should be masked, got: {test_member['aadhaar']}"
        print(f"PASS: Aadhaar masked for secretary: {test_member['aadhaar']}")

        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/members/{member_id}")

    def test_aadhaar_unmasked_for_super_admin(self, admin_session):
        # Create a member with aadhaar
        r = admin_session.post(f"{BASE_URL}/api/members", json={
            "name": "Aadhaar Test Super",
            "mobile": "9876543211",
            "address": "Test Address 2",
            "joining_date": "2024-01-01",
            "status": "active",
            "aadhaar": "987654321098"
        })
        assert r.status_code == 200
        member_id = r.json()["id"]

        r = admin_session.get(f"{BASE_URL}/api/members")
        assert r.status_code == 200
        members = r.json()
        test_member = next((m for m in members if m["id"] == member_id), None)
        assert test_member is not None
        # super_admin should see real aadhaar (no XXXX)
        assert "XXXX" not in (test_member.get("aadhaar") or ""), f"Aadhaar should NOT be masked for super_admin, got: {test_member.get('aadhaar')}"
        print(f"PASS: Aadhaar unmasked for super_admin: {test_member.get('aadhaar')}")

        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/members/{member_id}")


# ── 7. ObjectId safety ────────────────────────────────────────────────────────
class TestObjectIdSafety:
    """Malformed IDs return 400 not 500"""

    def test_malformed_qr_card_id_returns_400(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/members/not-a-valid-objectid/qr-card")
        assert r.status_code == 400, f"Expected 400 for malformed ID, got {r.status_code}: {r.text}"
        print(f"PASS: Malformed QR card ID returns {r.status_code}")

    def test_malformed_contribution_receipt_id_returns_400(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/contributions/not-a-valid-id/receipt")
        assert r.status_code == 400, f"Expected 400 for malformed ID, got {r.status_code}: {r.text}"
        print(f"PASS: Malformed contribution receipt ID returns {r.status_code}")


# ── 8. Member IDOR: cannot access another member's receipt ───────────────────
class TestReceiptIDOR:
    """Member cannot access another member's receipt"""

    def test_member_cannot_access_other_member_receipt(self, admin_session):
        # Create two members
        m1 = admin_session.post(f"{BASE_URL}/api/members", json={
            "name": "IDOR Test Member1",
            "mobile": "9999999991",
            "address": "Test Addr",
            "joining_date": "2024-01-01",
            "status": "active"
        }).json()
        m2 = admin_session.post(f"{BASE_URL}/api/members", json={
            "name": "IDOR Test Member2",
            "mobile": "9999999992",
            "address": "Test Addr",
            "joining_date": "2024-01-01",
            "status": "active"
        }).json()

        # Create user accounts for m1 and m2
        user1_email = f"idor_u1_{uuid.uuid4().hex[:6]}@test.com"
        user2_email = f"idor_u2_{uuid.uuid4().hex[:6]}@test.com"

        u1 = admin_session.post(f"{BASE_URL}/api/users", json={
            "name": "IDOR User1",
            "email": user1_email,
            "password": "TestPass@123",
            "role": "member",
            "member_id": m1["member_id"]
        }).json()
        u2 = admin_session.post(f"{BASE_URL}/api/users", json={
            "name": "IDOR User2",
            "email": user2_email,
            "password": "TestPass@123",
            "role": "member",
            "member_id": m2["member_id"]
        }).json()

        # Create a contribution for member 2
        contrib_r = admin_session.post(f"{BASE_URL}/api/contributions", json={
            "member_id": m2["id"],
            "month": 1,
            "year": 2025,
            "amount": 100.0,
            "payment_method": "cash"
        })
        assert contrib_r.status_code == 200, f"Contribution creation failed: {contrib_r.text}"
        contrib_id = contrib_r.json()["id"]

        # Login as user1 (member with m1's member_id)
        s1 = requests.Session()
        login_r = s1.post(f"{BASE_URL}/api/auth/login", json={
            "email": user1_email,
            "password": "TestPass@123"
        })
        assert login_r.status_code == 200

        # User1 tries to access contribution belonging to member2 → 403
        r = s1.get(f"{BASE_URL}/api/contributions/{contrib_id}/receipt")
        assert r.status_code == 403, f"Expected 403 for IDOR attempt, got {r.status_code}: {r.text}"
        print(f"PASS: Member IDOR prevented, got {r.status_code}")

        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/contributions/{contrib_id}")
        admin_session.delete(f"{BASE_URL}/api/users/{u1['id']}")
        admin_session.delete(f"{BASE_URL}/api/users/{u2['id']}")
        admin_session.delete(f"{BASE_URL}/api/members/{m1['id']}")
        admin_session.delete(f"{BASE_URL}/api/members/{m2['id']}")


# ── 9. Password length validation ────────────────────────────────────────────
class TestPasswordValidation:
    def test_register_short_password_returns_422(self):
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Short Pass",
            "email": f"shortpass_{uuid.uuid4().hex[:6]}@test.com",
            "password": "abc123"  # 6 chars < 8
        })
        assert r.status_code == 422, f"Expected 422 for short password, got {r.status_code}: {r.text}"
        print(f"PASS: Short password returns {r.status_code}")


# ── 10. Email validation ──────────────────────────────────────────────────────
class TestEmailValidation:
    def test_register_invalid_email_returns_422(self):
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Bad Email",
            "email": "not-an-email",
            "password": "ValidPass@123"
        })
        assert r.status_code == 422, f"Expected 422 for invalid email, got {r.status_code}: {r.text}"
        print(f"PASS: Invalid email returns {r.status_code}")


# ── 11. Core endpoints still work ────────────────────────────────────────────
class TestCoreEndpoints:
    def test_admin_login_works(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASS
        })
        assert r.status_code == 200, f"Admin login failed: {r.text}"
        data = r.json()
        assert data["role"] == "super_admin"
        print(f"PASS: Admin login works, role={data['role']}")

    def test_get_members_returns_data(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/members")
        assert r.status_code == 200, f"Failed: {r.text}"
        assert isinstance(r.json(), list)
        print(f"PASS: /api/members returns {len(r.json())} records")

    def test_get_contributions_returns_data(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/contributions")
        assert r.status_code == 200, f"Failed: {r.text}"
        assert isinstance(r.json(), list)
        print(f"PASS: /api/contributions returns {len(r.json())} records")

    def test_dashboard_returns_data(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/dashboard/stats")
        assert r.status_code == 200, f"Failed: {r.text}"
        print(f"PASS: /api/dashboard/stats returns data")
