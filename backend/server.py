from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, UploadFile, File
from fastapi.responses import Response, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, BeforeValidator, EmailStr, field_validator
from typing import Annotated, Optional, List
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fpdf import FPDF
from collections import defaultdict
import os, jwt, bcrypt, logging, io, pandas as pd, time
import qrcode

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

# ── Database ─────────────────────────────────────────────────────────────────
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

# ── Security constants ────────────────────────────────────────────────────────
# Cookies: secure=True in prod; set COOKIE_SECURE=false only for local http dev
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() != "false"

# Privileged roles that only super_admin can assign
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

# ── PyObjectId ────────────────────────────────────────────────────────────────
def validate_object_id(v):
    if isinstance(v, ObjectId): return str(v)
    if isinstance(v, str) and ObjectId.is_valid(v): return v
    raise ValueError(f"Invalid ObjectId: {v}")

PyObjectId = Annotated[str, BeforeValidator(validate_object_id)]

def safe_oid(val: str) -> ObjectId:
    """Convert a path/query param to ObjectId, raising 400 on bad input."""
    if not ObjectId.is_valid(val):
        raise HTTPException(400, "Invalid ID format")

def _member_owns(user: dict, member: dict) -> bool:
    """True if `user` (role=member) is the member record `member`.
    Matches on either the Mongo _id or the TW- member code, so the check
    is robust to how the user account was linked."""
    if not member:
        return False
    uid = str(user.get("member_id") or "")
    return uid in (str(member.get("_id", "")), str(member.get("member_id", "")))

    return ObjectId(val)

# ── Brute-force rate limiter (in-memory, 5 attempts / 15 min per email+IP) ───
_login_attempts: dict = defaultdict(list)
_RATE_MAX    = 5
_RATE_WINDOW = 900   # seconds

def _check_rate_limit(email: str, ip: str):
    # Use email only as key (IP alone is unreliable behind K8s ingress)
    key  = email.lower()
    now  = time.time()
    hits = [t for t in _login_attempts[key] if now - t < _RATE_WINDOW]
    _login_attempts[key] = hits
    if len(hits) >= _RATE_MAX:
        raise HTTPException(429, "Too many login attempts. Try again in 15 minutes.")
    _login_attempts[key].append(now)

def _reset_rate_limit(email: str, ip: str):
    key = email.lower()
    _login_attempts.pop(key, None)

# ── Auth helpers ──────────────────────────────────────────────────────────────
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "): token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(401, "Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(401, "User not found")
        if not user.get("is_active", True):
            raise HTTPException(403, "Account is disabled")
        user["id"] = str(user.pop("_id"))
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

def require_roles(*roles):
    async def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return checker

# ── Serializers ───────────────────────────────────────────────────────────────
def s(doc: dict) -> dict:
    if doc is None: return None
    doc["id"] = str(doc.pop("_id"))
    return doc

def ss(docs) -> list:
    return [s(d) for d in docs]

# ── ID generators ─────────────────────────────────────────────────────────────
async def next_member_id():
    # Use max existing ID to avoid collisions after deletions
    last = await db.members.find_one({}, sort=[("member_id", -1)])
    if last and last.get("member_id"):
        try:
            num = int(last["member_id"].split("-")[-1])
            return f"TW-{(num+1):03d}"
        except (ValueError, IndexError):
            pass
    return "TW-001"

async def next_receipt():
    yr = datetime.now().year
    count = await db.contributions.count_documents({"year": yr})
    return f"RCP-{yr}-{(count+1):04d}"

async def next_voucher():
    count = await db.cashbook.count_documents({})
    return f"VCH-{datetime.now().year}-{(count+1):04d}"

# ── Pydantic Models ───────────────────────────────────────────────────────────
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

class MemberUpdate(BaseModel):
    name: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None
    aadhaar: Optional[str] = None

class ContribCreate(BaseModel):
    member_id: str
    month: int
    year: int
    amount: float
    payment_method: str

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

# Support comma-separated origins (e.g. staging + prod)
_origins_raw = os.environ.get("FRONTEND_URL", "http://localhost:3000")
FRONTEND_ORIGINS = [o.strip() for o in _origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Cookie"],
)

# ── AUTH ──────────────────────────────────────────────────────────────────────
@api_router.post("/auth/register")
async def register(data: UserCreate, response: Response):
    email = data.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    uid = (await db.users.insert_one({
        "name": data.name, "email": email,
        "password_hash": hash_password(data.password),
        "role": "member",          # registration always creates a plain member
        "member_id": data.member_id,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    })).inserted_id
    user_id = str(uid)
    at = create_access_token(user_id, email)
    rt = create_refresh_token(user_id)
    response.set_cookie("access_token", at, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=28800)
    response.set_cookie("refresh_token", rt, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=604800)
    return {"id": user_id, "name": data.name, "email": email, "role": "member"}

