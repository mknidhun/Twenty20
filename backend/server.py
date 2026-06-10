from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends
from fastapi.responses import Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, BeforeValidator
from typing import Annotated, Optional, List
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os, jwt, bcrypt, logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Database ─────────────────────────────────────────────────────────────────
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_ALGORITHM = "HS256"
def get_jwt_secret(): return os.environ["JWT_SECRET"]

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
    email: str
    password: str

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "member"
    member_id: Optional[str] = None

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
    status: Optional[str] = None
    attendees: Optional[List[str]] = None

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Twenty20 Wariyad API")
api_router = APIRouter(prefix="/api")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        "role": data.role, "member_id": data.member_id,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    })).inserted_id
    user_id = str(uid)
    at = create_access_token(user_id, email)
    rt = create_refresh_token(user_id)
    response.set_cookie("access_token", at, httponly=True, secure=False, samesite="lax", max_age=28800)
    response.set_cookie("refresh_token", rt, httponly=True, secure=False, samesite="lax", max_age=604800)
    return {"id": user_id, "name": data.name, "email": email, "role": data.role}

@api_router.post("/auth/login")
async def login(data: LoginReq, response: Response):
    email = data.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    user_id = str(user["_id"])
    at = create_access_token(user_id, email)
    rt = create_refresh_token(user_id)
    response.set_cookie("access_token", at, httponly=True, secure=False, samesite="lax", max_age=28800)
    response.set_cookie("refresh_token", rt, httponly=True, secure=False, samesite="lax", max_age=604800)
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
    await db.users.update_one({"_id": ObjectId(uid)}, {"$set": upd})
    doc = await db.users.find_one({"_id": ObjectId(uid)}, {"password_hash": 0})
    return s(doc)

@api_router.delete("/users/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_roles("super_admin"))):
    await db.users.delete_one({"_id": ObjectId(uid)})
    return {"message": "User deleted"}

# ── MEMBERS ───────────────────────────────────────────────────────────────────
@api_router.get("/members")
async def list_members(user: dict = Depends(get_current_user)):
    docs = await db.members.find().sort("created_at", -1).to_list(500)
    return ss(docs)

@api_router.post("/members")
async def create_member(data: MemberCreate, user: dict = Depends(require_roles("super_admin", "secretary", "treasurer"))):
    mid = await next_member_id()
    doc = {**data.model_dump(), "member_id": mid,
           "created_at": datetime.now(timezone.utc).isoformat()}
    result = await db.members.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc

@api_router.get("/members/{mid}")
async def get_member(mid: str, user: dict = Depends(get_current_user)):
    doc = await db.members.find_one({"_id": ObjectId(mid)})
    if not doc: raise HTTPException(404, "Member not found")
    return s(doc)

@api_router.put("/members/{mid}")
async def update_member(mid: str, data: MemberUpdate, user: dict = Depends(require_roles("super_admin", "secretary", "treasurer"))):
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    await db.members.update_one({"_id": ObjectId(mid)}, {"$set": upd})
    return s(await db.members.find_one({"_id": ObjectId(mid)}))

@api_router.delete("/members/{mid}")
async def delete_member(mid: str, user: dict = Depends(require_roles("super_admin"))):
    await db.members.delete_one({"_id": ObjectId(mid)})
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
    member = await db.members.find_one({"_id": ObjectId(data.member_id)})
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
    await db.contributions.delete_one({"_id": ObjectId(cid)})
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
        benefit = await db.benefits.find_one({"_id": ObjectId(bid)})
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
    await db.benefits.update_one({"_id": ObjectId(bid)}, {"$set": upd})
    return s(await db.benefits.find_one({"_id": ObjectId(bid)}))

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
        aid = await db.medical_aid.find_one({"_id": ObjectId(aid_id)})
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
    await db.medical_aid.update_one({"_id": ObjectId(aid_id)}, {"$set": upd})
    return s(await db.medical_aid.find_one({"_id": ObjectId(aid_id)}))

@api_router.delete("/medical-aid/{aid_id}")
async def delete_medical_aid(aid_id: str, user: dict = Depends(require_roles("super_admin"))):
    await db.medical_aid.delete_one({"_id": ObjectId(aid_id)})
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
    await db.death_assistance.update_one({"_id": ObjectId(case_id)}, {"$set": upd})
    return s(await db.death_assistance.find_one({"_id": ObjectId(case_id)}))

@api_router.delete("/death-assistance/{case_id}")
async def delete_death_assistance(case_id: str, user: dict = Depends(require_roles("super_admin"))):
    await db.death_assistance.delete_one({"_id": ObjectId(case_id)})
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
    await db.cashbook.delete_one({"_id": ObjectId(eid)})
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

@api_router.put("/committee/{cid}")
async def update_committee(cid: str, data: dict, user: dict = Depends(require_roles("super_admin", "president"))):
    await db.committee.update_one({"_id": ObjectId(cid)}, {"$set": data})
    return s(await db.committee.find_one({"_id": ObjectId(cid)}))

@api_router.delete("/committee/{cid}")
async def delete_committee(cid: str, user: dict = Depends(require_roles("super_admin"))):
    await db.committee.delete_one({"_id": ObjectId(cid)})
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
    await db.meetings.update_one({"_id": ObjectId(mid)}, {"$set": upd})
    return s(await db.meetings.find_one({"_id": ObjectId(mid)}))

@api_router.delete("/meetings/{mid}")
async def delete_meeting(mid: str, user: dict = Depends(require_roles("super_admin", "president", "secretary"))):
    await db.meetings.delete_one({"_id": ObjectId(mid)})
    return {"message": "Deleted"}

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

# ── STARTUP ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.contributions.create_index([("member_id", 1), ("month", 1), ("year", 1)])
    await db.members.create_index("member_id", unique=True)
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@twenty20wariyad.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@20W20")
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
    mem_path = Path("/app/memory")
    mem_path.mkdir(exist_ok=True)
    (mem_path / "test_credentials.md").write_text(
        f"# Test Credentials\n\n## Super Admin\n- Email: {admin_email}\n- Password: {admin_password}\n- Role: super_admin\n\n"
        "## Auth Endpoints\n- POST /api/auth/login\n- POST /api/auth/register\n- GET /api/auth/me\n- POST /api/auth/logout\n"
    )

app.include_router(api_router)

@app.on_event("shutdown")
async def shutdown():
    client.close()
