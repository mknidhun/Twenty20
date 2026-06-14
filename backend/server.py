"""Twenty20 Wariyad API — PostgreSQL edition (SQLModel / SQLAlchemy async).

Ported from the original MongoDB/motor implementation. Same routes, same request/
response shapes, same auth/JWT/cookies/PDF/Excel/Twilio behavior. Only the data
access layer changed: motor collections -> SQLModel async sessions.
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, UploadFile, File
from fastapi.responses import Response, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from fpdf import FPDF
from pathlib import Path
import os, jwt, bcrypt, logging, io, time, uuid as _uuidlib, pandas as pd
import qrcode

# ── PDF fonts/logo (Latin + Malayalam fallback) ───────────────────────────────
LOGO_WHITE = str(Path(__file__).parent / "assets" / "logo_white.png")
FONT_DIR = Path(__file__).parent / "assets" / "fonts"

def new_pdf(*args, **kwargs) -> FPDF:
    """FPDF instance with Unicode fonts registered (Latin primary + Malayalam fallback)."""
    pdf = FPDF(*args, **kwargs)
    pdf.add_font("noto", "", str(FONT_DIR / "NotoSans-Regular.ttf"))
    pdf.add_font("noto", "B", str(FONT_DIR / "NotoSans-Bold.ttf"))
    pdf.add_font("noto", "I", str(FONT_DIR / "NotoSans-Italic.ttf"))
    pdf.add_font("notoml", "", str(FONT_DIR / "NotoSansMalayalam-Regular.ttf"))
    pdf.add_font("notoml", "B", str(FONT_DIR / "NotoSansMalayalam-Bold.ttf"))
    pdf.set_fallback_fonts(["notoml"], exact_match=False)
    return pdf

from sqlalchemy import select, func, delete as sqldelete
from sqlalchemy.ext.asyncio import AsyncSession
from db import get_session, init_db, async_session_maker, engine
from models import (
    User, Member, Benefit, MedicalAid, DeathAssistance,
    Cashbook, Committee, CommitteeHandover, Meeting, NotificationLog, AuditSignOff,
    OrgSettings, MonthlyDues, Payment,
)
from ledger import (
    month_index, resolve_rate, build_ledger, allocate_payment, _status as _ledger_status,
)

# Twilio (optional — graceful fallback if credentials not configured)
try:
    from twilio.rest import Client as TwilioClient
    _TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    _TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    _TWILIO_FROM = os.environ.get("TWILIO_FROM_PHONE", "")
    _TWILIO_WA_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "")
    TWILIO_ENABLED = bool(_TWILIO_SID and _TWILIO_TOKEN and _TWILIO_FROM)
except Exception:
    TwilioClient = None
    _TWILIO_FROM = _TWILIO_WA_FROM = ""
    TWILIO_ENABLED = False

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Security constants ────────────────────────────────────────────────────────
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() != "false"
PRIVILEGED_ROLES = {"super_admin", "president", "auditor"}

# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_ALGORITHM = "HS256"
def get_jwt_secret() -> str:
    secret = os.environ["JWT_SECRET"]
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 characters")
    return secret

def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(hours=8)}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "type": "refresh",
               "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

# ── Password ──────────────────────────────────────────────────────────────────
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

# ── ID helpers ────────────────────────────────────────────────────────────────
def safe_id(val: str) -> str:
    """Validate a UUID path/query param, raising 400 on bad input."""
    try:
        return str(_uuidlib.UUID(str(val)))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(400, "Invalid ID format")

def row_to_dict(obj) -> Optional[dict]:
    """Serialize a SQLModel row to a plain dict (drops password_hash)."""
    if obj is None:
        return None
    d = obj.model_dump()
    d.pop("password_hash", None)
    return d

def _member_owns(user: dict, member: Optional["Member"]) -> bool:
    """True if `user` (role=member) owns the member record (match on id or TW- code)."""
    if not member:
        return False
    uid = str(user.get("member_id") or "")
    return uid in (str(member.id), str(member.member_id))

# ── Brute-force rate limiter (in-memory, 5 attempts / 15 min per email) ───
_login_attempts: dict = defaultdict(list)
_RATE_MAX = 5
_RATE_WINDOW = 900

def _check_rate_limit(email: str, ip: str):
    key = email.lower()
    now = time.time()
    hits = [t for t in _login_attempts[key] if now - t < _RATE_WINDOW]
    _login_attempts[key] = hits
    if len(hits) >= _RATE_MAX:
        raise HTTPException(429, "Too many login attempts. Try again in 15 minutes.")
    _login_attempts[key].append(now)

def _reset_rate_limit(email: str, ip: str):
    _login_attempts.pop(email.lower(), None)

# ── Auth helpers ──────────────────────────────────────────────────────────────
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(401, "Invalid token type")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    async with async_session_maker() as session:
        user = await session.get(User, payload["sub"])
    if not user:
        raise HTTPException(401, "User not found")
    if user.is_active is False:
        raise HTTPException(403, "Account is disabled")
    d = user.model_dump()
    d.pop("password_hash", None)
    return d

def require_roles(*roles):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return checker


# ── ID generators ─────────────────────────────────────────────────────────────
async def next_member_id(session: AsyncSession) -> str:
    res = await session.execute(select(Member.member_id).order_by(Member.member_id.desc()).limit(1))
    last = res.scalar_one_or_none()
    if last:
        try:
            return f"TW-{(int(last.split('-')[-1]) + 1):03d}"
        except (ValueError, IndexError):
            pass
    return "TW-001"

async def next_receipt(session: AsyncSession) -> str:
    yr = datetime.now().year
    res = await session.execute(select(func.count()).select_from(Payment).where(Payment.year == yr))
    return f"RCP-{yr}-{(res.scalar_one() + 1):04d}"

async def next_voucher(session: AsyncSession) -> str:
    res = await session.execute(select(func.count()).select_from(Cashbook))
    return f"VCH-{datetime.now().year}-{(res.scalar_one() + 1):04d}"


# ── LEDGER SERVICE (DB-backed; math lives in ledger.py) ───────────────────────
async def get_settings(session: AsyncSession) -> OrgSettings:
    """Return the single org_settings row, creating defaults on first use."""
    res = await session.execute(select(OrgSettings).limit(1))
    s = res.scalar_one_or_none()
    if not s:
        s = OrgSettings()
        session.add(s)
        await session.commit()
        await session.refresh(s)
    return s


def _ym_parse(s: Optional[str], default=None):
    """Parse 'YYYY-MM' or 'YYYY-MM-DD' -> (year, month). None-safe."""
    if not s:
        return default
    parts = str(s).split("-")
    try:
        return (int(parts[0]), int(parts[1]))
    except (IndexError, ValueError):
        return default


async def member_ledger(session: AsyncSession, member: Member, settings: OrgSettings,
                        through_year: int, through_month: int):
    """Build a member's full month-by-month ledger using stored dues+payments."""
    join = _ym_parse(member.joining_date, (datetime.now().year, datetime.now().month))
    start = _ym_parse(member.ledger_start, join)
    inactive = _ym_parse(member.inactive_from, None)
    # paid-per-month from MonthlyDues; the synthetic (year=0,month=0) row is the
    # paydown applied to the member's opening pending balance.
    dres = await session.execute(select(MonthlyDues).where(MonthlyDues.member_id == member.id))
    all_dues = dres.scalars().all()
    paid_by_month = {(d.year, d.month): d.paid for d in all_dues if not (d.year == 0 and d.month == 0)}
    opening_paid = sum(d.paid for d in all_dues if d.year == 0 and d.month == 0)
    # opening balance, reduced by any paydown already applied to opening pending
    eff_opening = int(member.opening_balance or 0) + int(opening_paid)
    rows = build_ledger(
        join[0], join[1], paid_by_month,
        standard_rate=int(settings.standard_rate),
        intro_rate=int(settings.intro_rate),
        intro_months=int(settings.intro_months),
        member_intro_rate=(int(member.intro_rate) if member.intro_rate is not None else None),
        through_year=through_year, through_month=through_month,
        opening_balance=eff_opening,
        inactive_from=inactive, start_year=start[0], start_month=start[1],
    )
    return rows


async def member_balance(session: AsyncSession, member: Member, settings: OrgSettings):
    """Current balance (− pending / + advance) and status for a member, as of now."""
    now = datetime.now()
    rows = await member_ledger(session, member, settings, now.year, now.month)
    if not rows:
        return {"balance": 0, "status": "Up to Date", "outstanding": 0, "advance": 0}
    last = rows[-1]
    return {
        "balance": last.balance,
        "status": last.status,
        "outstanding": max(0, -last.balance),
        "advance": max(0, last.balance),
    }