@api_router.post("/auth/login")
async def login(data: LoginReq, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    email = data.email.lower().strip()
    _check_rate_limit(email, client_ip)
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    if not user.get("is_active", True):
        raise HTTPException(403, "Account is disabled")
    _reset_rate_limit(email, client_ip)
    user_id = str(user["_id"])
    at = create_access_token(user_id, email)
    rt = create_refresh_token(user_id)
    response.set_cookie("access_token", at, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=28800)
    response.set_cookie("refresh_token", rt, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=604800)
    return {"id": user_id, "name": user["name"], "email": user["email"],
            "role": user["role"], "member_id": user.get("member_id")}

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
async def list_users(user: dict = Depends(require_roles("super_admin", "president", "secretary"))):
    docs = await db.users.find({}, {"password_hash": 0}).to_list(500)
    return ss(docs)

@api_router.post("/users")
async def create_user(data: UserCreate, user: dict = Depends(require_roles("super_admin", "secretary"))):
    if user["role"] != "super_admin" and data.role in PRIVILEGED_ROLES:
        raise HTTPException(403, "Only super_admin can assign privileged roles")
    email = data.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    uid = (await db.users.insert_one({
        "name": data.name, "email": email,
        "password_hash": hash_password(data.password),
        "role": data.role, "member_id": data.member_id,
        "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
    })).inserted_id
    return {"id": str(uid), "name": data.name, "email": email, "role": data.role}

@api_router.put("/users/{uid}")
async def update_user(uid: str, data: UserUpdate, user: dict = Depends(require_roles("super_admin"))):
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    await db.users.update_one({"_id": safe_oid(uid)}, {"$set": upd})
    doc = await db.users.find_one({"_id": safe_oid(uid)}, {"password_hash": 0})
    return s(doc)

@api_router.delete("/users/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_roles("super_admin"))):
    if user["id"] == uid:
        raise HTTPException(400, "Cannot delete your own account")
    await db.users.delete_one({"_id": safe_oid(uid)})
    return {"message": "User deleted"}

def _mask_aadhaar(doc: dict, role: str) -> dict:
    """Mask Aadhaar for all non-super_admin roles."""
    if doc and doc.get("aadhaar") and role != "super_admin":
        raw = doc["aadhaar"].replace("-", "").replace(" ", "")
        doc["aadhaar"] = "XXXX-XXXX-" + (raw[-4:] if len(raw) >= 4 else "****")
    return doc

# ── MEMBERS ───────────────────────────────────────────────────────────────────
@api_router.get("/members")
async def list_members(user: dict = Depends(get_current_user)):
    docs = await db.members.find().sort("created_at", -1).to_list(500)
    return [_mask_aadhaar(s(d), user["role"]) for d in docs]

@api_router.post("/members")
async def create_member(data: MemberCreate, user: dict = Depends(require_roles("super_admin", "secretary", "treasurer"))):
    mid = await next_member_id()
    doc = {**data.model_dump(), "member_id": mid,
           "created_at": datetime.now(timezone.utc).isoformat()}
    result = await db.members.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc

# ── BULK IMPORT (must be before /{mid} to avoid routing conflict) ─────────────
@api_router.get("/members/import-template")
async def import_template():
    csv_content = (
        "name,mobile,address,joining_date,status,aadhaar\n"
        "Mohammed Ashraf,9876543210,\"House No 12 Main Road Wariyad\",2024-01-15,active,\n"
        "Suhail Ahmed,9876543211,\"Near Mosque Wariyad\",2024-02-20,active,123456789012\n"
        "Fathima Beevi,9876543212,\"Colony Road Wariyad\",2024-03-10,active,\n"
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=members_template.csv"}
    )

def build_member_qr_card(member: dict) -> bytes:
    """Generate a PDF ID card with embedded QR code for a member."""
    qr_data = (
        f"Twenty20 Charity Group Wariyad\n"
        f"Name: {member.get('name','')}\n"
        f"Member ID: {member.get('member_id','')}\n"
        f"Mobile: {member.get('mobile','')}"
    )
    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#166534", back_color="white")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    pdf = new_pdf(orientation="L", format=(54, 86))  # Landscape credit-card size (mm)
    pdf.set_margins(0, 0, 0)
    pdf.add_page()

    # Green header band
    pdf.set_fill_color(22, 101, 52)
    pdf.rect(0, 0, 86, 14, "F")
    pdf.image(LOGO_WHITE, x=2, y=2, h=10)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("noto", "B", 7)
    pdf.set_y(2)
    pdf.cell(0, 5, "TWENTY20 CHARITY GROUP  WARIYAD", align="C", ln=True)
    pdf.set_font("noto", "", 6)
    pdf.cell(0, 4, "Verified Member Card", align="C", ln=True)

    # Left side — member details
    pdf.set_text_color(28, 25, 23)
    pdf.set_y(17)
    pdf.set_x(3)
    pdf.set_font("noto", "B", 11)
    pdf.cell(48, 7, member.get("name", ""), ln=True)
    pdf.set_x(3)
    pdf.set_font("noto", "B", 8)
    pdf.set_text_color(22, 101, 52)
    pdf.cell(48, 5, member.get("member_id", ""), ln=True)
    pdf.set_x(3)
    pdf.set_text_color(80, 80, 80)
    pdf.set_font("noto", "", 7)
    pdf.cell(48, 4, f"Mobile: {member.get('mobile', '-')}", ln=True)
    pdf.set_x(3)
    pdf.cell(48, 4, f"Joined: {member.get('joining_date', '-')}", ln=True)

    # Status badge
    pdf.set_x(3)
    pdf.set_y(42)
    pdf.set_fill_color(220, 252, 231)
    pdf.set_draw_color(22, 101, 52)
    pdf.set_text_color(22, 101, 52)
    pdf.set_font("noto", "B", 6)
    pdf.cell(20, 5, "  ACTIVE", border=1, fill=True, align="C")

    # QR code on right
    pdf.image(qr_buf, x=54, y=14, w=29, h=29)

    # Footer
    pdf.set_fill_color(22, 101, 52)
    pdf.rect(0, 49, 86, 5, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("noto", "", 5)
    pdf.set_y(50)
    pdf.cell(0, 3, "This card is the property of Twenty20 Charity Group Wariyad", align="C")

    return bytes(pdf.output())


@api_router.get("/members/{mid}/qr-card")
async def download_member_qr_card(mid: str, user: dict = Depends(get_current_user)):
    member = await db.members.find_one({"_id": safe_oid(mid)})
    if not member:
        raise HTTPException(404, "Member not found")
    # Members can only download their own QR card (match on _id or TW- code)
    if user["role"] == "member" and not _member_owns(user, member):
        raise HTTPException(403, "Access denied")
    pdf_bytes = build_member_qr_card(member)
    name_slug = member.get("name", "member").replace(" ", "_")
    name_slug = name_slug.encode("ascii", "ignore").decode() or member.get("member_id", "member")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=MemberCard_{name_slug}.pdf"}
    )

@api_router.put("/members/{mid}")
async def update_member(mid: str, data: MemberUpdate, user: dict = Depends(require_roles("super_admin", "secretary", "treasurer"))):
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    await db.members.update_one({"_id": safe_oid(mid)}, {"$set": upd})
    return _mask_aadhaar(s(await db.members.find_one({"_id": safe_oid(mid)})), user["role"])

@api_router.delete("/members/{mid}")
async def delete_member(mid: str, user: dict = Depends(require_roles("super_admin"))):
    await db.members.delete_one({"_id": safe_oid(mid)})
    return {"message": "Member deleted"}

# ── CONTRIBUTIONS ─────────────────────────────────────────────────────────────
@api_router.get("/contributions")
async def list_contributions(
    member_id: Optional[str] = None, year: Optional[int] = None,
    month: Optional[int] = None, user: dict = Depends(get_current_user)
):
    q = {}
    if member_id: q["member_id"] = member_id
    elif user["role"] == "member" and user.get("member_id"):
        q["member_id"] = user["member_id"]
    if year: q["year"] = year
    if month: q["month"] = month
    docs = await db.contributions.find(q).sort("paid_at", -1).to_list(2000)
    return ss(docs)

@api_router.post("/contributions")
async def record_contribution(data: ContribCreate, user: dict = Depends(require_roles("super_admin", "treasurer"))):
    if await db.contributions.find_one({"member_id": data.member_id, "month": data.month, "year": data.year}):
        raise HTTPException(400, "Contribution already recorded for this month")
    receipt = await next_receipt()
    doc = {**data.model_dump(), "receipt_number": receipt,
           "recorded_by": user["id"], "paid_at": datetime.now(timezone.utc).isoformat()}
    result = await db.contributions.insert_one(doc)
    cid = str(result.inserted_id)
    # Auto cashbook credit
    member = await db.members.find_one({"_id": safe_oid(data.member_id)}) if ObjectId.is_valid(data.member_id) else None
    await db.cashbook.insert_one({
        "entry_type": "credit", "category": "contribution",
        "description": f"Monthly contribution - {data.year}/{data.month:02d} ({member['name'] if member else 'Unknown'})",
        "amount": data.amount, "date": datetime.now(timezone.utc).date().isoformat(),
        "reference_id": cid, "voucher_number": await next_voucher(),
        "recorded_by": user["id"], "created_at": datetime.now(timezone.utc).isoformat()
    })
    doc["id"] = cid
    doc.pop("_id", None)
    return doc

@api_router.delete("/contributions/{cid}")
async def delete_contribution(cid: str, user: dict = Depends(require_roles("super_admin", "treasurer"))):
    await db.contributions.delete_one({"_id": safe_oid(cid)})
    return {"message": "Deleted"}

@api_router.get("/contributions/status/{year}/{month}")
async def contribution_status(year: int, month: int, user: dict = Depends(get_current_user)):
    members = await db.members.find({"status": "active"}).to_list(500)
    contribs = await db.contributions.find({"year": year, "month": month}).to_list(500)
    paid_map = {c["member_id"]: c for c in contribs}
    result = []
    for m in members:
        mid = str(m["_id"])
        c = paid_map.get(mid)
        result.append({
            "member_id": mid, "member_name": m["name"],
            "member_code": m["member_id"],
            "status": "paid" if c else "pending",
            "amount": c["amount"] if c else None,
            "receipt_number": c["receipt_number"] if c else None,
            "payment_method": c["payment_method"] if c else None,
            "contribution_id": str(c["_id"]) if c else None
        })
    return result

# ── BENEFITS ──────────────────────────────────────────────────────────────────
BENEFIT_AMOUNTS = {"marriage": 5000, "housewarming": 3000}

@api_router.get("/benefits")
async def list_benefits(user: dict = Depends(get_current_user)):
    q = {}
    if user["role"] == "member" and user.get("member_id"):
        q["member_id"] = user["member_id"]
    docs = await db.benefits.find(q).sort("created_at", -1).to_list(500)
    return ss(docs)

@api_router.post("/benefits")
async def apply_benefit(data: BenefitCreate, user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(data.member_id):
        raise HTTPException(400, "Invalid member ID")
    member = await db.members.find_one({"_id": ObjectId(data.member_id)})
    if not member: raise HTTPException(404, "Member not found")
    if member["status"] != "active": raise HTTPException(400, "Member is not active")
    existing = await db.benefits.find_one({"member_id": data.member_id,
        "benefit_type": data.benefit_type, "status": {"$nin": ["rejected"]}})
    if existing: raise HTTPException(400, f"{data.benefit_type.capitalize()} benefit already applied")
    doc = {**data.model_dump(), "member_name": member["name"],
           "amount": BENEFIT_AMOUNTS.get(data.benefit_type, 0),
           "status": "pending", "applied_by": user["id"],
           "created_at": datetime.now(timezone.utc).isoformat()}
    result = await db.benefits.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc

@api_router.put("/benefits/{bid}/status")
async def update_benefit_status(bid: str, data: StatusUpdate, user: dict = Depends(get_current_user)):
    upd: dict = {"status": data.status}
    if data.notes: upd["notes"] = data.notes
    now = datetime.now(timezone.utc).isoformat()
    st = data.status
    if st == "secretary_verified":
        if user["role"] not in ["super_admin", "secretary"]: raise HTTPException(403, "Secretary only")
        upd.update({"secretary_verified_by": user["id"], "secretary_verified_at": now})
    elif st == "committee_approved":
        if user["role"] not in ["super_admin", "president", "committee_member"]: raise HTTPException(403, "Committee only")
        upd.update({"committee_approved_by": user["id"], "committee_approved_at": now})
    elif st == "paid":
        if user["role"] not in ["super_admin", "treasurer"]: raise HTTPException(403, "Treasurer only")
        upd.update({"paid_by": user["id"], "paid_at": now})
        benefit = await db.benefits.find_one({"_id": safe_oid(bid)})
        if benefit:
            await db.cashbook.insert_one({
                "entry_type": "debit",
                "category": f"{benefit['benefit_type']}_benefit",
                "description": f"{benefit['benefit_type'].capitalize()} benefit - {benefit['member_name']}",
                "amount": benefit["amount"], "date": datetime.now(timezone.utc).date().isoformat(),
                "reference_id": bid, "voucher_number": await next_voucher(),
                "recorded_by": user["id"], "created_at": now
            })
    elif st == "rejected":
        upd.update({"rejected_by": user["id"], "rejected_at": now})
    await db.benefits.update_one({"_id": safe_oid(bid)}, {"$set": upd})
    return s(await db.benefits.find_one({"_id": safe_oid(bid)}))

# ── MEDICAL AID ───────────────────────────────────────────────────────────────
@api_router.get("/medical-aid")
async def list_medical_aid(user: dict = Depends(get_current_user)):
    docs = await db.medical_aid.find().sort("created_at", -1).to_list(500)
    return ss(docs)

@api_router.post("/medical-aid")
async def apply_medical_aid(data: MedicalAidCreate, user: dict = Depends(get_current_user)):
    doc = {**data.model_dump(), "status": "pending",
           "applied_by": user["id"], "created_at": datetime.now(timezone.utc).isoformat()}
    result = await db.medical_aid.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc

@api_router.put("/medical-aid/{aid_id}")
async def update_medical_aid(aid_id: str, data: MedicalAidUpdate, user: dict = Depends(get_current_user)):
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    now = datetime.now(timezone.utc).isoformat()
    if data.status == "approved":
        upd.update({"approved_by": user["id"], "approved_at": now})
    elif data.status == "paid":
        aid = await db.medical_aid.find_one({"_id": safe_oid(aid_id)})
        if aid:
            await db.cashbook.insert_one({
                "entry_type": "debit", "category": "medical_aid",
                "description": f"Medical aid - {aid['applicant_name']}",
                "amount": aid.get("recommended_amount") or aid.get("estimated_expense", 0),
                "date": datetime.now(timezone.utc).date().isoformat(),
                "reference_id": aid_id, "voucher_number": await next_voucher(),
                "recorded_by": user["id"], "created_at": now
            })
        upd.update({"paid_by": user["id"], "paid_at": now})
    await db.medical_aid.update_one({"_id": safe_oid(aid_id)}, {"$set": upd})
    return s(await db.medical_aid.find_one({"_id": safe_oid(aid_id)}))

@api_router.delete("/medical-aid/{aid_id}")
async def delete_medical_aid(aid_id: str, user: dict = Depends(require_roles("super_admin"))):
    await db.medical_aid.delete_one({"_id": safe_oid(aid_id)})
    return {"message": "Deleted"}

# ── DEATH ASSISTANCE ──────────────────────────────────────────────────────────
@api_router.get("/death-assistance")
async def list_death_assistance(user: dict = Depends(get_current_user)):
    docs = await db.death_assistance.find().sort("created_at", -1).to_list(500)
    return ss(docs)

@api_router.post("/death-assistance")
async def create_death_assistance(data: DeathCreate, user: dict = Depends(get_current_user)):
    doc = {**data.model_dump(), "status": "pending",
           "created_by": user["id"], "created_at": datetime.now(timezone.utc).isoformat()}
    result = await db.death_assistance.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc

@api_router.put("/death-assistance/{case_id}")
async def update_death_assistance(case_id: str, data: DeathUpdate, user: dict = Depends(get_current_user)):
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    if data.status == "approved":
        upd["approved_by"] = user["id"]
        upd["approved_at"] = datetime.now(timezone.utc).isoformat()
    await db.death_assistance.update_one({"_id": safe_oid(case_id)}, {"$set": upd})
    return s(await db.death_assistance.find_one({"_id": safe_oid(case_id)}))

@api_router.delete("/death-assistance/{case_id}")
async def delete_death_assistance(case_id: str, user: dict = Depends(require_roles("super_admin"))):
    await db.death_assistance.delete_one({"_id": safe_oid(case_id)})
    return {"message": "Deleted"}

# ── CASHBOOK ──────────────────────────────────────────────────────────────────
@api_router.get("/cashbook")
async def list_cashbook(user: dict = Depends(get_current_user)):
    entries = await db.cashbook.find().sort("created_at", 1).to_list(5000)
    serialized = ss(entries)
    balance = 0.0
    for e in serialized:
        balance += e["amount"] if e["entry_type"] == "credit" else -e["amount"]
        e["running_balance"] = round(balance, 2)
    serialized.reverse()
    return serialized

@api_router.post("/cashbook")
async def create_cashbook_entry(data: CashbookCreate, user: dict = Depends(require_roles("super_admin", "treasurer"))):
    voucher = await next_voucher()
    doc = {**data.model_dump(), "voucher_number": voucher,
           "recorded_by": user["id"], "created_at": datetime.now(timezone.utc).isoformat()}
    result = await db.cashbook.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc

@api_router.delete("/cashbook/{eid}")
async def delete_cashbook_entry(eid: str, user: dict = Depends(require_roles("super_admin", "treasurer"))):
    await db.cashbook.delete_one({"_id": safe_oid(eid)})
    return {"message": "Deleted"}

# ── COMMITTEE ─────────────────────────────────────────────────────────────────
@api_router.get("/committee")
async def list_committees(user: dict = Depends(get_current_user)):
    docs = await db.committee.find().sort("year", -1).to_list(50)
    return ss(docs)

@api_router.post("/committee")
async def create_committee(data: CommitteeCreate, user: dict = Depends(require_roles("super_admin", "president", "secretary"))):
    doc = {**data.model_dump(), "is_active": True,
           "created_by": user["id"], "created_at": datetime.now(timezone.utc).isoformat()}
    result = await db.committee.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc

@api_router.get("/committee/handovers")
async def list_handovers(user: dict = Depends(get_current_user)):
    docs = await db.committee_handovers.find().sort("handover_date", -1).to_list(100)
    return ss(docs)


@api_router.post("/committee/handovers")
async def create_handover(
    data: CommitteeHandoverCreate,
    user: dict = Depends(require_roles("super_admin", "president", "secretary"))
):
    doc = {
        **data.model_dump(),
        "recorded_by": user["id"],
        "recorded_by_name": user["name"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await db.committee_handovers.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@api_router.put("/committee/{cid}")
async def update_committee(cid: str, data: dict, user: dict = Depends(require_roles("super_admin", "president"))):
    await db.committee.update_one({"_id": safe_oid(cid)}, {"$set": data})
    return s(await db.committee.find_one({"_id": safe_oid(cid)}))

@api_router.delete("/committee/{cid}")
async def delete_committee(cid: str, user: dict = Depends(require_roles("super_admin"))):
    await db.committee.delete_one({"_id": safe_oid(cid)})
    return {"message": "Deleted"}

# ── MEETINGS ──────────────────────────────────────────────────────────────────
@api_router.get("/meetings")
async def list_meetings(user: dict = Depends(get_current_user)):
    docs = await db.meetings.find().sort("scheduled_date", -1).to_list(200)
    return ss(docs)

@api_router.post("/meetings")
async def create_meeting(data: MeetingCreate, user: dict = Depends(require_roles("super_admin", "president", "secretary"))):
    doc = {**data.model_dump(), "status": "scheduled",
           "created_by": user["id"], "created_at": datetime.now(timezone.utc).isoformat()}
    result = await db.meetings.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc

@api_router.put("/meetings/{mid}")
async def update_meeting(mid: str, data: MeetingUpdate, user: dict = Depends(get_current_user)):
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    await db.meetings.update_one({"_id": safe_oid(mid)}, {"$set": upd})
    return s(await db.meetings.find_one({"_id": safe_oid(mid)}))

@api_router.delete("/meetings/{mid}")
async def delete_meeting(mid: str, user: dict = Depends(require_roles("super_admin", "president", "secretary"))):
    await db.meetings.delete_one({"_id": safe_oid(mid)})
    return {"message": "Deleted"}


def build_minutes_pdf(meeting: dict) -> bytes:
    """Generate a PDF of meeting minutes and resolutions."""
    TYPE_LABELS_PDF = {
        "executive": "Executive Committee Meeting",
        "annual_general": "Annual General Body Meeting",
        "emergency": "Emergency Meeting",
    }
    pdf = new_pdf()
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    # Header
    pdf.set_fill_color(22, 101, 52)
    pdf.rect(0, 0, 210, 42, "F")
    pdf.image(LOGO_WHITE, x=12, y=7, h=28)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(10)
    pdf.set_font("noto", "B", 16)
    pdf.cell(0, 9, "TWENTY20 CHARITY GROUP", ln=True, align="C")
    pdf.set_font("noto", "B", 10)
    pdf.cell(0, 6, "WARIYAD", ln=True, align="C")
    pdf.set_font("noto", "", 8)
    pdf.cell(0, 5, "Meeting Minutes", ln=True, align="C")

    pdf.set_y(50)
    pdf.set_text_color(28, 25, 23)

    # Meeting details
    meeting_type = TYPE_LABELS_PDF.get(meeting.get("meeting_type", ""), meeting.get("meeting_type", ""))
    pdf.set_font("noto", "B", 13)
    pdf.set_text_color(22, 101, 52)
    title = meeting.get("title", "")
    pdf.multi_cell(0, 8, title, align="C")
    pdf.ln(2)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)

    # Meta row
    pdf.set_text_color(28, 25, 23)
    for label, val in [
        ("Meeting Type", meeting_type),
        ("Date", meeting.get("scheduled_date", "")),
        ("Status", meeting.get("status", "").title()),
    ]:
        pdf.set_font("noto", "B", 10)
        pdf.cell(50, 6, label + ":", ln=False)
        pdf.set_font("noto", "", 10)
        pdf.cell(0, 6, val, ln=True)

    # Attendees
    attendees = meeting.get("attendees", [])
    if attendees:
        pdf.ln(3)
        pdf.set_font("noto", "B", 10)
        pdf.cell(0, 6, f"Attendees ({len(attendees)}):", ln=True)
        pdf.set_font("noto", "", 10)
        pdf.multi_cell(0, 6, ", ".join(attendees))

    # Agenda
    pdf.ln(3)
    pdf.set_font("noto", "B", 11)
    pdf.set_text_color(22, 101, 52)
    pdf.cell(0, 7, "AGENDA", ln=True)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    pdf.set_text_color(28, 25, 23)
    pdf.set_font("noto", "", 10)
    pdf.multi_cell(0, 6, meeting.get("agenda", ""))

    # Minutes
    if meeting.get("minutes"):
        pdf.ln(4)
        pdf.set_font("noto", "B", 11)
        pdf.set_text_color(22, 101, 52)
        pdf.cell(0, 7, "MINUTES OF MEETING", ln=True)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(3)
        pdf.set_text_color(28, 25, 23)
        pdf.set_font("noto", "", 10)
        pdf.multi_cell(0, 6, meeting.get("minutes", ""))

    # Structured Resolutions
    resolutions_list = meeting.get("resolutions_list", [])
    if resolutions_list:
        pdf.ln(4)
        pdf.set_font("noto", "B", 11)
        pdf.set_text_color(22, 101, 52)
        pdf.cell(0, 7, "RESOLUTIONS", ln=True)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(3)
        for i, res in enumerate(resolutions_list, 1):
            status = res.get("status", "passed").upper()
            pdf.set_font("noto", "B", 10)
            pdf.set_text_color(28, 25, 23)
            pdf.cell(8, 6, f"{i}.", ln=False)
            pdf.set_font("noto", "", 10)
            # Color-code status
            if status == "PASSED":
                pdf.set_text_color(22, 101, 52)
            elif status == "FAILED":
                pdf.set_text_color(185, 28, 28)
            else:
                pdf.set_text_color(120, 88, 0)
            pdf.cell(25, 6, f"[{status}]", ln=False)
            pdf.set_text_color(28, 25, 23)
            pdf.set_font("noto", "", 10)
            pdf.multi_cell(0, 6, res.get("text", ""))
    elif meeting.get("resolutions"):
        # Fallback to legacy text resolutions
        pdf.ln(4)
        pdf.set_font("noto", "B", 11)
        pdf.set_text_color(22, 101, 52)
        pdf.cell(0, 7, "RESOLUTIONS", ln=True)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(3)
        pdf.set_text_color(28, 25, 23)
        pdf.set_font("noto", "", 10)
        pdf.multi_cell(0, 6, meeting.get("resolutions", ""))

    # Footer
    pdf.ln(10)
    pdf.set_text_color(120, 113, 108)
    pdf.set_font("noto", "I", 8)
    pdf.set_draw_color(231, 229, 228)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)
    pdf.cell(0, 5, f"Minutes recorded on {datetime.now().strftime('%d %B %Y')} - Twenty20 Charity Group Wariyad", ln=True, align="C")
    return bytes(pdf.output())


@api_router.get("/meetings/{mid}/minutes-pdf")
async def download_minutes_pdf(mid: str, user: dict = Depends(get_current_user)):
    meeting = await db.meetings.find_one({"_id": safe_oid(mid)})
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    pdf_bytes = build_minutes_pdf(meeting)
    title_slug = meeting.get("title", "minutes").replace(" ", "_")[:30]
    title_slug = title_slug.encode("ascii", "ignore").decode() or "minutes"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Minutes_{title_slug}.pdf"}
    )

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@api_router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    now = datetime.now()
    cm, cy = now.month, now.year
    total_members = await db.members.count_documents({"status": "active"})
    total_all_members = await db.members.count_documents({})
    pending_benefits = await db.benefits.count_documents({"status": {"$in": ["pending", "secretary_verified", "committee_approved"]}})
    pending_medical = await db.medical_aid.count_documents({"status": {"$in": ["pending", "under_review"]}})
    cashbook = await db.cashbook.find().to_list(10000)
    balance = sum(e["amount"] * (1 if e["entry_type"] == "credit" else -1) for e in cashbook)
    this_month_contribs = await db.contributions.find({"year": cy, "month": cm}).to_list(500)
    monthly_collection = sum(c["amount"] for c in this_month_contribs)
    paid_benefits = await db.benefits.find({"status": "paid"}).to_list(500)
    total_benefits_paid = sum(b["amount"] for b in paid_benefits)
    paid_medical = await db.medical_aid.find({"status": "paid"}).to_list(500)
    total_medical_paid = sum(m.get("recommended_amount") or m.get("estimated_expense", 0) for m in paid_medical)
    upcoming_meetings = await db.meetings.count_documents({"status": "scheduled"})
    pending_death = await db.death_assistance.count_documents({"status": "pending"})
    return {
        "total_members": total_members, "total_all_members": total_all_members,
        "pending_benefits": pending_benefits, "pending_medical": pending_medical,
        "fund_balance": round(balance, 2), "monthly_collection": monthly_collection,
        "total_benefits_paid": total_benefits_paid, "total_medical_paid": total_medical_paid,
        "upcoming_meetings": upcoming_meetings, "pending_death": pending_death,
        "current_month": cm, "current_year": cy
    }

@api_router.get("/dashboard/recent-activity")
async def recent_activity(user: dict = Depends(get_current_user)):
    contribs = await db.contributions.find().sort("paid_at", -1).limit(5).to_list(5)
    benefits = await db.benefits.find().sort("created_at", -1).limit(5).to_list(5)
    return {"recent_contributions": ss(contribs), "recent_benefits": ss(benefits)}

@api_router.get("/dashboard/monthly-collections")
async def monthly_collections(year: Optional[int] = None, user: dict = Depends(get_current_user)):
    yr = year or datetime.now().year
    data = []
    for m in range(1, 13):
        docs = await db.contributions.find({"year": yr, "month": m}).to_list(500)
        data.append({"month": m, "count": len(docs), "total": sum(d["amount"] for d in docs)})
    return data

# ── REPORTS ───────────────────────────────────────────────────────────────────
@api_router.get("/reports/members")
async def report_members(user: dict = Depends(get_current_user)):
    total = await db.members.count_documents({})
    active = await db.members.count_documents({"status": "active"})
    inactive = await db.members.count_documents({"status": "inactive"})
    resigned = await db.members.count_documents({"status": "resigned"})
    deceased = await db.members.count_documents({"status": "deceased"})
    return {"total": total, "active": active, "inactive": inactive,
            "resigned": resigned, "deceased": deceased}

@api_router.get("/reports/contributions/{year}")
async def report_contributions(year: int, user: dict = Depends(get_current_user)):
    docs = await db.contributions.find({"year": year}).to_list(5000)
    by_month: dict = {}
    for d in docs:
        m = d["month"]
        if m not in by_month: by_month[m] = {"month": m, "count": 0, "total": 0}
        by_month[m]["count"] += 1
        by_month[m]["total"] += d["amount"]
    return {"year": year, "total": sum(d["amount"] for d in docs),
            "monthly": sorted(by_month.values(), key=lambda x: x["month"])}

@api_router.get("/reports/benefits")
async def report_benefits(user: dict = Depends(get_current_user)):
    marriage = await db.benefits.count_documents({"benefit_type": "marriage", "status": "paid"})
    housewarming = await db.benefits.count_documents({"benefit_type": "housewarming", "status": "paid"})
    medical = await db.medical_aid.count_documents({"status": "paid"})
    death = await db.death_assistance.count_documents({"status": "delivered"})
    m_docs = await db.benefits.find({"benefit_type": "marriage", "status": "paid"}).to_list(500)
    h_docs = await db.benefits.find({"benefit_type": "housewarming", "status": "paid"}).to_list(500)
    med_docs = await db.medical_aid.find({"status": "paid"}).to_list(500)
    return {
        "marriage_count": marriage, "marriage_total": sum(d["amount"] for d in m_docs),
        "housewarming_count": housewarming, "housewarming_total": sum(d["amount"] for d in h_docs),
        "medical_count": medical,
        "medical_total": sum(d.get("recommended_amount") or d.get("estimated_expense", 0) for d in med_docs),
        "death_count": death
    }

@api_router.post("/members/import")
async def import_members(
    file: UploadFile = File(...),
    user: dict = Depends(require_roles("super_admin", "secretary"))
):
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

    # Normalize column names
    df.columns = [str(c).lower().strip().replace(" ", "_") for c in df.columns]
    required = ["name", "mobile", "address"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(400, f"Missing required columns: {', '.join(missing)}. Required: name, mobile, address")

    imported = 0
    skipped = 0
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
            # Normalize date
            if len(joining_date) == 10 and joining_date[4] == "-":
                pass  # already YYYY-MM-DD
            else:
                try:
                    joining_date = pd.to_datetime(joining_date).strftime("%Y-%m-%d")
                except:
                    joining_date = datetime.now().date().isoformat()

            status_raw = str(row.get("status", "active")).strip().lower()
            status = status_raw if status_raw in ("active", "inactive", "resigned", "deceased") else "active"
            aadhaar_raw = str(row.get("aadhaar", "")).strip()
            aadhaar = aadhaar_raw if aadhaar_raw not in ("nan", "") else None

            member_id = await next_member_id()
            await db.members.insert_one({
                "member_id": member_id, "name": name, "mobile": mobile,
                "address": address, "joining_date": joining_date,
                "status": status, "aadhaar": aadhaar,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            imported += 1
        except Exception as e:
            errors.append(f"Row {i + 2}: {str(e)}")

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "total_rows": len(df),
        "message": f"Successfully imported {imported} members."
        + (f" Skipped {skipped} empty rows." if skipped else "")
        + (f" {len(errors)} rows had errors." if errors else "")
    }

# ── PDF RECEIPT ───────────────────────────────────────────────────────────────
MONTHS_NAMES = ["","January","February","March","April","May","June",
                "July","August","September","October","November","December"]

def build_receipt_pdf(contrib: dict, member: dict | None) -> bytes:
    pdf = new_pdf()
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    # Header bar
    pdf.set_fill_color(22, 101, 52)
    pdf.rect(0, 0, 210, 42, "F")
    pdf.image(LOGO_WHITE, x=12, y=7, h=28)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(10)
    pdf.set_font("noto", "B", 18)
    pdf.cell(0, 9, "TWENTY20 CHARITY GROUP", ln=True, align="C")
    pdf.set_font("noto", "B", 11)
    pdf.cell(0, 7, "WARIYAD", ln=True, align="C")
    pdf.set_font("noto", "", 9)
    pdf.cell(0, 6, "Monthly Contribution Receipt", ln=True, align="C")

    pdf.set_y(50)
    pdf.set_text_color(28, 25, 23)

    # Receipt meta
    def row(label: str, value: str, bold_val: bool = False):
        pdf.set_font("noto", "B", 10)
        pdf.cell(60, 8, label, ln=False)
        pdf.set_font("noto", "B" if bold_val else "", 10)
        pdf.cell(0, 8, value, ln=True)

    row("Receipt No:", contrib.get("receipt_number", "N/A"))
    paid_at = contrib.get("paid_at", "")
    try:
        dt_obj = datetime.fromisoformat(paid_at)
        date_str = dt_obj.strftime("%d %B %Y")
    except Exception:
        date_str = paid_at[:10] if paid_at else "-"
    row("Date:", date_str)

    # Divider
    pdf.set_draw_color(200, 200, 200)
    pdf.ln(3)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(5)

    # Member info
    pdf.set_font("noto", "B", 10)
    pdf.set_text_color(22, 101, 52)
    pdf.cell(0, 7, "MEMBER DETAILS", ln=True)
    pdf.set_text_color(28, 25, 23)
    row("Name:", member["name"] if member else "Unknown")
    row("Member ID:", member["member_id"] if member else "-")
    row("Mobile:", member.get("mobile", "-") if member else "-")

    pdf.ln(3)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(5)

    # Contribution info
    pdf.set_font("noto", "B", 10)
    pdf.set_text_color(22, 101, 52)
    pdf.cell(0, 7, "CONTRIBUTION DETAILS", ln=True)
    pdf.set_text_color(28, 25, 23)
    month_num = contrib.get("month", 1)
    month_str = MONTHS_NAMES[month_num] if 1 <= month_num <= 12 else str(month_num)
    row("Period:", f"{month_str} {contrib.get('year', '')}")
    method = str(contrib.get("payment_method", "-")).replace("_", " ").title()
    row("Payment Method:", method)

    # Amount box
    pdf.ln(5)
    pdf.set_fill_color(240, 253, 244)
    pdf.set_draw_color(22, 101, 52)
    pdf.rect(15, pdf.get_y(), 180, 18, "FD")
    pdf.set_font("noto", "B", 14)
    pdf.set_text_color(22, 101, 52)
    amount = contrib.get("amount", 0)
    pdf.set_y(pdf.get_y() + 3)
    pdf.cell(0, 8, f"AMOUNT PAID: Rs. {amount:,.0f}/-", ln=True, align="C")

    # Footer
    pdf.ln(15)
    pdf.set_text_color(120, 113, 108)
    pdf.set_font("noto", "I", 8)
    pdf.set_draw_color(231, 229, 228)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)
    pdf.cell(0, 5, "This is a computer-generated receipt. No signature required.", ln=True, align="C")
    pdf.cell(0, 5, "Twenty20 Charity Group Wariyad - Serving the community", ln=True, align="C")

    return bytes(pdf.output())

@api_router.get("/contributions/{contrib_id}/receipt")
async def download_receipt(contrib_id: str, user: dict = Depends(get_current_user)):
    contrib = await db.contributions.find_one({"_id": safe_oid(contrib_id)})
    if not contrib:
        raise HTTPException(404, "Contribution not found")
    # Members can only download their own receipts (match on _id or TW- code)
    if user["role"] == "member":
        owner = None
        cmid = contrib.get("member_id")
        if cmid and ObjectId.is_valid(cmid):
            owner = await db.members.find_one({"_id": ObjectId(cmid)})
        if not _member_owns(user, owner):
            raise HTTPException(403, "Access denied")
    member = None
    if contrib.get("member_id") and ObjectId.is_valid(contrib["member_id"]):
        try:
            member = await db.members.find_one({"_id": ObjectId(contrib["member_id"])})
        except Exception:
            pass

    pdf_bytes = build_receipt_pdf(contrib, member)
    rnum = contrib.get("receipt_number", "receipt")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={rnum}.pdf"}
    )

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
async def export_excel_report(
    year: Optional[int] = None,
    user: dict = Depends(require_roles("super_admin", "president", "treasurer", "secretary", "auditor"))
):
    yr = year or datetime.now().year
    contributions = await db.contributions.find({"year": yr}).to_list(5000)
    benefits = await db.benefits.find({}).to_list(2000)
    cashbook = await db.cashbook.find({}).sort("created_at", 1).to_list(10000)
    members = await db.members.find({}).to_list(1000)
    member_map = {str(m["_id"]): m for m in members}

    contrib_rows = [
        {
            "Receipt No":       _safe_cell(c.get("receipt_number", "")),
            "Month":            _MONTH_NAMES_SHORT[c.get("month", 1)],
            "Year":             c.get("year", yr),
            "Member Name":      _safe_cell(member_map.get(c.get("member_id", ""), {}).get("name", "Unknown")),
            "Amount (Rs)":      c.get("amount", 0),
            "Payment Method":   _safe_cell(c.get("payment_method", "").replace("_", " ").title()),
            "Date Paid":        c.get("paid_at", "")[:10] if c.get("paid_at") else "",
        }
        for c in contributions
    ]
    benefit_rows = [
        {
            "Benefit Type": _safe_cell(b.get("benefit_type", "").replace("_", " ").title()),
            "Member Name":  _safe_cell(b.get("member_name", "")),
            "Amount (Rs)":  b.get("amount", 0),
            "Status":       _safe_cell(b.get("status", "").replace("_", " ").title()),
            "Event Date":   b.get("event_date", ""),
            "Applied Date": b.get("created_at", "")[:10] if b.get("created_at") else "",
        }
        for b in benefits
    ]
    running_bal = 0
    cashbook_rows = []
    for e in cashbook:
        running_bal += e["amount"] if e["entry_type"] == "credit" else -e["amount"]
        cashbook_rows.append({
            "Voucher No":   _safe_cell(e.get("voucher_number", "")),
            "Date":         e.get("date", ""),
            "Description":  _safe_cell(e.get("description", "")),
            "Category":     _safe_cell(e.get("category", "").replace("_", " ").title()),
            "Type":         "Credit" if e["entry_type"] == "credit" else "Debit",
            "Credit (Rs)":  e["amount"] if e["entry_type"] == "credit" else 0,
            "Debit (Rs)":   e["amount"] if e["entry_type"] == "debit" else 0,
            "Balance (Rs)": round(running_bal, 2),
        })
    member_rows = [
        {
            "Member ID":    m.get("member_id", ""),
            "Name":         _safe_cell(m.get("name", "")),
            "Mobile":       _safe_cell(m.get("mobile", "")),
            "Address":      _safe_cell(m.get("address", "")),
            "Joining Date": m.get("joining_date", ""),
            "Status":       m.get("status", "").title(),
        }
        for m in members
    ]
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
async def export_pdf_report(
    year: Optional[int] = None,
    user: dict = Depends(require_roles("super_admin", "president", "treasurer", "secretary", "auditor"))
):
    yr = year or datetime.now().year
    contributions = await db.contributions.find({"year": yr}).to_list(5000)
    benefits_paid = await db.benefits.find({"status": "paid"}).to_list(500)
    medical_paid = await db.medical_aid.find({"status": "paid"}).to_list(500)
    cashbook = await db.cashbook.find({}).to_list(10000)
    members = await db.members.find({}).to_list(1000)

    total_contrib = sum(c["amount"] for c in contributions)
    total_credits = sum(e["amount"] for e in cashbook if e["entry_type"] == "credit")
    total_debits = sum(e["amount"] for e in cashbook if e["entry_type"] == "debit")
    balance = total_credits - total_debits
    monthly = {}
    for c in contributions:
        m = c["month"]
        if m not in monthly:
            monthly[m] = {"count": 0, "amount": 0}
        monthly[m]["count"] += 1
        monthly[m]["amount"] += c["amount"]

    pdf = new_pdf()
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    # Header
    pdf.set_fill_color(22, 101, 52)
    pdf.rect(0, 0, 210, 42, "F")
    pdf.image(LOGO_WHITE, x=12, y=7, h=28)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(10)
    pdf.set_font("noto", "B", 18)
    pdf.cell(0, 9, "TWENTY20 CHARITY GROUP", ln=True, align="C")
    pdf.set_font("noto", "B", 11)
    pdf.cell(0, 7, "WARIYAD", ln=True, align="C")
    pdf.set_font("noto", "", 9)
    pdf.cell(0, 6, f"Annual Financial Report - {yr}", ln=True, align="C")
    pdf.set_y(50)
    pdf.set_text_color(28, 25, 23)
    # Summary
    pdf.set_font("noto", "B", 12)
    pdf.set_text_color(22, 101, 52)
    pdf.cell(0, 8, f"ANNUAL SUMMARY - {yr}", ln=True)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)
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
        pdf.set_font("noto", "B", 10)
        pdf.cell(110, 7, label, ln=False)
        pdf.set_font("noto", "", 10)
        pdf.cell(0, 7, value, ln=True)
    # Monthly table
    pdf.ln(5)
    pdf.set_font("noto", "B", 11)
    pdf.set_text_color(22, 101, 52)
    pdf.cell(0, 8, "MONTHLY CONTRIBUTION BREAKDOWN", ln=True)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    pdf.set_fill_color(22, 101, 52)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("noto", "B", 9)
    pdf.cell(60, 7, "Month", border=1, fill=True, align="C")
    pdf.cell(50, 7, "Members Paid", border=1, fill=True, align="C")
    pdf.cell(70, 7, "Amount Collected (Rs)", border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_text_color(28, 25, 23)
    pdf.set_font("noto", "", 9)
    t_count = 0
    for m_idx in range(1, 13):
        md = monthly.get(m_idx, {"count": 0, "amount": 0})
        fill = m_idx % 2 == 0
        if fill:
            pdf.set_fill_color(248, 248, 248)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.cell(60, 6, _MONTH_NAMES_FULL[m_idx], border=1, fill=fill)
        pdf.cell(50, 6, str(md["count"]), border=1, fill=fill, align="C")
        pdf.cell(70, 6, f"{md['amount']:,.0f}", border=1, fill=fill, align="R")
        pdf.ln()
        t_count += md["count"]
    pdf.set_fill_color(22, 101, 52)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("noto", "B", 9)
    pdf.cell(60, 7, "TOTAL", border=1, fill=True)
    pdf.cell(50, 7, str(t_count), border=1, fill=True, align="C")
    pdf.cell(70, 7, f"{total_contrib:,.0f}", border=1, fill=True, align="R")
    pdf.ln()
    # Footer
    pdf.ln(10)
    pdf.set_text_color(120, 113, 108)
    pdf.set_font("noto", "I", 8)
    pdf.set_draw_color(231, 229, 228)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)
    pdf.cell(0, 5, f"Generated on {datetime.now().strftime('%d %B %Y')} - Twenty20 Charity Group Wariyad", ln=True, align="C")
    pdf.cell(0, 5, "This is a computer-generated report. For official audit purposes.", ln=True, align="C")
    pdf_bytes = bytes(pdf.output())
    return StreamingResponse(io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Twenty20_Wariyad_Report_{yr}.pdf"})


# ── NOTIFICATIONS ──────────────────────────────────────────────────────────────
@api_router.get("/notifications/defaulters")
async def get_defaulters(
    month: int, year: int,
    user: dict = Depends(require_roles("super_admin", "president", "secretary", "treasurer"))
):
    members = await db.members.find({"status": "active"}).to_list(500)
    contributions = await db.contributions.find({"year": year, "month": month}).to_list(500)
    paid_ids = {c["member_id"] for c in contributions}
    defaulters = [
        {
            "member_id": str(m["_id"]),
            "member_code": m.get("member_id", ""),
            "name": m["name"],
            "mobile": m.get("mobile", ""),
            "address": m.get("address", ""),
        }
        for m in members if str(m["_id"]) not in paid_ids
    ]
    return {
        "month": month, "year": year,
        "total_active": len(members),
        "total_paid": len(paid_ids),
        "total_defaulters": len(defaulters),
        "defaulters": defaulters,
        "twilio_enabled": TWILIO_ENABLED,
    }


@api_router.post("/notifications/send-reminders")
async def send_reminders(
    data: NotificationSendReq,
    user: dict = Depends(require_roles("super_admin", "president", "secretary", "treasurer"))
):
    members = await db.members.find({"status": "active"}).to_list(500)
    contributions = await db.contributions.find({"year": data.year, "month": data.month}).to_list(500)
    paid_ids = {c["member_id"] for c in contributions}
    defaulters = [m for m in members if str(m["_id"]) not in paid_ids]
    if not defaulters:
        return {"sent": 0, "message": "No defaulters found for this month.", "mode": "none", "results": []}
    month_name = _MONTH_NAMES_FULL[data.month] if 1 <= data.month <= 12 else str(data.month)
    msg = (data.message or
           f"Dear Member, your monthly contribution of Rs.100 for {month_name} {data.year} "
           f"is pending. Please pay at the earliest. - Twenty20 Charity Group Wariyad")
    results = []
    sms_sent = 0
    wa_sent = 0
    if TWILIO_ENABLED:
        tc = TwilioClient(_TWILIO_SID, _TWILIO_TOKEN)
        for m in defaulters:
            phone = m.get("mobile", "")
            if not phone:
                results.append({"member": m["name"], "status": "skipped", "reason": "no phone"})
                continue
            ph = phone.strip().replace(" ", "").replace("-", "")
            if not ph.startswith("+"):
                ph = "+91" + ph
            sms_ok = wa_ok = False
            try:
                tc.messages.create(body=msg, from_=_TWILIO_FROM, to=ph)
                sms_ok = True; sms_sent += 1
            except Exception as e:
                logger.error(f"SMS failed for {m['name']}: {e}")
            if _TWILIO_WA_FROM:
                try:
                    tc.messages.create(body=msg, from_=f"whatsapp:{_TWILIO_WA_FROM}", to=f"whatsapp:{ph}")
                    wa_ok = True; wa_sent += 1
                except Exception as e:
                    logger.error(f"WhatsApp failed for {m['name']}: {e}")
            results.append({"member": m["name"], "phone": ph,
                            "sms": "sent" if sms_ok else "failed",
                            "whatsapp": "sent" if wa_ok else "failed"})
    else:
        for m in defaulters:
            logger.info(f"[MOCK SMS] To: {m.get('mobile','N/A')} | {msg[:80]}")
            results.append({"member": m["name"], "phone": m.get("mobile", "N/A"), "sms": "mock", "whatsapp": "mock"})
    await db.notification_logs.insert_one({
        "type": "monthly_reminder", "month": data.month, "year": data.year,
        "sent_by": user["id"], "mode": "live" if TWILIO_ENABLED else "mock",
        "sent_count": len(defaulters), "sms_sent": sms_sent, "wa_sent": wa_sent,
        "results": results[:50], "created_at": datetime.now(timezone.utc).isoformat()
    })
    return {
        "sent": len(defaulters), "sms_sent": sms_sent, "wa_sent": wa_sent,
        "mode": "live" if TWILIO_ENABLED else "mock",
        "message": (
            f"Reminders sent to {len(defaulters)} defaulters via SMS and WhatsApp."
            if TWILIO_ENABLED else
            f"[MOCK] Twilio not configured. Would notify {len(defaulters)} defaulters. "
            f"Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_PHONE to backend/.env to enable real sending."
        ),
        "results": results,
    }


# ── AUDIT MODULE ───────────────────────────────────────────────────────────────
@api_router.get("/audit/report")
async def get_audit_report(
    year: Optional[int] = None,
    user: dict = Depends(require_roles("super_admin", "president", "secretary", "treasurer", "auditor"))
):
    yr = year or datetime.now().year
    contributions = await db.contributions.find({"year": yr}).to_list(5000)
    benefits_paid = await db.benefits.find({"status": "paid"}).to_list(500)
    medical_paid = await db.medical_aid.find({"status": "paid"}).to_list(500)
    death_delivered = await db.death_assistance.find({"status": "delivered"}).to_list(500)
    cashbook = await db.cashbook.find({}).to_list(10000)
    members = await db.members.find({}).to_list(1000)
    total_contrib = sum(c["amount"] for c in contributions)
    total_credits = sum(e["amount"] for e in cashbook if e["entry_type"] == "credit")
    total_debits = sum(e["amount"] for e in cashbook if e["entry_type"] == "debit")
    monthly = {}
    for c in contributions:
        m = c["month"]
        if m not in monthly:
            monthly[m] = {"month": m, "count": 0, "amount": 0}
        monthly[m]["count"] += 1
        monthly[m]["amount"] += c["amount"]
    m_marriage = [b for b in benefits_paid if b.get("benefit_type") == "marriage"]
    m_house = [b for b in benefits_paid if b.get("benefit_type") == "housewarming"]
    return {
        "year": yr,
        "total_members": len(members),
        "active_members": sum(1 for m in members if m.get("status") == "active"),
        "total_contributions": total_contrib,
        "contribution_count": len(contributions),
        "monthly_breakdown": sorted(monthly.values(), key=lambda x: x["month"]),
        "marriage_count": len(m_marriage),
        "marriage_total": sum(b.get("amount", 0) for b in m_marriage),
        "housewarming_count": len(m_house),
        "housewarming_total": sum(b.get("amount", 0) for b in m_house),
        "medical_aid_count": len(medical_paid),
        "medical_aid_total": sum(d.get("recommended_amount") or d.get("estimated_expense", 0) for d in medical_paid),
        "death_cases": len(death_delivered),
        "total_credits": total_credits,
        "total_debits": total_debits,
        "closing_balance": round(total_credits - total_debits, 2),
    }


@api_router.post("/audit/sign-off")
async def create_audit_sign_off(
    data: AuditSignOffCreate,
    user: dict = Depends(require_roles("auditor"))
):
    existing = await db.audit_sign_offs.find_one({"year": data.year, "auditor_id": user["id"]})
    if existing:
        raise HTTPException(400, f"You have already signed off on year {data.year}. Only one sign-off per auditor per year is allowed.")
    doc = {
        "year": data.year, "remarks": data.remarks,
        "auditor_id": user["id"], "auditor_name": user["name"],
        "auditor_email": user["email"],
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await db.audit_sign_offs.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@api_router.get("/audit/sign-offs")
async def list_audit_sign_offs(
    user: dict = Depends(require_roles("super_admin", "president", "secretary", "treasurer", "auditor"))
):
    docs = await db.audit_sign_offs.find().sort("signed_at", -1).to_list(200)
    return ss(docs)


# ── DEMO DATA SEEDING ─────────────────────────────────────────────────────────
@api_router.post("/demo/seed")
async def seed_demo_data(user: dict = Depends(require_roles("super_admin"))):
    demo_members = [
        {"name": "Mohammed Ashraf", "mobile": "9876543210", "address": "House No 12, Main Road, Wariyad", "joining_date": "2022-01-15", "status": "active"},
        {"name": "Suhail Ahmed Khan", "mobile": "9876543211", "address": "Near Mosque, Wariyad", "joining_date": "2022-02-20", "status": "active"},
        {"name": "Abdul Rasheed", "mobile": "9876543212", "address": "Plot 45, East Block, Wariyad", "joining_date": "2022-03-10", "status": "active"},
        {"name": "Basheer Ibrahim", "mobile": "9876543213", "address": "House 78, West Lane, Wariyad", "joining_date": "2022-04-05", "status": "active"},
        {"name": "Faisal Mohammed", "mobile": "9876543214", "address": "Colony Road, Wariyad", "joining_date": "2022-05-12", "status": "active"},
        {"name": "Hameed Ali", "mobile": "9876543215", "address": "Market Street, Wariyad", "joining_date": "2022-06-18", "status": "active"},
        {"name": "Ibrahim Kutty", "mobile": "9876543216", "address": "Near School, Wariyad", "joining_date": "2022-07-22", "status": "active"},
        {"name": "Jabir Haneef", "mobile": "9876543217", "address": "Bus Stand Road, Wariyad", "joining_date": "2022-08-30", "status": "active"},
        {"name": "Khalid Mansoor", "mobile": "9876543218", "address": "Temple Road, Wariyad", "joining_date": "2022-09-14", "status": "active"},
        {"name": "Latheef Salim", "mobile": "9876543219", "address": "Ring Road, Wariyad", "joining_date": "2022-10-08", "status": "active"},
        {"name": "Mujeeb Rahman", "mobile": "9876543220", "address": "North Gate, Wariyad", "joining_date": "2022-11-03", "status": "active"},
        {"name": "Noufal Hassan", "mobile": "9876543221", "address": "South Block, Wariyad", "joining_date": "2022-12-17", "status": "active"},
        {"name": "Omar Farooq", "mobile": "9876543222", "address": "Riverside Road, Wariyad", "joining_date": "2023-01-09", "status": "active"},
        {"name": "Rafeeq Ahamed", "mobile": "9876543223", "address": "Hill View, Wariyad", "joining_date": "2023-02-14", "status": "inactive"},
        {"name": "Salim Babu", "mobile": "9876543224", "address": "Garden Lane, Wariyad", "joining_date": "2023-03-21", "status": "active"},
    ]

    created_ids = []
    members_created = 0
    for md in demo_members:
        existing = await db.members.find_one({"mobile": md["mobile"]})
        if existing:
            created_ids.append({"_id": existing["_id"], "name": existing["name"]})
        else:
            member_id = await next_member_id()
            doc = {**md, "member_id": member_id, "created_at": datetime.now(timezone.utc).isoformat()}
            result = await db.members.insert_one(doc)
            doc["_id"] = result.inserted_id
            created_ids.append({"_id": result.inserted_id, "name": md["name"]})
            members_created += 1

    # Contributions for active members — last 4 months
    now = datetime.now()
    months_to_seed = []
    for i in range(4):
        m = now.month - i
        y = now.year
        if m <= 0:
            m += 12
            y -= 1
        months_to_seed.append((m, y))

    contrib_count = 0
    for member_info in created_ids:
        mid = str(member_info["_id"])
        # Active members pay for all months; some skip last month (overdue)
        for idx, (month, year) in enumerate(months_to_seed):
            if idx == 0 and created_ids.index(member_info) % 4 == 0:
                continue  # simulate 1 in 4 members pending this month
            existing_c = await db.contributions.find_one({"member_id": mid, "month": month, "year": year})
            if existing_c:
                continue
            receipt = await next_receipt()
            doc = {
                "member_id": mid, "month": month, "year": year,
                "amount": 100.0, "payment_method": "cash",
                "receipt_number": receipt, "recorded_by": user["id"],
                "paid_at": datetime.now(timezone.utc).isoformat()
            }
            result = await db.contributions.insert_one(doc)
            cid = str(result.inserted_id)
            await db.cashbook.insert_one({
                "entry_type": "credit", "category": "contribution",
                "description": f"Monthly contribution - {year}/{month:02d} ({member_info['name']})",
                "amount": 100.0, "date": datetime.now(timezone.utc).date().isoformat(),
                "reference_id": cid, "voucher_number": await next_voucher(),
                "recorded_by": user["id"], "created_at": datetime.now(timezone.utc).isoformat()
            })
            contrib_count += 1

    # Seed a sample marriage benefit
    if created_ids:
        first_mid = str(created_ids[0]["_id"])
        existing_b = await db.benefits.find_one({"member_id": first_mid, "benefit_type": "marriage"})
        if not existing_b:
            await db.benefits.insert_one({
                "member_id": first_mid, "member_name": created_ids[0]["name"],
                "benefit_type": "marriage", "amount": 5000,
                "event_date": "2026-05-10", "status": "committee_approved",
                "applied_by": user["id"], "created_at": datetime.now(timezone.utc).isoformat()
            })

    # Seed a sample medical aid request
    existing_med = await db.medical_aid.find_one({"applicant_name": "Basheer Ibrahim (Demo)"})
    if not existing_med:
        await db.medical_aid.insert_one({
            "applicant_name": "Basheer Ibrahim (Demo)", "contact": "9876543213",
            "address": "Plot 45, East Block, Wariyad",
            "medical_condition": "Cardiac Surgery", "hospital": "Govt Medical College",
            "estimated_expense": 45000.0, "recommended_amount": 10000.0,
            "status": "approved", "notes": "Recommended ₹10,000 by committee",
            "applied_by": user["id"], "created_at": datetime.now(timezone.utc).isoformat()
        })

    return {
        "members_created": members_created,
        "members_already_existed": len(created_ids) - members_created,
        "contributions_created": contrib_count,
        "message": f"Demo data loaded: {members_created} new members, {contrib_count} contributions added."
    }


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.contributions.create_index([("member_id", 1), ("month", 1), ("year", 1)])
    await db.members.create_index("member_id", unique=True)
    admin_email    = os.environ["ADMIN_EMAIL"]
    admin_password = os.environ["ADMIN_PASSWORD"]   # no default — must be set explicitly
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "name": "Super Admin", "email": admin_email,
            "password_hash": hash_password(admin_password),
            "role": "super_admin", "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Admin seeded: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}})

app.include_router(api_router)

@app.on_event("shutdown")
async def shutdown():
    client.close()
