"""SQLModel table definitions — Postgres-ready (UUID PKs, JSON/JSONB columns).

Mirrors the original Mongo collections one-to-one. IDs are UUIDs (was ObjectId).
List/dict fields (committee positions, checklists, meeting attendees/resolutions,
notification results) are stored as JSON, which becomes JSONB on PostgreSQL.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on Postgres, JSON elsewhere (SQLite for local dev)
JSONType = JSON().with_variant(JSONB, "postgresql")


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    password_hash: str
    role: str = "member"
    member_id: Optional[str] = None
    is_active: bool = True
    created_at: str = Field(default_factory=_now)


class Member(SQLModel, table=True):
    __tablename__ = "members"
    id: str = Field(default_factory=_uuid, primary_key=True)
    member_id: str = Field(index=True, unique=True)  # business code TW-001
    name: str
    mobile: str
    address: str
    joining_date: str                 # YYYY-MM-DD — drives intro-rate timing
    status: str = "active"
    aadhaar: Optional[str] = None
    # ── Ledger fields ──────────────────────────────────────────────
    intro_rate: Optional[float] = None        # per-member first-year rate (₹200 default via settings)
    opening_balance: float = 0.0              # balance carried in before ledger_start (− pending, + advance)
    ledger_start: Optional[str] = None        # "YYYY-MM" the opening_balance applies to (default = joining month)
    inactive_from: Optional[str] = None       # "YYYY-MM" — dues stop accruing from this month
    created_at: str = Field(default_factory=_now)


class OrgSettings(SQLModel, table=True):
    """Single-row org configuration for contribution rates (admin-editable)."""
    __tablename__ = "org_settings"
    id: str = Field(default_factory=_uuid, primary_key=True)
    standard_rate: float = 100.0
    intro_rate: float = 200.0
    intro_months: int = 12
    updated_by: Optional[str] = None
    updated_at: str = Field(default_factory=_now)


class MonthlyDues(SQLModel, table=True):
    """One ledger line per member per month: the dues + total paid toward it."""
    __tablename__ = "monthly_dues"
    __table_args__ = (UniqueConstraint("member_id", "year", "month", name="uq_dues_member_year_month"),)
    id: str = Field(default_factory=_uuid, primary_key=True)
    member_id: str = Field(index=True)
    year: int = Field(index=True)
    month: int
    rate: float                                # dues for this month (intro/standard resolved)
    paid: float = 0.0                          # total applied to this month
    status: str = "pending"                    # up_to_date | pending | advance (derived snapshot)
    created_at: str = Field(default_factory=_now)


class Payment(SQLModel, table=True):
    """An actual payment event — supports partial, exact, or over-payment."""
    __tablename__ = "payments"
    id: str = Field(default_factory=_uuid, primary_key=True)
    member_id: str = Field(index=True)
    amount: float
    payment_method: str                        # cash | upi | ...
    year: int                                  # the month the payment was booked against
    month: int
    receipt_number: Optional[str] = None
    allocation: list = Field(default_factory=list, sa_column=Column(JSONType))  # [{year,month,amount,kind}]
    recorded_by: Optional[str] = None
    paid_at: str = Field(default_factory=_now)


class Benefit(SQLModel, table=True):
    __tablename__ = "benefits"
    id: str = Field(default_factory=_uuid, primary_key=True)
    member_id: str = Field(index=True)
    member_name: Optional[str] = None
    benefit_type: str
    amount: float = 0
    status: str = "pending"
    event_date: Optional[str] = None
    notes: Optional[str] = None
    applied_by: Optional[str] = None
    secretary_verified_by: Optional[str] = None
    secretary_verified_at: Optional[str] = None
    committee_approved_by: Optional[str] = None
    committee_approved_at: Optional[str] = None
    paid_by: Optional[str] = None
    paid_at: Optional[str] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[str] = None
    created_at: str = Field(default_factory=_now)


class MedicalAid(SQLModel, table=True):
    __tablename__ = "medical_aid"
    id: str = Field(default_factory=_uuid, primary_key=True)
    applicant_name: str
    contact: str
    address: str
    medical_condition: str
    hospital: str
    estimated_expense: float
    recommended_amount: Optional[float] = None
    status: str = "pending"
    notes: Optional[str] = None
    applied_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    paid_by: Optional[str] = None
    paid_at: Optional[str] = None
    created_at: str = Field(default_factory=_now)


class DeathAssistance(SQLModel, table=True):
    __tablename__ = "death_assistance"
    id: str = Field(default_factory=_uuid, primary_key=True)
    deceased_name: str
    member_id: Optional[str] = None
    family_details: str
    address: str
    contact_person: str
    date_of_death: str
    grocery_kit_value: Optional[float] = None
    delivery_date: Optional[str] = None
    remarks: Optional[str] = None
    status: str = "pending"
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    created_at: str = Field(default_factory=_now)


class Cashbook(SQLModel, table=True):
    __tablename__ = "cashbook"
    id: str = Field(default_factory=_uuid, primary_key=True)
    entry_type: str  # credit | debit
    category: str
    description: str
    amount: float
    date: str
    reference_id: Optional[str] = None
    voucher_number: Optional[str] = None
    recorded_by: Optional[str] = None
    created_at: str = Field(default_factory=_now)


class Committee(SQLModel, table=True):
    __tablename__ = "committee"
    id: str = Field(default_factory=_uuid, primary_key=True)
    year: int
    positions: List[dict] = Field(default_factory=list, sa_column=Column(JSONType))
    start_date: str
    end_date: str
    is_active: bool = True
    created_by: Optional[str] = None
    created_at: str = Field(default_factory=_now)


class CommitteeHandover(SQLModel, table=True):
    __tablename__ = "committee_handovers"
    id: str = Field(default_factory=_uuid, primary_key=True)
    from_year: int
    to_year: int
    handover_date: str
    fund_balance: float
    documents_checklist: List[dict] = Field(default_factory=list, sa_column=Column(JSONType))
    registers_checklist: List[dict] = Field(default_factory=list, sa_column=Column(JSONType))
    outstanding_items: Optional[str] = None
    notes: Optional[str] = None
    recorded_by: Optional[str] = None
    recorded_by_name: Optional[str] = None
    created_at: str = Field(default_factory=_now)


class Meeting(SQLModel, table=True):
    __tablename__ = "meetings"
    id: str = Field(default_factory=_uuid, primary_key=True)
    meeting_type: str
    title: str
    scheduled_date: str
    agenda: str
    attendees: List[str] = Field(default_factory=list, sa_column=Column(JSONType))
    minutes: Optional[str] = None
    resolutions: Optional[str] = None
    resolutions_list: Optional[List[dict]] = Field(default=None, sa_column=Column(JSONType))
    status: str = "scheduled"
    created_by: Optional[str] = None
    created_at: str = Field(default_factory=_now)


class NotificationLog(SQLModel, table=True):
    __tablename__ = "notification_logs"
    id: str = Field(default_factory=_uuid, primary_key=True)
    type: str
    month: int
    year: int
    sent_by: Optional[str] = None
    mode: str
    sent_count: int = 0
    sms_sent: int = 0
    wa_sent: int = 0
    results: List[dict] = Field(default_factory=list, sa_column=Column(JSONType))
    created_at: str = Field(default_factory=_now)


class AuditSignOff(SQLModel, table=True):
    __tablename__ = "audit_sign_offs"
    __table_args__ = (UniqueConstraint("year", "auditor_id", name="uq_audit_year_auditor"),)
    id: str = Field(default_factory=_uuid, primary_key=True)
    year: int
    remarks: str
    auditor_id: str
    auditor_name: Optional[str] = None
    auditor_email: Optional[str] = None
    signed_at: str = Field(default_factory=_now)
    created_at: str = Field(default_factory=_now)