# ── Pydantic request models ───────────────────────────────────────────────────
class LoginReq(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "member"
    member_id: Optional[str] = None
    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class MemberCreate(BaseModel):
    name: str
    mobile: str
    address: str
    joining_date: str
    status: str = "active"
    aadhaar: Optional[str] = None
    intro_rate: Optional[float] = None        # first-year monthly rate (defaults to org intro rate)
    opening_balance: float = 0.0              # − pending / + advance carried in before ledger_start
    ledger_start: Optional[str] = None        # "YYYY-MM" the opening balance applies to

class MemberUpdate(BaseModel):
    name: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None
    aadhaar: Optional[str] = None
    intro_rate: Optional[float] = None
    opening_balance: Optional[float] = None
    ledger_start: Optional[str] = None
    inactive_from: Optional[str] = None       # "YYYY-MM" — stop accruing dues

class PaymentCreate(BaseModel):
    member_id: str
    amount: float                             # may be partial, exact, or over the month's rate
    payment_method: str
    month: int
    year: int

class SettingsUpdate(BaseModel):
    standard_rate: Optional[float] = None
    intro_rate: Optional[float] = None
    intro_months: Optional[int] = None

class BenefitCreate(BaseModel):
    member_id: str
    benefit_type: str
    event_date: str
    notes: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None

class MedicalAidCreate(BaseModel):
    applicant_name: str
    contact: str
    address: str
    medical_condition: str
    hospital: str
    estimated_expense: float
    notes: Optional[str] = None

class MedicalAidUpdate(BaseModel):
    status: Optional[str] = None
    recommended_amount: Optional[float] = None
    notes: Optional[str] = None

class DeathCreate(BaseModel):
    deceased_name: str
    member_id: Optional[str] = None
    family_details: str
    address: str
    contact_person: str
    date_of_death: str

class DeathUpdate(BaseModel):
    grocery_kit_value: Optional[float] = None
    delivery_date: Optional[str] = None
    remarks: Optional[str] = None
    status: Optional[str] = None

class CashbookCreate(BaseModel):
    entry_type: str
    category: str
    description: str
    amount: float
    date: str
    reference_id: Optional[str] = None

class CommitteeCreate(BaseModel):
    year: int
    positions: List[dict]
    start_date: str
    end_date: str

class MeetingCreate(BaseModel):
    meeting_type: str
    title: str
    scheduled_date: str
    agenda: str
    attendees: Optional[List[str]] = []

class MeetingUpdate(BaseModel):
    minutes: Optional[str] = None
    resolutions: Optional[str] = None
    resolutions_list: Optional[List[dict]] = None
    status: Optional[str] = None
    attendees: Optional[List[str]] = None

class CommitteeHandoverCreate(BaseModel):
    from_year: int
    to_year: int
    handover_date: str
    fund_balance: float
    documents_checklist: List[dict]
    registers_checklist: List[dict]
    outstanding_items: Optional[str] = None
    notes: Optional[str] = None

class AuditSignOffCreate(BaseModel):
    year: int
    remarks: str

class NotificationSendReq(BaseModel):
    month: int
    year: int
    message: Optional[str] = None


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Twenty20 Wariyad API")
api_router = APIRouter(prefix="/api")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in FRONTEND_URL.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

def set_auth_cookies(response: Response, at: str, rt: str):
    response.set_cookie("access_token", at, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=28800)
    response.set_cookie("refresh_token", rt, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=604800)


# ── AUTH ──────────────────────────────────────────────────────────────────────
@api_router.post("/auth/register")
async def register(data: UserCreate, response: Response, session: AsyncSession = Depends(get_session)):
    email = data.email.lower().strip()
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")
    # Self-registration always creates a plain member (no privileged role from client).
    user = User(name=data.name, email=email, password_hash=hash_password(data.password),
                role="member", member_id=None, is_active=True)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    at = create_access_token(user.id, email)
    rt = create_refresh_token(user.id)
    set_auth_cookies(response, at, rt)
    return {"id": user.id, "name": user.name, "email": email, "role": "member"}

@api_router.post("/auth/login")
async def login(data: LoginReq, request: Request, response: Response, session: AsyncSession = Depends(get_session)):
    email = data.email.lower().strip()
    ip = request.client.host if request.client else ""
    _check_rate_limit(email, ip)
    res = await session.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if user.is_active is False:
        raise HTTPException(403, "Account is disabled")
    _reset_rate_limit(email, ip)
    at = create_access_token(user.id, email)
    rt = create_refresh_token(user.id)
    set_auth_cookies(response, at, rt)
    return {"id": user.id, "name": user.name, "email": user.email,
            "role": user.role, "member_id": user.member_id}

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out"}

@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ── USERS ─────────────────────────────────────────────────────────────────────
@api_router.get("/users")
async def list_users(user: dict = Depends(require_roles("super_admin", "president", "secretary")),
                     session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(User))
    return [row_to_dict(u) for u in res.scalars().all()]

@api_router.post("/users")
async def create_user(data: UserCreate, user: dict = Depends(require_roles("super_admin", "secretary")),
                      session: AsyncSession = Depends(get_session)):
    email = data.email.lower().strip()
    if data.role in PRIVILEGED_ROLES and user["role"] != "super_admin":
        raise HTTPException(403, "Only super_admin can assign privileged roles")
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")
    u = User(name=data.name, email=email, password_hash=hash_password(data.password),
             role=data.role, member_id=data.member_id, is_active=True)
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return {"id": u.id, "name": u.name, "email": email, "role": u.role}

@api_router.put("/users/{uid}")
async def update_user(uid: str, data: UserUpdate, user: dict = Depends(require_roles("super_admin")),
                      session: AsyncSession = Depends(get_session)):
    u = await session.get(User, safe_id(uid))
    if not u:
        raise HTTPException(404, "User not found")
    for k, v in data.model_dump().items():
        if v is not None:
            setattr(u, k, v)
    await session.commit()
    await session.refresh(u)
    return row_to_dict(u)

@api_router.delete("/users/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_roles("super_admin")),
                      session: AsyncSession = Depends(get_session)):
    uid = safe_id(uid)
    if uid == user["id"]:
        raise HTTPException(400, "Cannot delete your own account")
    u = await session.get(User, uid)
    if u:
        await session.delete(u)
        await session.commit()
    return {"message": "User deleted"}


# ── MEMBERS ───────────────────────────────────────────────────────────────────
def _mask_aadhaar(d: Optional[dict], role: str) -> Optional[dict]:
    """Mask Aadhaar for all non-super_admin roles."""
    if d and d.get("aadhaar") and role != "super_admin":
        raw = d["aadhaar"].replace("-", "").replace(" ", "")
        d["aadhaar"] = "XXXX-XXXX-" + (raw[-4:] if len(raw) >= 4 else "****")
    return d

@api_router.get("/members")
async def list_members(with_balance: bool = True, user: dict = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Member).order_by(Member.created_at.desc()))
    members = res.scalars().all()
    settings = await get_settings(session) if with_balance else None
    out = []
    for m in members:
        d = _mask_aadhaar(m.model_dump(), user["role"])
        if with_balance:
            bal = await member_balance(session, m, settings)
            d.update({"balance": bal["balance"], "balance_status": bal["status"],
                      "outstanding": bal["outstanding"], "advance": bal["advance"]})
        out.append(d)
    return out

@api_router.post("/members")
async def create_member(data: MemberCreate, user: dict = Depends(require_roles("super_admin", "secretary", "treasurer")),
                        session: AsyncSession = Depends(get_session)):
    mid = await next_member_id(session)
    m = Member(member_id=mid, **data.model_dump())
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m.model_dump()

# ── BULK IMPORT (must be before /{mid} to avoid routing conflict) ─────────────
@api_router.get("/members/import-template")
async def import_template():
    csv_content = (
        "name,mobile,address,joining_date,status,aadhaar\n"
        "Mohammed Ashraf,9876543210,\"House No 12 Main Road Wariyad\",2024-01-15,active,\n"
        "Suhail Ahmed,9876543211,\"Near Mosque Wariyad\",2024-02-20,active,123456789012\n"
        "Fathima Beevi,9876543212,\"Colony Road Wariyad\",2024-03-10,active,\n"
    )
    return Response(content=csv_content, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=members_template.csv"})

def build_member_qr_card(member: dict) -> bytes:
    qr_data = (
        f"Twenty20 Charity Group Wariyad\n"
        f"Name: {member.get('name','')}\n"
        f"Member ID: {member.get('member_id','')}\n"
        f"Mobile: {member.get('mobile','')}"
    )
    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(qr_data); qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#166534", back_color="white")
    qr_buf = io.BytesIO(); qr_img.save(qr_buf, format="PNG"); qr_buf.seek(0)

    pdf = new_pdf(orientation="L", format=(54, 86))
    pdf.set_margins(0, 0, 0); pdf.add_page()
    pdf.set_fill_color(22, 101, 52); pdf.rect(0, 0, 86, 14, "F")
    try: pdf.image(LOGO_WHITE, x=2, y=2, h=10)
    except Exception: pass
    pdf.set_text_color(255, 255, 255); pdf.set_font("noto", "B", 7); pdf.set_y(2)
    pdf.cell(0, 5, "TWENTY20 CHARITY GROUP  WARIYAD", align="C", ln=True)
    pdf.set_font("noto", "", 6); pdf.cell(0, 4, "Verified Member Card", align="C", ln=True)
    pdf.set_text_color(28, 25, 23); pdf.set_y(17); pdf.set_x(3)
    pdf.set_font("noto", "B", 11); pdf.cell(48, 7, member.get("name", ""), ln=True)
    pdf.set_x(3); pdf.set_font("noto", "B", 8); pdf.set_text_color(22, 101, 52)
    pdf.cell(48, 5, member.get("member_id", ""), ln=True)
    pdf.set_x(3); pdf.set_text_color(80, 80, 80); pdf.set_font("noto", "", 7)
    pdf.cell(48, 4, f"Mobile: {member.get('mobile', '-')}", ln=True)
    pdf.set_x(3); pdf.cell(48, 4, f"Joined: {member.get('joining_date', '-')}", ln=True)
    pdf.set_x(3); pdf.set_y(42); pdf.set_fill_color(220, 252, 231)
    pdf.set_draw_color(22, 101, 52); pdf.set_text_color(22, 101, 52); pdf.set_font("noto", "B", 6)
    pdf.cell(20, 5, "  ACTIVE", border=1, fill=True, align="C")
    pdf.image(qr_buf, x=54, y=14, w=29, h=29)
    pdf.set_fill_color(22, 101, 52); pdf.rect(0, 49, 86, 5, "F")
    pdf.set_text_color(255, 255, 255); pdf.set_font("noto", "", 5); pdf.set_y(50)
    pdf.cell(0, 3, "This card is the property of Twenty20 Charity Group Wariyad", align="C")
    return bytes(pdf.output())

@api_router.get("/members/{mid}/qr-card")
async def download_member_qr_card(mid: str, user: dict = Depends(get_current_user),
                                  session: AsyncSession = Depends(get_session)):
    member = await session.get(Member, safe_id(mid))
    if not member:
        raise HTTPException(404, "Member not found")
    if user["role"] == "member" and not _member_owns(user, member):
        raise HTTPException(403, "Access denied")
    pdf_bytes = build_member_qr_card(member.model_dump())
    name_slug = (member.name or "member").replace(" ", "_").encode("ascii", "ignore").decode() or member.member_id
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=MemberCard_{name_slug}.pdf"})

@api_router.put("/members/{mid}")
async def update_member(mid: str, data: MemberUpdate, user: dict = Depends(require_roles("super_admin", "secretary", "treasurer")),
                        session: AsyncSession = Depends(get_session)):
    m = await session.get(Member, safe_id(mid))
    if not m:
        raise HTTPException(404, "Member not found")
    for k, v in data.model_dump().items():
        if v is not None:
            setattr(m, k, v)
    await session.commit()
    await session.refresh(m)
    return _mask_aadhaar(m.model_dump(), user["role"])

@api_router.delete("/members/{mid}")
async def delete_member(mid: str, user: dict = Depends(require_roles("super_admin")),
                        session: AsyncSession = Depends(get_session)):
    m = await session.get(Member, safe_id(mid))
    if m:
        await session.delete(m)
        await session.commit()
    return {"message": "Member deleted"}

@api_router.post("/members/import")
async def import_members(file: UploadFile = File(...),
                         user: dict = Depends(require_roles("super_admin", "secretary")),
                         session: AsyncSession = Depends(get_session)):
    content = await file.read()
    fname = (file.filename or "").lower()
    try:
        if fname.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif fname.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(400, "Only CSV (.csv) and Excel (.xlsx/.xls) files are supported")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Error parsing file: {str(e)}")
    df.columns = [str(c).lower().strip().replace(" ", "_") for c in df.columns]
    required = ["name", "mobile", "address"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(400, f"Missing required columns: {', '.join(missing)}. Required: name, mobile, address")
    imported = skipped = 0
    errors = []
    for i, row in df.iterrows():
        try:
            name = str(row.get("name", "")).strip()
            if not name or name.lower() == "nan":
                skipped += 1
                continue
            mobile = str(row.get("mobile", "")).strip()
            address = str(row.get("address", "")).strip()
            jd_raw = row.get("joining_date", row.get("joining date", ""))
            joining_date = str(jd_raw).strip() if str(jd_raw).strip() not in ("nan", "", "NaT") else datetime.now().date().isoformat()
            if not (len(joining_date) == 10 and joining_date[4] == "-"):
                try:
                    joining_date = pd.to_datetime(joining_date).strftime("%Y-%m-%d")
                except Exception:
                    joining_date = datetime.now().date().isoformat()
            status_raw = str(row.get("status", "active")).strip().lower()
            status = status_raw if status_raw in ("active", "inactive", "resigned", "deceased") else "active"
            aadhaar_raw = str(row.get("aadhaar", "")).strip()
            aadhaar = aadhaar_raw if aadhaar_raw not in ("nan", "") else None
            mid = await next_member_id(session)
            session.add(Member(member_id=mid, name=name, mobile=mobile, address=address,
                               joining_date=joining_date, status=status, aadhaar=aadhaar))
            await session.commit()
            imported += 1
        except Exception as e:
            await session.rollback()
            errors.append(f"Row {i + 2}: {str(e)}")
    return {"imported": imported, "skipped": skipped, "errors": errors, "total_rows": len(df),
            "message": f"Successfully imported {imported} members."
            + (f" Skipped {skipped} empty rows." if skipped else "")
            + (f" {len(errors)} rows had errors." if errors else "")}


def _is_uuid(val) -> bool:
    try:
        _uuidlib.UUID(str(val)); return True
    except (ValueError, AttributeError, TypeError):
        return False


# ── SETTINGS (contribution rates) ─────────────────────────────────────────────
@api_router.get("/settings")
async def read_settings(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    s = await get_settings(session)
    return {"standard_rate": s.standard_rate, "intro_rate": s.intro_rate,
            "intro_months": s.intro_months, "updated_at": s.updated_at}

@api_router.put("/settings")
async def update_settings(data: SettingsUpdate, user: dict = Depends(require_roles("super_admin", "treasurer")),
                          session: AsyncSession = Depends(get_session)):
    s = await get_settings(session)
    for k, v in data.model_dump().items():
        if v is not None:
            setattr(s, k, v)
    s.updated_by = user["id"]; s.updated_at = datetime.now(timezone.utc).isoformat()
    await session.commit(); await session.refresh(s)
    return {"standard_rate": s.standard_rate, "intro_rate": s.intro_rate,
            "intro_months": s.intro_months, "updated_at": s.updated_at}


# ── CONTRIBUTIONS (ledger model: dues + payments) ─────────────────────────────
@api_router.get("/contributions")
async def list_payments(member_id: Optional[str] = None, year: Optional[int] = None,
                        month: Optional[int] = None, user: dict = Depends(get_current_user),
                        session: AsyncSession = Depends(get_session)):
    """List payment events (the 'contributions' the UI shows). Members see only their own."""
    stmt = select(Payment)
    if member_id:
        stmt = stmt.where(Payment.member_id == member_id)
    elif user["role"] == "member" and user.get("member_id"):
        stmt = stmt.where(Payment.member_id == user["member_id"])
    if year:
        stmt = stmt.where(Payment.year == year)
    if month:
        stmt = stmt.where(Payment.month == month)
    stmt = stmt.order_by(Payment.paid_at.desc()).limit(2000)
    res = await session.execute(stmt)
    return [p.model_dump() for p in res.scalars().all()]


@api_router.post("/contributions/pay")
async def record_payment(data: PaymentCreate, user: dict = Depends(require_roles("super_admin", "treasurer")),
                         session: AsyncSession = Depends(get_session)):
    """Record a payment of any amount. Applies oldest arrears first, then current
    month, then advance — updating the member's monthly_dues ledger, writing one
    cashbook credit, and returning the allocation + updated balance."""
    if not _is_uuid(data.member_id):
        raise HTTPException(400, "Invalid member ID")
    member = await session.get(Member, data.member_id)
    if not member:
        raise HTTPException(404, "Member not found")
    if data.amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    settings = await get_settings(session)

    # 1) Ensure a MonthlyDues row exists for every month from ledger start..target,
    #    so arrears are concrete and allocatable.
    now_ref = (data.year, data.month)
    join = _ym_parse(member.joining_date, now_ref)
    start = _ym_parse(member.ledger_start, join)
    inactive = _ym_parse(member.inactive_from, None)
    existing = {(d.year, d.month): d for d in (await session.execute(
        select(MonthlyDues).where(MonthlyDues.member_id == member.id))).scalars().all()}
    idx = month_index(*start)
    end_idx = month_index(*now_ref)
    while idx <= end_idx:
        yy, mm = divmod(idx, 12); mm += 1
        if (yy, mm) not in existing:
            if inactive and month_index(yy, mm) >= month_index(*inactive):
                rate = 0
            else:
                rate = resolve_rate(join[0], join[1], yy, mm,
                                    standard_rate=int(settings.standard_rate),
                                    intro_rate=int(settings.intro_rate),
                                    intro_months=int(settings.intro_months),
                                    member_intro_rate=(int(member.intro_rate) if member.intro_rate is not None else None))
            d = MonthlyDues(member_id=member.id, year=yy, month=mm, rate=rate, paid=0.0)
            session.add(d); existing[(yy, mm)] = d
        idx += 1
    await session.commit()

    # 2) Compute arrears (oldest-first). The member's opening_balance pending is the
    #    OLDEST arrear (a synthetic pre-ledger bucket), tracked via a stored
    #    "opening_paid" running tally encoded as paid on the start-month row's negative
    #    space. Simpler + correct: derive remaining opening pending from current balance.
    ordered = sorted(existing.values(), key=lambda d: (d.year, d.month))
    arrears = []
    # opening pending still outstanding = original opening pending minus what prior
    # payments already absorbed (reconstructed from ledger: any month's paid beyond
    # its own rate flowed to opening/older — but we keep it explicit below).
    opening_pending = max(0, -int(member.opening_balance or 0))
    # How much of opening has been paid so far = total paid across dues that exceeds
    # the dues' own rates is NOT how we track it; instead store opening paydown on the
    # member via a dedicated field-free approach: recompute from ledger up to (but not
    # including) this payment. Since ledger already reflects stored `paid`, the opening
    # pending remaining = opening_pending reduced by (extra paid already applied to it).
    # We track that extra as paid recorded on the synthetic key ("OPENING").
    opening_row = existing.get(("OPENING",))
    opening_paid_so_far = (opening_row.paid if opening_row else 0)
    opening_remaining = max(0, opening_pending - int(opening_paid_so_far))
    if opening_remaining > 0:
        arrears.append(("OPENING", 0, opening_remaining))
    for d in ordered:
        if (d.year, d.month) == now_ref:
            continue
        owed = (d.rate or 0) - (d.paid or 0)
        if owed > 0:
            arrears.append((d.year, d.month, owed))
    current = existing[now_ref]
    current_owed = max(0, (current.rate or 0) - (current.paid or 0))

    # 3) Allocate
    alloc = allocate_payment(int(data.amount), prior_balance=0, current_rate=int(current_owed),
                             arrears_months=arrears)
    # apply to arrears months
    detail = []
    for (yy, mm, amt) in alloc.detail:
        if yy == "OPENING":
            # record opening paydown on a synthetic MonthlyDues row (year=0,month=0)
            orow = existing.get(("OPENING",))
            if not orow:
                orow = MonthlyDues(member_id=member.id, year=0, month=0, rate=0, paid=0.0)
                session.add(orow); existing[("OPENING",)] = orow
            orow.paid = (orow.paid or 0) + amt
            detail.append({"year": "opening", "month": 0, "amount": amt, "kind": "arrears"})
        else:
            existing[(yy, mm)].paid = (existing[(yy, mm)].paid or 0) + amt
            detail.append({"year": yy, "month": mm, "amount": amt, "kind": "arrears"})
    if alloc.applied_to_current:
        current.paid = (current.paid or 0) + alloc.applied_to_current
        detail.append({"year": now_ref[0], "month": now_ref[1], "amount": alloc.applied_to_current, "kind": "current"})
    if alloc.advance:
        # advance is recorded on the payment; it reduces future dues implicitly via balance
        detail.append({"year": now_ref[0], "month": now_ref[1], "amount": alloc.advance, "kind": "advance"})

    # refresh status snapshots on touched dues
    for d in existing.values():
        bal = (d.paid or 0) - (d.rate or 0)
        d.status = "up_to_date" if bal == 0 else ("advance" if bal > 0 else "pending")

    receipt = await next_receipt(session)
    pay = Payment(member_id=member.id, amount=data.amount, payment_method=data.payment_method,
                  year=data.year, month=data.month, receipt_number=receipt,
                  allocation=detail, recorded_by=user["id"])
    session.add(pay)
    # cashbook credit (one entry per payment)
    session.add(Cashbook(
        entry_type="credit", category="contribution",
        description=f"Contribution - {member.name} ({data.year}/{data.month:02d})",
        amount=data.amount, date=datetime.now(timezone.utc).date().isoformat(),
        reference_id=member.id, voucher_number=await next_voucher(session), recorded_by=user["id"]))
    await session.commit()
    await session.refresh(pay)

    bal = await member_balance(session, member, settings)
    out = pay.model_dump()
    out.update({"member_name": member.name, "member_code": member.member_id,
                "balance": bal["balance"], "balance_status": bal["status"], "allocation": detail})
    return out


@api_router.get("/contributions/ledger/{member_id}")
async def get_member_ledger(member_id: str, through: Optional[str] = None,
                            user: dict = Depends(get_current_user),
                            session: AsyncSession = Depends(get_session)):
    """Full month-by-month ledger for one member (Prior Pending/Advance, Rate, Paid, Balance, Status)."""
    member = await session.get(Member, safe_id(member_id))
    if not member:
        raise HTTPException(404, "Member not found")
    if user["role"] == "member" and not _member_owns(user, member):
        raise HTTPException(403, "Access denied")
    settings = await get_settings(session)
    ty, tm = _ym_parse(through, (datetime.now().year, datetime.now().month))
    rows = await member_ledger(session, member, settings, ty, tm)
    return {
        "member": {"id": member.id, "name": member.name, "member_code": member.member_id,
                   "joining_date": member.joining_date, "intro_rate": member.intro_rate,
                   "status": member.status},
        "rows": [{"year": r.year, "month": r.month, "prior_pending": r.prior_pending,
                  "prior_advance": r.prior_advance, "rate": r.rate, "paid": r.paid,
                  "balance": r.balance, "status": r.status} for r in rows],
    }


@api_router.get("/contributions/status/{year}/{month}")
async def contribution_status(year: int, month: int, user: dict = Depends(get_current_user),
                              session: AsyncSession = Depends(get_session)):
    """Monthly grid mirroring a sheet tab: every active member's prior pending/advance,
    rate, paid, balance, status for the given month."""
    settings = await get_settings(session)
    members = (await session.execute(select(Member).where(Member.status == "active"))).scalars().all()
    result = []
    for m in members:
        rows = await member_ledger(session, m, settings, year, month)
        row = next((r for r in rows if r.year == year and r.month == month), None)
        if row is None:
            continue   # member's ledger doesn't reach this month (joined later)
        result.append({
            "member_id": m.id, "member_name": m.name, "member_code": m.member_id,
            "prior_pending": row.prior_pending, "prior_advance": row.prior_advance,
            "rate": row.rate, "paid": row.paid, "balance": row.balance, "status": row.status,
            "is_paid": row.balance >= 0,
        })
    return result


@api_router.delete("/contributions/{pid}")
async def delete_payment(pid: str, user: dict = Depends(require_roles("super_admin", "treasurer")),
                         session: AsyncSession = Depends(get_session)):
    """Reverse a payment: subtract its allocation from monthly_dues, delete the payment."""
    p = await session.get(Payment, safe_id(pid))
    if not p:
        return {"message": "Deleted"}
    dues = {(d.year, d.month): d for d in (await session.execute(
        select(MonthlyDues).where(MonthlyDues.member_id == p.member_id))).scalars().all()}
    for item in (p.allocation or []):
        if item.get("kind") in ("arrears", "current"):
            d = dues.get((item["year"], item["month"]))
            if d:
                d.paid = max(0, (d.paid or 0) - item["amount"])
                bal = (d.paid or 0) - (d.rate or 0)
                d.status = "up_to_date" if bal == 0 else ("advance" if bal > 0 else "pending")
    await session.delete(p)
    await session.commit()
    return {"message": "Deleted"}


# ── BENEFITS ──────────────────────────────────────────────────────────────────
BENEFIT_AMOUNTS = {"marriage": 5000, "housewarming": 3000}

@api_router.get("/benefits")
async def list_benefits(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    stmt = select(Benefit)
    if user["role"] == "member" and user.get("member_id"):
        stmt = stmt.where(Benefit.member_id == user["member_id"])
    stmt = stmt.order_by(Benefit.created_at.desc()).limit(500)
    res = await session.execute(stmt)
    return [b.model_dump() for b in res.scalars().all()]

@api_router.post("/benefits")
async def apply_benefit(data: BenefitCreate, user: dict = Depends(get_current_user),
                        session: AsyncSession = Depends(get_session)):
    if not _is_uuid(data.member_id):
        raise HTTPException(400, "Invalid member ID")
    member = await session.get(Member, data.member_id)
    if not member:
        raise HTTPException(404, "Member not found")
    if member.status != "active":
        raise HTTPException(400, "Member is not active")
    dup = await session.execute(select(Benefit).where(
        Benefit.member_id == data.member_id, Benefit.benefit_type == data.benefit_type,
        Benefit.status.not_in(["rejected"])))
    if dup.scalar_one_or_none():
        raise HTTPException(400, f"{data.benefit_type.capitalize()} benefit already applied")
    b = Benefit(**data.model_dump(), member_name=member.name,
                amount=BENEFIT_AMOUNTS.get(data.benefit_type, 0), status="pending", applied_by=user["id"])
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return b.model_dump()

@api_router.put("/benefits/{bid}/status")
async def update_benefit_status(bid: str, data: StatusUpdate, user: dict = Depends(get_current_user),
                                session: AsyncSession = Depends(get_session)):
    b = await session.get(Benefit, safe_id(bid))
    if not b:
        raise HTTPException(404, "Benefit not found")
    now = datetime.now(timezone.utc).isoformat()
    st = data.status
    b.status = st
    if data.notes:
        b.notes = data.notes
    if st == "secretary_verified":
        if user["role"] not in ["super_admin", "secretary"]:
            raise HTTPException(403, "Secretary only")
        b.secretary_verified_by = user["id"]; b.secretary_verified_at = now
    elif st == "committee_approved":
        if user["role"] not in ["super_admin", "president", "committee_member"]:
            raise HTTPException(403, "Committee only")
        b.committee_approved_by = user["id"]; b.committee_approved_at = now
    elif st == "paid":
        if user["role"] not in ["super_admin", "treasurer"]:
            raise HTTPException(403, "Treasurer only")
        b.paid_by = user["id"]; b.paid_at = now
        session.add(Cashbook(
            entry_type="debit", category=f"{b.benefit_type}_benefit",
            description=f"{b.benefit_type.capitalize()} benefit - {b.member_name}",
            amount=b.amount, date=datetime.now(timezone.utc).date().isoformat(),
            reference_id=b.id, voucher_number=await next_voucher(session), recorded_by=user["id"]))
    elif st == "rejected":
        b.rejected_by = user["id"]; b.rejected_at = now
    await session.commit()
    await session.refresh(b)
    return b.model_dump()


# ── MEDICAL AID ───────────────────────────────────────────────────────────────
@api_router.get("/medical-aid")
async def list_medical_aid(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(MedicalAid).order_by(MedicalAid.created_at.desc()).limit(500))
    return [m.model_dump() for m in res.scalars().all()]

@api_router.post("/medical-aid")
async def apply_medical_aid(data: MedicalAidCreate, user: dict = Depends(get_current_user),
                            session: AsyncSession = Depends(get_session)):
    m = MedicalAid(**data.model_dump(), status="pending", applied_by=user["id"])
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m.model_dump()

@api_router.put("/medical-aid/{aid_id}")
async def update_medical_aid(aid_id: str, data: MedicalAidUpdate, user: dict = Depends(get_current_user),
                             session: AsyncSession = Depends(get_session)):
    m = await session.get(MedicalAid, safe_id(aid_id))
    if not m:
        raise HTTPException(404, "Not found")
    now = datetime.now(timezone.utc).isoformat()
    for k, v in data.model_dump().items():
        if v is not None:
            setattr(m, k, v)
    if data.status == "approved":
        m.approved_by = user["id"]; m.approved_at = now
    elif data.status == "paid":
        session.add(Cashbook(
            entry_type="debit", category="medical_aid",
            description=f"Medical aid - {m.applicant_name}",
            amount=m.recommended_amount or m.estimated_expense or 0,
            date=datetime.now(timezone.utc).date().isoformat(),
            reference_id=m.id, voucher_number=await next_voucher(session), recorded_by=user["id"]))
        m.paid_by = user["id"]; m.paid_at = now
    await session.commit()
    await session.refresh(m)
    return m.model_dump()

@api_router.delete("/medical-aid/{aid_id}")
async def delete_medical_aid(aid_id: str, user: dict = Depends(require_roles("super_admin")),
                             session: AsyncSession = Depends(get_session)):
    m = await session.get(MedicalAid, safe_id(aid_id))
    if m:
        await session.delete(m); await session.commit()
    return {"message": "Deleted"}


# ── DEATH ASSISTANCE ──────────────────────────────────────────────────────────
@api_router.get("/death-assistance")
async def list_death_assistance(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(DeathAssistance).order_by(DeathAssistance.created_at.desc()).limit(500))
    return [d.model_dump() for d in res.scalars().all()]

@api_router.post("/death-assistance")
async def create_death_assistance(data: DeathCreate, user: dict = Depends(get_current_user),
                                  session: AsyncSession = Depends(get_session)):
    d = DeathAssistance(**data.model_dump(), status="pending", created_by=user["id"])
    session.add(d)
    await session.commit()
    await session.refresh(d)
    return d.model_dump()

@api_router.put("/death-assistance/{case_id}")
async def update_death_assistance(case_id: str, data: DeathUpdate, user: dict = Depends(get_current_user),
                                  session: AsyncSession = Depends(get_session)):
    d = await session.get(DeathAssistance, safe_id(case_id))
    if not d:
        raise HTTPException(404, "Not found")
    for k, v in data.model_dump().items():
        if v is not None:
            setattr(d, k, v)
    if data.status == "approved":
        d.approved_by = user["id"]; d.approved_at = datetime.now(timezone.utc).isoformat()
    await session.commit()
    await session.refresh(d)
    return d.model_dump()

@api_router.delete("/death-assistance/{case_id}")
async def delete_death_assistance(case_id: str, user: dict = Depends(require_roles("super_admin")),
                                  session: AsyncSession = Depends(get_session)):
    d = await session.get(DeathAssistance, safe_id(case_id))
    if d:
        await session.delete(d); await session.commit()
    return {"message": "Deleted"}


# ── CASHBOOK ──────────────────────────────────────────────────────────────────
@api_router.get("/cashbook")
async def list_cashbook(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Cashbook).order_by(Cashbook.created_at.asc()).limit(5000))
    serialized = [e.model_dump() for e in res.scalars().all()]
    balance = 0.0
    for e in serialized:
        balance += e["amount"] if e["entry_type"] == "credit" else -e["amount"]
        e["running_balance"] = round(balance, 2)
    serialized.reverse()
    return serialized

@api_router.post("/cashbook")
async def create_cashbook_entry(data: CashbookCreate, user: dict = Depends(require_roles("super_admin", "treasurer")),
                                session: AsyncSession = Depends(get_session)):
    e = Cashbook(**data.model_dump(), voucher_number=await next_voucher(session), recorded_by=user["id"])
    session.add(e)
    await session.commit()
    await session.refresh(e)
    return e.model_dump()

@api_router.delete("/cashbook/{eid}")
async def delete_cashbook_entry(eid: str, user: dict = Depends(require_roles("super_admin", "treasurer")),
                                session: AsyncSession = Depends(get_session)):
    e = await session.get(Cashbook, safe_id(eid))
    if e:
        await session.delete(e); await session.commit()
    return {"message": "Deleted"}


# ── COMMITTEE ─────────────────────────────────────────────────────────────────
@api_router.get("/committee")
async def list_committees(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Committee).order_by(Committee.year.desc()).limit(50))
    return [c.model_dump() for c in res.scalars().all()]

@api_router.post("/committee")
async def create_committee(data: CommitteeCreate, user: dict = Depends(require_roles("super_admin", "president", "secretary")),
                           session: AsyncSession = Depends(get_session)):
    c = Committee(**data.model_dump(), is_active=True, created_by=user["id"])
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c.model_dump()

@api_router.get("/committee/handovers")
async def list_handovers(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(CommitteeHandover).order_by(CommitteeHandover.handover_date.desc()).limit(100))
    return [h.model_dump() for h in res.scalars().all()]

@api_router.post("/committee/handovers")
async def create_handover(data: CommitteeHandoverCreate,
                          user: dict = Depends(require_roles("super_admin", "president", "secretary")),
                          session: AsyncSession = Depends(get_session)):
    h = CommitteeHandover(**data.model_dump(), recorded_by=user["id"], recorded_by_name=user["name"])
    session.add(h)
    await session.commit()
    await session.refresh(h)
    return h.model_dump()

@api_router.put("/committee/{cid}")
async def update_committee(cid: str, data: dict, user: dict = Depends(require_roles("super_admin", "president")),
                           session: AsyncSession = Depends(get_session)):
    c = await session.get(Committee, safe_id(cid))
    if not c:
        raise HTTPException(404, "Not found")
    for k, v in data.items():
        if hasattr(c, k):
            setattr(c, k, v)
    await session.commit()
    await session.refresh(c)
    return c.model_dump()

@api_router.delete("/committee/{cid}")
async def delete_committee(cid: str, user: dict = Depends(require_roles("super_admin")),
                           session: AsyncSession = Depends(get_session)):
    c = await session.get(Committee, safe_id(cid))
    if c:
        await session.delete(c); await session.commit()
    return {"message": "Deleted"}


# ── MEETINGS ──────────────────────────────────────────────────────────────────
@api_router.get("/meetings")
async def list_meetings(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Meeting).order_by(Meeting.scheduled_date.desc()).limit(200))
    return [m.model_dump() for m in res.scalars().all()]

@api_router.post("/meetings")
async def create_meeting(data: MeetingCreate, user: dict = Depends(require_roles("super_admin", "president", "secretary")),
                         session: AsyncSession = Depends(get_session)):
    m = Meeting(**data.model_dump(), status="scheduled", created_by=user["id"])
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m.model_dump()

@api_router.put("/meetings/{mid}")
async def update_meeting(mid: str, data: MeetingUpdate, user: dict = Depends(get_current_user),
                         session: AsyncSession = Depends(get_session)):
    m = await session.get(Meeting, safe_id(mid))
    if not m:
        raise HTTPException(404, "Not found")
    for k, v in data.model_dump().items():
        if v is not None:
            setattr(m, k, v)
    await session.commit()
    await session.refresh(m)
    return m.model_dump()

@api_router.delete("/meetings/{mid}")
async def delete_meeting(mid: str, user: dict = Depends(require_roles("super_admin", "president", "secretary")),
                         session: AsyncSession = Depends(get_session)):
    m = await session.get(Meeting, safe_id(mid))
    if m:
        await session.delete(m); await session.commit()
    return {"message": "Deleted"}

def build_minutes_pdf(meeting: dict) -> bytes:
    TYPE_LABELS_PDF = {"executive": "Executive Committee Meeting",
                       "annual_general": "Annual General Body Meeting", "emergency": "Emergency Meeting"}
    pdf = new_pdf(); pdf.set_margins(15, 15, 15); pdf.add_page()
    pdf.set_fill_color(22, 101, 52); pdf.rect(0, 0, 210, 42, "F")
    try: pdf.image(LOGO_WHITE, x=12, y=7, h=28)
    except Exception: pass
    pdf.set_text_color(255, 255, 255); pdf.set_y(10); pdf.set_font("noto", "B", 16)
    pdf.cell(0, 9, "TWENTY20 CHARITY GROUP", ln=True, align="C")
    pdf.set_font("noto", "B", 10); pdf.cell(0, 6, "WARIYAD", ln=True, align="C")
    pdf.set_font("noto", "", 8); pdf.cell(0, 5, "Meeting Minutes", ln=True, align="C")
    pdf.set_y(50); pdf.set_text_color(28, 25, 23)
    meeting_type = TYPE_LABELS_PDF.get(meeting.get("meeting_type", ""), meeting.get("meeting_type", ""))
    pdf.set_font("noto", "B", 13); pdf.set_text_color(22, 101, 52)
    pdf.multi_cell(0, 8, meeting.get("title", ""), align="C"); pdf.ln(2)
    pdf.set_draw_color(200, 200, 200); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(4)
    pdf.set_text_color(28, 25, 23)
    for label, val in [("Meeting Type", meeting_type), ("Date", meeting.get("scheduled_date", "")),
                       ("Status", (meeting.get("status", "") or "").title())]:
        pdf.set_font("noto", "B", 10); pdf.cell(50, 6, label + ":", ln=False)
        pdf.set_font("noto", "", 10); pdf.cell(0, 6, val, ln=True)
    attendees = meeting.get("attendees") or []
    if attendees:
        pdf.ln(3); pdf.set_font("noto", "B", 10); pdf.cell(0, 6, f"Attendees ({len(attendees)}):", ln=True)
        pdf.set_font("noto", "", 10); pdf.multi_cell(0, 6, ", ".join(attendees))
    pdf.ln(3); pdf.set_font("noto", "B", 11); pdf.set_text_color(22, 101, 52); pdf.cell(0, 7, "AGENDA", ln=True)
    pdf.set_draw_color(200, 200, 200); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(3)
    pdf.set_text_color(28, 25, 23); pdf.set_font("noto", "", 10); pdf.multi_cell(0, 6, meeting.get("agenda", ""))
    if meeting.get("minutes"):
        pdf.ln(4); pdf.set_font("noto", "B", 11); pdf.set_text_color(22, 101, 52)
        pdf.cell(0, 7, "MINUTES OF MEETING", ln=True); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(3)
        pdf.set_text_color(28, 25, 23); pdf.set_font("noto", "", 10); pdf.multi_cell(0, 6, meeting.get("minutes", ""))
    resolutions_list = meeting.get("resolutions_list") or []
    if resolutions_list:
        pdf.ln(4); pdf.set_font("noto", "B", 11); pdf.set_text_color(22, 101, 52)
        pdf.cell(0, 7, "RESOLUTIONS", ln=True); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(3)
        for i, res in enumerate(resolutions_list, 1):
            status = (res.get("status", "passed") or "passed").upper()
            pdf.set_font("noto", "B", 10); pdf.set_text_color(28, 25, 23); pdf.cell(8, 6, f"{i}.", ln=False)
            pdf.set_font("noto", "", 10)
            pdf.set_text_color(*( (22,101,52) if status=="PASSED" else (185,28,28) if status=="FAILED" else (120,88,0)))
            pdf.cell(25, 6, f"[{status}]", ln=False)
            pdf.set_text_color(28, 25, 23); pdf.set_font("noto", "", 10); pdf.multi_cell(0, 6, res.get("text", ""))
    elif meeting.get("resolutions"):
        pdf.ln(4); pdf.set_font("noto", "B", 11); pdf.set_text_color(22, 101, 52)
        pdf.cell(0, 7, "RESOLUTIONS", ln=True); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(3)
        pdf.set_text_color(28, 25, 23); pdf.set_font("noto", "", 10); pdf.multi_cell(0, 6, meeting.get("resolutions", ""))
    pdf.ln(10); pdf.set_text_color(120, 113, 108); pdf.set_font("noto", "I", 8)
    pdf.set_draw_color(231, 229, 228); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(4)
    pdf.cell(0, 5, f"Minutes recorded on {datetime.now().strftime('%d %B %Y')} - Twenty20 Charity Group Wariyad", ln=True, align="C")
    return bytes(pdf.output())

@api_router.get("/meetings/{mid}/minutes-pdf")
async def download_minutes_pdf(mid: str, user: dict = Depends(get_current_user),
                               session: AsyncSession = Depends(get_session)):
    meeting = await session.get(Meeting, safe_id(mid))
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    pdf_bytes = build_minutes_pdf(meeting.model_dump())
    title_slug = (meeting.title or "minutes").replace(" ", "_")[:30].encode("ascii", "ignore").decode() or "minutes"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Minutes_{title_slug}.pdf"})


# ── DASHBOARD ─────────────────────────────────────────────────────────────────
async def _count(session, model, *conds):
    stmt = select(func.count()).select_from(model)
    for c in conds:
        stmt = stmt.where(c)
    return (await session.execute(stmt)).scalar_one()

@api_router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    now = datetime.now(); cm, cy = now.month, now.year
    total_members = await _count(session, Member, Member.status == "active")
    total_all_members = await _count(session, Member)
    pending_benefits = await _count(session, Benefit, Benefit.status.in_(["pending", "secretary_verified", "committee_approved"]))
    pending_medical = await _count(session, MedicalAid, MedicalAid.status.in_(["pending", "under_review"]))
    cb = (await session.execute(select(Cashbook))).scalars().all()
    balance = sum(e.amount * (1 if e.entry_type == "credit" else -1) for e in cb)
    tmc = (await session.execute(select(Payment).where(Payment.year == cy, Payment.month == cm))).scalars().all()
    monthly_collection = sum(c.amount for c in tmc)
    paid_benefits = (await session.execute(select(Benefit).where(Benefit.status == "paid"))).scalars().all()
    total_benefits_paid = sum(b.amount for b in paid_benefits)
    paid_medical = (await session.execute(select(MedicalAid).where(MedicalAid.status == "paid"))).scalars().all()
    total_medical_paid = sum((m.recommended_amount or m.estimated_expense or 0) for m in paid_medical)
    upcoming_meetings = await _count(session, Meeting, Meeting.status == "scheduled")
    pending_death = await _count(session, DeathAssistance, DeathAssistance.status == "pending")
    # Ledger totals: sum each active member's outstanding / advance as of now
    settings = await get_settings(session)
    active_members = (await session.execute(select(Member).where(Member.status == "active"))).scalars().all()
    total_outstanding = total_advance = 0
    for m in active_members:
        b = await member_balance(session, m, settings)
        total_outstanding += b["outstanding"]
        total_advance += b["advance"]
    return {"total_members": total_members, "total_all_members": total_all_members,
            "pending_benefits": pending_benefits, "pending_medical": pending_medical,
            "fund_balance": round(balance, 2), "monthly_collection": monthly_collection,
            "total_benefits_paid": total_benefits_paid, "total_medical_paid": total_medical_paid,
            "upcoming_meetings": upcoming_meetings, "pending_death": pending_death,
            "total_outstanding": round(total_outstanding, 2), "total_advance": round(total_advance, 2),
            "current_month": cm, "current_year": cy}

@api_router.get("/dashboard/recent-activity")
async def recent_activity(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    contribs = (await session.execute(select(Payment).order_by(Payment.paid_at.desc()).limit(5))).scalars().all()
    benefits = (await session.execute(select(Benefit).order_by(Benefit.created_at.desc()).limit(5))).scalars().all()
    return {"recent_contributions": [c.model_dump() for c in contribs],
            "recent_benefits": [b.model_dump() for b in benefits]}

@api_router.get("/dashboard/monthly-collections")
async def monthly_collections(year: Optional[int] = None, user: dict = Depends(get_current_user),
                              session: AsyncSession = Depends(get_session)):
    yr = year or datetime.now().year
    data = []
    for m in range(1, 13):
        docs = (await session.execute(select(Payment).where(Payment.year == yr, Payment.month == m))).scalars().all()
        data.append({"month": m, "count": len(docs), "total": sum(d.amount for d in docs)})
    return data


# ── REPORTS ───────────────────────────────────────────────────────────────────
@api_router.get("/reports/members")
async def report_members(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return {
        "total": await _count(session, Member),
        "active": await _count(session, Member, Member.status == "active"),
        "inactive": await _count(session, Member, Member.status == "inactive"),
        "resigned": await _count(session, Member, Member.status == "resigned"),
        "deceased": await _count(session, Member, Member.status == "deceased"),
    }

@api_router.get("/reports/contributions/{year}")
async def report_contributions(year: int, user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    docs = (await session.execute(select(Payment).where(Payment.year == year))).scalars().all()
    by_month: dict = {}
    for d in docs:
        by_month.setdefault(d.month, {"month": d.month, "count": 0, "total": 0})
        by_month[d.month]["count"] += 1
        by_month[d.month]["total"] += d.amount
    return {"year": year, "total": sum(d.amount for d in docs),
            "monthly": sorted(by_month.values(), key=lambda x: x["month"])}

@api_router.get("/reports/benefits")
async def report_benefits(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    m_docs = (await session.execute(select(Benefit).where(Benefit.benefit_type == "marriage", Benefit.status == "paid"))).scalars().all()
    h_docs = (await session.execute(select(Benefit).where(Benefit.benefit_type == "housewarming", Benefit.status == "paid"))).scalars().all()
    med_docs = (await session.execute(select(MedicalAid).where(MedicalAid.status == "paid"))).scalars().all()
    death = await _count(session, DeathAssistance, DeathAssistance.status == "delivered")
    return {
        "marriage_count": len(m_docs), "marriage_total": sum(d.amount for d in m_docs),
        "housewarming_count": len(h_docs), "housewarming_total": sum(d.amount for d in h_docs),
        "medical_count": len(med_docs),
        "medical_total": sum((d.recommended_amount or d.estimated_expense or 0) for d in med_docs),
        "death_count": death,
    }


@api_router.get("/reports/summary")
async def report_summary(from_ym: Optional[str] = None, to_ym: Optional[str] = None,
                         user: dict = Depends(require_roles("super_admin", "president", "treasurer", "secretary", "auditor")),
                         session: AsyncSession = Depends(get_session)):
    """Monthly contribution summary mirroring the spreadsheet 'Summary' tab:
    per month → members, up-to-date, pending, advance, total collected,
    total outstanding, total advance credit, collection rate."""
    settings = await get_settings(session)
    now = datetime.now()
    frm = _ym_parse(from_ym, (now.year, now.month))
    to = _ym_parse(to_ym, (now.year + (now.month + 10) // 12, (now.month + 10) % 12 + 1))  # ~12 months
    members = (await session.execute(select(Member))).scalars().all()
    # payments per (year,month) for "collected"
    pays = (await session.execute(select(Payment))).scalars().all()
    collected = {}
    for p in pays:
        collected[(p.year, p.month)] = collected.get((p.year, p.month), 0) + p.amount

    rows = []
    idx = month_index(*frm); end = month_index(*to)
    tot_collected = tot_out = tot_adv = 0
    while idx <= end:
        yy, mm = divmod(idx, 12); mm += 1
        up = pend = adv = 0
        out_sum = adv_sum = active = 0
        for m in members:
            if m.status != "active":
                continue
            mrows = await member_ledger(session, m, settings, yy, mm)
            row = next((r for r in mrows if r.year == yy and r.month == mm), None)
            if row is None:
                continue
            active += 1
            # Org definition (matches the spreadsheet Summary tab):
            # "Up to date" = not in arrears (balance >= 0); advance members are
            # ALSO counted in the Advance column (so up_to_date + pending = members,
            # and advance is an overlapping subset of up_to_date).
            if row.balance >= 0:
                up += 1
            else:
                pend += 1; out_sum += -row.balance
            if row.balance > 0:
                adv += 1; adv_sum += row.balance
        coll = collected.get((yy, mm), 0)
        rate = (up / active) if active else 0
        rows.append({"year": yy, "month": mm, "members": active, "up_to_date": up,
                     "pending": pend, "advance": adv, "collected": coll,
                     "outstanding": out_sum, "advance_credit": adv_sum,
                     "collection_rate": round(rate, 4)})
        tot_collected += coll; tot_out = out_sum; tot_adv = adv_sum  # outstanding/advance are point-in-time
        idx += 1
    return {"from": f"{frm[0]}-{frm[1]:02d}", "to": f"{to[0]}-{to[1]:02d}",
            "rows": rows, "total_collected": tot_collected,
            "current_outstanding": tot_out, "current_advance": tot_adv}


# ── PDF RECEIPT ───────────────────────────────────────────────────────────────
MONTHS_NAMES = ["","January","February","March","April","May","June",
                "July","August","September","October","November","December"]

def build_receipt_pdf(contrib: dict, member: Optional[dict]) -> bytes:
    pdf = new_pdf(); pdf.set_margins(15, 15, 15); pdf.add_page()
    pdf.set_fill_color(22, 101, 52); pdf.rect(0, 0, 210, 42, "F")
    try: pdf.image(LOGO_WHITE, x=12, y=7, h=28)
    except Exception: pass
    pdf.set_text_color(255, 255, 255); pdf.set_y(10); pdf.set_font("noto", "B", 18)
    pdf.cell(0, 9, "TWENTY20 CHARITY GROUP", ln=True, align="C")
    pdf.set_font("noto", "B", 11); pdf.cell(0, 7, "WARIYAD", ln=True, align="C")
    pdf.set_font("noto", "", 9); pdf.cell(0, 6, "Monthly Contribution Receipt", ln=True, align="C")
    pdf.set_y(50); pdf.set_text_color(28, 25, 23)
    def row(label, value, bold_val=False):
        pdf.set_font("noto", "B", 10); pdf.cell(60, 8, label, ln=False)
        pdf.set_font("noto", "B" if bold_val else "", 10); pdf.cell(0, 8, value, ln=True)
    row("Receipt No:", contrib.get("receipt_number", "N/A"))
    paid_at = contrib.get("paid_at", "")
    try: date_str = datetime.fromisoformat(paid_at).strftime("%d %B %Y")
    except Exception: date_str = paid_at[:10] if paid_at else "-"
    row("Date:", date_str)
    pdf.set_draw_color(200, 200, 200); pdf.ln(3); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(5)
    pdf.set_font("noto", "B", 10); pdf.set_text_color(22, 101, 52); pdf.cell(0, 7, "MEMBER DETAILS", ln=True)
    pdf.set_text_color(28, 25, 23)
    row("Name:", member["name"] if member else "Unknown")
    row("Member ID:", member["member_id"] if member else "-")
    row("Mobile:", (member.get("mobile", "-") if member else "-"))
    pdf.ln(3); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(5)
    pdf.set_font("noto", "B", 10); pdf.set_text_color(22, 101, 52); pdf.cell(0, 7, "CONTRIBUTION DETAILS", ln=True)
    pdf.set_text_color(28, 25, 23)
    month_num = contrib.get("month", 1)
    month_str = MONTHS_NAMES[month_num] if 1 <= month_num <= 12 else str(month_num)
    row("Period:", f"{month_str} {contrib.get('year', '')}")
    row("Payment Method:", str(contrib.get("payment_method", "-")).replace("_", " ").title())
    pdf.ln(5); pdf.set_fill_color(240, 253, 244); pdf.set_draw_color(22, 101, 52)
    pdf.rect(15, pdf.get_y(), 180, 18, "FD"); pdf.set_font("noto", "B", 14); pdf.set_text_color(22, 101, 52)
    pdf.set_y(pdf.get_y() + 3); pdf.cell(0, 8, f"AMOUNT PAID: Rs. {contrib.get('amount', 0):,.0f}/-", ln=True, align="C")
    pdf.ln(15); pdf.set_text_color(120, 113, 108); pdf.set_font("noto", "I", 8)
    pdf.set_draw_color(231, 229, 228); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(4)
    pdf.cell(0, 5, "This is a computer-generated receipt. No signature required.", ln=True, align="C")
    pdf.cell(0, 5, "Twenty20 Charity Group Wariyad - Serving the community", ln=True, align="C")
    return bytes(pdf.output())

@api_router.get("/contributions/{payment_id}/receipt")
async def download_receipt(payment_id: str, user: dict = Depends(get_current_user),
                           session: AsyncSession = Depends(get_session)):
    pay = await session.get(Payment, safe_id(payment_id))
    if not pay:
        raise HTTPException(404, "Payment not found")
    member = await session.get(Member, pay.member_id) if _is_uuid(pay.member_id) else None
    if user["role"] == "member" and not _member_owns(user, member):
        raise HTTPException(403, "Access denied")
    pdf_bytes = build_receipt_pdf(pay.model_dump(), member.model_dump() if member else None)
    rnum = pay.receipt_number or "receipt"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={rnum}.pdf"})


# ── EXPORT REPORTS ────────────────────────────────────────────────────────────
_MONTH_NAMES_FULL = ["","January","February","March","April","May","June",
                     "July","August","September","October","November","December"]
_MONTH_NAMES_SHORT = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def _safe_cell(val) -> str:
    """Prevent CSV/Excel formula injection by prefixing dangerous characters."""
    s = str(val) if val is not None else ""
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r', '|', '%'):
        return "'" + s
    return s

@api_router.get("/reports/export/excel")
async def export_excel_report(year: Optional[int] = None,
        user: dict = Depends(require_roles("super_admin", "president", "treasurer", "secretary", "auditor")),
        session: AsyncSession = Depends(get_session)):
    yr = year or datetime.now().year
    contributions = [c.model_dump() for c in (await session.execute(select(Payment).where(Payment.year == yr))).scalars().all()]
    benefits = [b.model_dump() for b in (await session.execute(select(Benefit))).scalars().all()]
    cashbook = [e.model_dump() for e in (await session.execute(select(Cashbook).order_by(Cashbook.created_at.asc()))).scalars().all()]
    members = [m.model_dump() for m in (await session.execute(select(Member))).scalars().all()]
    member_map = {m["id"]: m for m in members}

    contrib_rows = [{
        "Receipt No": _safe_cell(c.get("receipt_number", "")),
        "Month": _MONTH_NAMES_SHORT[c.get("month", 1)],
        "Year": c.get("year", yr),
        "Member Name": _safe_cell(member_map.get(c.get("member_id", ""), {}).get("name", "Unknown")),
        "Amount (Rs)": c.get("amount", 0),
        "Payment Method": _safe_cell(c.get("payment_method", "").replace("_", " ").title()),
        "Date Paid": c.get("paid_at", "")[:10] if c.get("paid_at") else "",
    } for c in contributions]
    benefit_rows = [{
        "Benefit Type": _safe_cell((b.get("benefit_type") or "").replace("_", " ").title()),
        "Member Name": _safe_cell(b.get("member_name", "")),
        "Amount (Rs)": b.get("amount", 0),
        "Status": _safe_cell((b.get("status") or "").replace("_", " ").title()),
        "Event Date": b.get("event_date", ""),
        "Applied Date": b.get("created_at", "")[:10] if b.get("created_at") else "",
    } for b in benefits]
    running_bal = 0
    cashbook_rows = []
    for e in cashbook:
        running_bal += e["amount"] if e["entry_type"] == "credit" else -e["amount"]
        cashbook_rows.append({
            "Voucher No": _safe_cell(e.get("voucher_number", "")),
            "Date": e.get("date", ""),
            "Description": _safe_cell(e.get("description", "")),
            "Category": _safe_cell((e.get("category") or "").replace("_", " ").title()),
            "Type": "Credit" if e["entry_type"] == "credit" else "Debit",
            "Credit (Rs)": e["amount"] if e["entry_type"] == "credit" else 0,
            "Debit (Rs)": e["amount"] if e["entry_type"] == "debit" else 0,
            "Balance (Rs)": round(running_bal, 2),
        })
    member_rows = [{
        "Member ID": m.get("member_id", ""),
        "Name": _safe_cell(m.get("name", "")),
        "Mobile": _safe_cell(m.get("mobile", "")),
        "Address": _safe_cell(m.get("address", "")),
        "Joining Date": m.get("joining_date", ""),
        "Status": (m.get("status") or "").title(),
    } for m in members]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        (pd.DataFrame(contrib_rows) if contrib_rows else pd.DataFrame(columns=["Receipt No","Month","Year","Member Name","Amount (Rs)","Payment Method","Date Paid"])).to_excel(writer, sheet_name=f"Contributions {yr}", index=False)
        (pd.DataFrame(benefit_rows) if benefit_rows else pd.DataFrame(columns=["Benefit Type","Member Name","Amount (Rs)","Status","Event Date","Applied Date"])).to_excel(writer, sheet_name="Benefits", index=False)
        (pd.DataFrame(cashbook_rows) if cashbook_rows else pd.DataFrame(columns=["Voucher No","Date","Description","Category","Type","Credit (Rs)","Debit (Rs)","Balance (Rs)"])).to_excel(writer, sheet_name="Cashbook", index=False)
        (pd.DataFrame(member_rows) if member_rows else pd.DataFrame(columns=["Member ID","Name","Mobile","Address","Joining Date","Status"])).to_excel(writer, sheet_name="Members", index=False)
    buf.seek(0)
    return StreamingResponse(buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Twenty20_Wariyad_Report_{yr}.xlsx"})

@api_router.get("/reports/export/pdf")
async def export_pdf_report(year: Optional[int] = None,
        user: dict = Depends(require_roles("super_admin", "president", "treasurer", "secretary", "auditor")),
        session: AsyncSession = Depends(get_session)):
    yr = year or datetime.now().year
    contributions = [c.model_dump() for c in (await session.execute(select(Payment).where(Payment.year == yr))).scalars().all()]
    benefits_paid = [b.model_dump() for b in (await session.execute(select(Benefit).where(Benefit.status == "paid"))).scalars().all()]
    medical_paid = [m.model_dump() for m in (await session.execute(select(MedicalAid).where(MedicalAid.status == "paid"))).scalars().all()]
    cashbook = [e.model_dump() for e in (await session.execute(select(Cashbook))).scalars().all()]
    members = [m.model_dump() for m in (await session.execute(select(Member))).scalars().all()]
    total_contrib = sum(c["amount"] for c in contributions)
    total_credits = sum(e["amount"] for e in cashbook if e["entry_type"] == "credit")
    total_debits = sum(e["amount"] for e in cashbook if e["entry_type"] == "debit")
    balance = total_credits - total_debits
    monthly = {}
    for c in contributions:
        monthly.setdefault(c["month"], {"count": 0, "amount": 0})
        monthly[c["month"]]["count"] += 1
        monthly[c["month"]]["amount"] += c["amount"]
    pdf = new_pdf(); pdf.set_margins(15, 15, 15); pdf.add_page()
    pdf.set_fill_color(22, 101, 52); pdf.rect(0, 0, 210, 42, "F")
    try: pdf.image(LOGO_WHITE, x=12, y=7, h=28)
    except Exception: pass
    pdf.set_text_color(255, 255, 255); pdf.set_y(10); pdf.set_font("noto", "B", 18)
    pdf.cell(0, 9, "TWENTY20 CHARITY GROUP", ln=True, align="C")
    pdf.set_font("noto", "B", 11); pdf.cell(0, 7, "WARIYAD", ln=True, align="C")
    pdf.set_font("noto", "", 9); pdf.cell(0, 6, f"Annual Financial Report - {yr}", ln=True, align="C")
    pdf.set_y(50); pdf.set_text_color(28, 25, 23)
    pdf.set_font("noto", "B", 12); pdf.set_text_color(22, 101, 52); pdf.cell(0, 8, f"ANNUAL SUMMARY - {yr}", ln=True)
    pdf.set_draw_color(200, 200, 200); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(4)
    pdf.set_text_color(28, 25, 23)
    active = sum(1 for m in members if m.get("status") == "active")
    m_marriage = [b for b in benefits_paid if b.get("benefit_type") == "marriage"]
    m_house = [b for b in benefits_paid if b.get("benefit_type") == "housewarming"]
    for label, value in [
        ("Total Members (All Time)", str(len(members))),
        ("Active Members", str(active)),
        (f"Contributions Collected ({yr})", f"Rs. {total_contrib:,.0f}"),
        ("Total Credits (Cashbook)", f"Rs. {total_credits:,.0f}"),
        ("Total Debits (Cashbook)", f"Rs. {total_debits:,.0f}"),
        ("Closing Fund Balance", f"Rs. {balance:,.0f}"),
        ("Marriage Benefits Paid", f"{len(m_marriage)} (Rs. {sum(b.get('amount',0) for b in m_marriage):,.0f})"),
        ("Housewarming Benefits Paid", f"{len(m_house)} (Rs. {sum(b.get('amount',0) for b in m_house):,.0f})"),
        ("Medical Aid Cases Paid", str(len(medical_paid))),
    ]:
        pdf.set_font("noto", "B", 10); pdf.cell(110, 7, label, ln=False)
        pdf.set_font("noto", "", 10); pdf.cell(0, 7, value, ln=True)
    pdf.ln(5); pdf.set_font("noto", "B", 11); pdf.set_text_color(22, 101, 52)
    pdf.cell(0, 8, "MONTHLY CONTRIBUTION BREAKDOWN", ln=True); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(3)
    pdf.set_fill_color(22, 101, 52); pdf.set_text_color(255, 255, 255); pdf.set_font("noto", "B", 9)
    pdf.cell(60, 7, "Month", border=1, fill=True, align="C")
    pdf.cell(50, 7, "Members Paid", border=1, fill=True, align="C")
    pdf.cell(70, 7, "Amount Collected (Rs)", border=1, fill=True, align="C"); pdf.ln()
    pdf.set_text_color(28, 25, 23); pdf.set_font("noto", "", 9); t_count = 0
    for m_idx in range(1, 13):
        md = monthly.get(m_idx, {"count": 0, "amount": 0}); fill = m_idx % 2 == 0
        pdf.set_fill_color(248, 248, 248) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(60, 6, _MONTH_NAMES_FULL[m_idx], border=1, fill=fill)
        pdf.cell(50, 6, str(md["count"]), border=1, fill=fill, align="C")
        pdf.cell(70, 6, f"{md['amount']:,.0f}", border=1, fill=fill, align="R"); pdf.ln()
        t_count += md["count"]
    pdf.set_fill_color(22, 101, 52); pdf.set_text_color(255, 255, 255); pdf.set_font("noto", "B", 9)
    pdf.cell(60, 7, "TOTAL", border=1, fill=True); pdf.cell(50, 7, str(t_count), border=1, fill=True, align="C")
    pdf.cell(70, 7, f"{total_contrib:,.0f}", border=1, fill=True, align="R"); pdf.ln()
    pdf.ln(10); pdf.set_text_color(120, 113, 108); pdf.set_font("noto", "I", 8)
    pdf.set_draw_color(231, 229, 228); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(4)
    pdf.cell(0, 5, f"Generated on {datetime.now().strftime('%d %B %Y')} - Twenty20 Charity Group Wariyad", ln=True, align="C")
    pdf.cell(0, 5, "This is a computer-generated report. For official audit purposes.", ln=True, align="C")
    return StreamingResponse(io.BytesIO(bytes(pdf.output())), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Twenty20_Wariyad_Report_{yr}.pdf"})


# ── NOTIFICATIONS ──────────────────────────────────────────────────────────────
@api_router.get("/notifications/defaulters")
async def get_defaulters(month: int, year: int,
        user: dict = Depends(require_roles("super_admin", "president", "secretary", "treasurer")),
        session: AsyncSession = Depends(get_session)):
    """Defaulters = members with an outstanding balance as of (year, month),
    ranked by amount owed. Includes outstanding amount + months pending."""
    settings = await get_settings(session)
    members = (await session.execute(select(Member).where(Member.status == "active"))).scalars().all()
    defaulters = []
    up_to_date = 0
    for m in members:
        rows = await member_ledger(session, m, settings, year, month)
        row = next((r for r in rows if r.year == year and r.month == month), None)
        if row is None:
            continue
        if row.balance < 0:
            defaulters.append({"member_id": m.id, "member_code": m.member_id, "name": m.name,
                               "mobile": m.mobile, "address": m.address,
                               "outstanding": -row.balance, "status": row.status})
        else:
            up_to_date += 1
    defaulters.sort(key=lambda d: -d["outstanding"])
    return {"month": month, "year": year, "total_active": len(members),
            "total_paid": up_to_date, "total_defaulters": len(defaulters),
            "defaulters": defaulters, "twilio_enabled": TWILIO_ENABLED}

@api_router.post("/notifications/send-reminders")
async def send_reminders(data: NotificationSendReq,
        user: dict = Depends(require_roles("super_admin", "president", "secretary", "treasurer")),
        session: AsyncSession = Depends(get_session)):
    settings = await get_settings(session)
    members = (await session.execute(select(Member).where(Member.status == "active"))).scalars().all()
    defaulters = []
    for m in members:
        rows = await member_ledger(session, m, settings, data.year, data.month)
        row = next((r for r in rows if r.year == data.year and r.month == data.month), None)
        if row is not None and row.balance < 0:
            defaulters.append(m)
    if not defaulters:
        return {"sent": 0, "message": "No defaulters found for this month.", "mode": "none", "results": []}
    month_name = _MONTH_NAMES_FULL[data.month] if 1 <= data.month <= 12 else str(data.month)
    msg = (data.message or
           f"Dear Member, your monthly contribution of Rs.100 for {month_name} {data.year} "
           f"is pending. Please pay at the earliest. - Twenty20 Charity Group Wariyad")
    results = []; sms_sent = wa_sent = 0
    if TWILIO_ENABLED:
        tc = TwilioClient(_TWILIO_SID, _TWILIO_TOKEN)
        for m in defaulters:
            phone = m.mobile or ""
            if not phone:
                results.append({"member": m.name, "status": "skipped", "reason": "no phone"}); continue
            ph = phone.strip().replace(" ", "").replace("-", "")
            if not ph.startswith("+"):
                ph = "+91" + ph
            sms_ok = wa_ok = False
            try:
                tc.messages.create(body=msg, from_=_TWILIO_FROM, to=ph); sms_ok = True; sms_sent += 1
            except Exception as e:
                logger.error(f"SMS failed for {m.name}: {e}")
            if _TWILIO_WA_FROM:
                try:
                    tc.messages.create(body=msg, from_=f"whatsapp:{_TWILIO_WA_FROM}", to=f"whatsapp:{ph}"); wa_ok = True; wa_sent += 1
                except Exception as e:
                    logger.error(f"WhatsApp failed for {m.name}: {e}")
            results.append({"member": m.name, "phone": ph,
                            "sms": "sent" if sms_ok else "failed",
                            "whatsapp": "sent" if wa_ok else "failed"})
    else:
        for m in defaulters:
            logger.info(f"[MOCK SMS] To: {m.mobile or 'N/A'} | {msg[:80]}")
            results.append({"member": m.name, "phone": m.mobile or "N/A", "sms": "mock", "whatsapp": "mock"})
    session.add(NotificationLog(type="monthly_reminder", month=data.month, year=data.year,
        sent_by=user["id"], mode="live" if TWILIO_ENABLED else "mock",
        sent_count=len(defaulters), sms_sent=sms_sent, wa_sent=wa_sent, results=results[:50]))
    await session.commit()
    return {"sent": len(defaulters), "sms_sent": sms_sent, "wa_sent": wa_sent,
            "mode": "live" if TWILIO_ENABLED else "mock",
            "message": (f"Reminders sent to {len(defaulters)} defaulters via SMS and WhatsApp."
                        if TWILIO_ENABLED else
                        f"[MOCK] Twilio not configured. Would notify {len(defaulters)} defaulters. "
                        f"Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_PHONE to backend/.env to enable real sending."),
            "results": results}


# ── AUDIT MODULE ───────────────────────────────────────────────────────────────
@api_router.get("/audit/report")
async def get_audit_report(year: Optional[int] = None,
        user: dict = Depends(require_roles("super_admin", "president", "secretary", "treasurer", "auditor")),
        session: AsyncSession = Depends(get_session)):
    yr = year or datetime.now().year
    contributions = [c.model_dump() for c in (await session.execute(select(Payment).where(Payment.year == yr))).scalars().all()]
    benefits_paid = [b.model_dump() for b in (await session.execute(select(Benefit).where(Benefit.status == "paid"))).scalars().all()]
    medical_paid = [m.model_dump() for m in (await session.execute(select(MedicalAid).where(MedicalAid.status == "paid"))).scalars().all()]
    death_delivered = (await session.execute(select(DeathAssistance).where(DeathAssistance.status == "delivered"))).scalars().all()
    cashbook = (await session.execute(select(Cashbook))).scalars().all()
    members = (await session.execute(select(Member))).scalars().all()
    total_contrib = sum(c["amount"] for c in contributions)
    total_credits = sum(e.amount for e in cashbook if e.entry_type == "credit")
    total_debits = sum(e.amount for e in cashbook if e.entry_type == "debit")
    monthly = {}
    for c in contributions:
        monthly.setdefault(c["month"], {"month": c["month"], "count": 0, "amount": 0})
        monthly[c["month"]]["count"] += 1
        monthly[c["month"]]["amount"] += c["amount"]
    m_marriage = [b for b in benefits_paid if b.get("benefit_type") == "marriage"]
    m_house = [b for b in benefits_paid if b.get("benefit_type") == "housewarming"]
    return {"year": yr, "total_members": len(members),
            "active_members": sum(1 for m in members if m.status == "active"),
            "total_contributions": total_contrib, "contribution_count": len(contributions),
            "monthly_breakdown": sorted(monthly.values(), key=lambda x: x["month"]),
            "marriage_count": len(m_marriage), "marriage_total": sum(b.get("amount", 0) for b in m_marriage),
            "housewarming_count": len(m_house), "housewarming_total": sum(b.get("amount", 0) for b in m_house),
            "medical_aid_count": len(medical_paid),
            "medical_aid_total": sum((d.get("recommended_amount") or d.get("estimated_expense", 0)) for d in medical_paid),
            "death_cases": len(death_delivered), "total_credits": total_credits, "total_debits": total_debits,
            "closing_balance": round(total_credits - total_debits, 2)}

@api_router.post("/audit/sign-off")
async def create_audit_sign_off(data: AuditSignOffCreate, user: dict = Depends(require_roles("auditor")),
                                session: AsyncSession = Depends(get_session)):
    dup = await session.execute(select(AuditSignOff).where(AuditSignOff.year == data.year, AuditSignOff.auditor_id == user["id"]))
    if dup.scalar_one_or_none():
        raise HTTPException(400, f"You have already signed off on year {data.year}. Only one sign-off per auditor per year is allowed.")
    a = AuditSignOff(year=data.year, remarks=data.remarks, auditor_id=user["id"],
                     auditor_name=user["name"], auditor_email=user["email"])
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a.model_dump()

@api_router.get("/audit/sign-offs")
async def list_audit_sign_offs(user: dict = Depends(require_roles("super_admin", "president", "secretary", "treasurer", "auditor")),
                               session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(AuditSignOff).order_by(AuditSignOff.signed_at.desc()).limit(200))
    return [a.model_dump() for a in res.scalars().all()]


# ── STARTUP / SHUTDOWN ────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await init_db()  # create tables (indexes/uniques come from the models)
    admin_email = os.environ["ADMIN_EMAIL"]
    admin_password = os.environ["ADMIN_PASSWORD"]  # no default — must be set explicitly
    async with async_session_maker() as session:
        res = await session.execute(select(User).where(User.email == admin_email))
        existing = res.scalar_one_or_none()
        if not existing:
            session.add(User(name="Super Admin", email=admin_email,
                             password_hash=hash_password(admin_password),
                             role="super_admin", is_active=True))
            await session.commit()
            logger.info(f"Admin seeded: {admin_email}")
        elif not verify_password(admin_password, existing.password_hash):
            existing.password_hash = hash_password(admin_password)
            await session.commit()

app.include_router(api_router)

@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()
