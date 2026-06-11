#!/usr/bin/env python3
"""
Twenty20 Wariyad — Data Migration Script
Clears all demo data and imports real organizational data from Excel files.
Run: python3 migrate_data.py
"""

import asyncio
import os
import sys
import pandas as pd
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

MONGO_URL = os.environ['MONGO_URL']
DB_NAME    = os.environ['DB_NAME']

client = AsyncIOMotorClient(MONGO_URL)
db     = client[DB_NAME]

CONTRIBUTIONS_FILE = '/tmp/contributions.xlsx'
CASHBOOK_FILE      = '/tmp/cashbook.xlsx'
BENEFITS_FILE      = '/tmp/benefits.xlsx'

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# Map contributions sheet names → (month, year)
CONTRIB_MONTH_MAP = {
    'May 2026': (5, 2026), 'Jun 2026': (6, 2026),  'Jul 2026': (7, 2026),
    'Aug 2026': (8, 2026), 'Sep 2026': (9, 2026),  'Oct 2026': (10, 2026),
    'Nov 2026': (11, 2026),'Dec 2026': (12, 2026), 'Jan 2027': (1, 2027),
    'Feb 2027': (2, 2027), 'Mar 2027': (3, 2027),  'Apr 2027': (4, 2027),
}

# ── Step 1: Clear existing collections ───────────────────────────────────────
async def clear_data():
    print("Clearing existing data...")
    for col in ['members', 'contributions', 'cashbook', 'benefits',
                'medical_aid', 'death_assistance']:
        res = await db[col].delete_many({})
        print(f"  {col}: removed {res.deleted_count} documents")


# ── Step 2: Import members ────────────────────────────────────────────────────
async def import_members():
    """Read Members sheet from benefits.xlsx → insert 57 members."""
    print("\nImporting members...")
    xl = pd.ExcelFile(BENEFITS_FILE)
    df = xl.parse('Members')
    # Row 0 is pandas column headers (col names are the label row)
    # Actual data rows: index 1 onward  (index 0 is the header row we skipped)
    data_rows = df.iloc[1:].reset_index(drop=True)

    member_id_map    = {}   # row_number (1-57) → MongoDB _id string
    member_mobile_map = {}  # row_number        → mobile string

    for _, row in data_rows.iterrows():
        num    = row.iloc[0]
        name   = row.iloc[1]
        mobile = row.iloc[2]

        if pd.isna(num) or pd.isna(name):
            continue

        num    = int(float(str(num)))
        name   = str(name).strip().replace('⭐', '').strip()
        mobile = str(mobile).strip() if not pd.isna(mobile) else ''
        if mobile in ('nan', 'NaN'):
            mobile = ''

        member_id = f"TW-{num:03d}"
        doc = {
            "member_id":    member_id,
            "name":         name,
            "mobile":       mobile,
            "address":      "Wariyad",
            "joining_date": "2026-05-01",
            "status":       "active",
            "created_at":   now_iso(),
        }
        result = await db.members.insert_one(doc)
        mongo_id = str(result.inserted_id)
        member_id_map[num]     = mongo_id
        member_mobile_map[num] = mobile
        print(f"  TW-{num:03d}: {name} ({mobile or 'no mobile'})")

    print(f"\nMembers imported: {len(member_id_map)}")
    return member_id_map, member_mobile_map


# ── Step 3: Import cashbook ───────────────────────────────────────────────────
async def import_cashbook():
    """Read monthly cashbook sheets and insert entries.
    Adds an opening-balance credit entry first (₹51,765 as of 30-Apr-2026).
    """
    print("\nImporting cashbook entries...")
    xl = pd.ExcelFile(CASHBOOK_FILE)

    # Opening balance — must come first so running balance is correct
    OPENING_BALANCE = 51765.0
    await db.cashbook.insert_one({
        "entry_type":     "credit",
        "category":       "opening_balance",
        "description":    "Opening balance (carried forward before May 2026)",
        "amount":         OPENING_BALANCE,
        "date":           "2026-04-30",
        "reference_id":   None,
        "voucher_number": "VCH-OPENING",
        "recorded_by":    "migration",
        "created_at":     "2026-04-30T00:00:00+00:00",
    })
    print(f"  Opening balance: ₹{OPENING_BALANCE:,.0f}")

    count = 0
    for sheet_name in xl.sheet_names:
        if not sheet_name.startswith('Cashbook-'):
            continue

        df = xl.parse(sheet_name)
        # Row 0: title  |  Row 1: opening/closing balance row
        # Row 2: column headers  |  Row 3 onwards: data
        if len(df) < 4:
            continue

        for idx in range(3, len(df)):
            row = df.iloc[idx]
            sl_no       = row.iloc[0]
            date_val    = row.iloc[1]
            description = row.iloc[2]
            type_raw    = row.iloc[3]
            voucher_raw = row.iloc[4]
            receipt_raw = row.iloc[5]
            payment_raw = row.iloc[6]
            remarks_raw = row.iloc[8]

            # Skip empty or TOTALS rows
            if pd.isna(date_val) or pd.isna(description):
                continue
            if str(sl_no).strip().upper() in ('TOTALS', 'NAN', ''):
                continue

            receipt_val = float(receipt_raw) if not pd.isna(receipt_raw) else 0.0
            payment_val = float(payment_raw) if not pd.isna(payment_raw) else 0.0
            if receipt_val == 0 and payment_val == 0:
                continue

            # Date
            if isinstance(date_val, pd.Timestamp):
                date_str   = date_val.strftime('%Y-%m-%d')
                created_at = date_val.isoformat() + '+00:00'
            else:
                date_str   = str(date_val)[:10]
                created_at = date_str + 'T00:00:00+00:00'

            # Entry type & amount
            if receipt_val > 0:
                etype  = "credit"
                amount = receipt_val
            else:
                etype  = "debit"
                amount = payment_val

            # Category
            type_str = str(type_raw).strip() if not pd.isna(type_raw) else ''
            if 'contribution' in type_str.lower() or 'monthly' in type_str.lower():
                category = "contribution"
            elif 'benefit' in type_str.lower():
                category = "benefit"
            else:
                category = "other"

            # Voucher number
            if not pd.isna(voucher_raw):
                try:
                    voucher = f"VCH-{int(float(str(voucher_raw)))}"
                except (ValueError, TypeError):
                    voucher = f"VCH-AUTO-{count + 1}"
            else:
                voucher = f"VCH-AUTO-{count + 1}"

            # Description + remarks
            desc = str(description).strip()
            rem  = str(remarks_raw).strip() if not pd.isna(remarks_raw) else ''
            if rem and rem not in ('nan', 'NaN'):
                desc = f"{desc} — {rem}"

            await db.cashbook.insert_one({
                "entry_type":     etype,
                "category":       category,
                "description":    desc,
                "amount":         amount,
                "date":           date_str,
                "reference_id":   None,
                "voucher_number": voucher,
                "recorded_by":    "migration",
                "created_at":     created_at,
            })
            count += 1

    print(f"  Cashbook entries imported: {count}")


# ── Step 4: Import contributions ──────────────────────────────────────────────
async def import_contributions(member_id_map: dict):
    """Read each monthly contribution sheet and insert paid records."""
    print("\nImporting contributions...")
    xl = pd.ExcelFile(CONTRIBUTIONS_FILE)

    total         = 0
    receipt_count = 1

    for sheet_name, (month, year) in CONTRIB_MONTH_MAP.items():
        if sheet_name not in xl.sheet_names:
            continue

        df = xl.parse(sheet_name)
        # Row 0: org name  |  Row 1: month title  |  Row 2: column headers
        # Row 3 onwards: member data
        if len(df) < 4:
            continue

        month_total = 0
        for idx in range(3, len(df)):
            row  = df.iloc[idx]
            num  = row.iloc[0]   # Member number (1-57)
            paid = row.iloc[5]   # Paid This Month
            pm   = row.iloc[6]   # Payment Method

            # Skip summary/totals rows
            if pd.isna(num):
                continue
            num_str = str(num).strip().upper()
            if num_str in ('TOTALS', 'NAN', ''):
                continue

            try:
                num = int(float(num_str))
            except (ValueError, TypeError):
                continue

            paid_val = float(paid) if not pd.isna(paid) else 0.0
            if paid_val <= 0:
                continue   # Member did not pay this month

            mongo_mid = member_id_map.get(num)
            if not mongo_mid:
                print(f"  WARNING: No member for row #{num}")
                continue

            pm_str = str(pm).strip() if not pd.isna(pm) else 'Cash'
            if pm_str in ('nan', 'NaN', ''):
                pm_str = 'Cash'

            receipt_num = f"RCP-{year}-{receipt_count:04d}"
            receipt_count += 1
            paid_date   = f"{year}-{month:02d}-01T00:00:00+00:00"

            # Prevent duplicates
            existing = await db.contributions.find_one(
                {"member_id": mongo_mid, "month": month, "year": year}
            )
            if existing:
                continue

            await db.contributions.insert_one({
                "member_id":      mongo_mid,
                "month":          month,
                "year":           year,
                "amount":         paid_val,
                "payment_method": pm_str,
                "receipt_number": receipt_num,
                "recorded_by":    "migration",
                "paid_at":        paid_date,
            })
            total      += 1
            month_total += 1

        if month_total:
            print(f"  {sheet_name}: {month_total} paid contributions")

    print(f"  Total contributions imported: {total}")


# ── Step 5: Import benefits & medical aid ─────────────────────────────────────
async def import_benefits(member_id_map: dict, member_mobile_map: dict):
    """Parse Disbursement Register sheet and insert into benefits / medical_aid."""
    print("\nImporting benefits and medical aid...")
    xl = pd.ExcelFile(BENEFITS_FILE)
    df = xl.parse('Disbursement Register')

    # Row 0: big title row | Row 1: column headers | Row 2 onwards: data
    # Columns (iloc indices):
    #   0=Sl.No. | 1=Date | 2=Member No. | 3=Member Name | 4=Benefit Type
    #   5=Details | 6=Amount | 7=Payment Method | 8=Reference No.
    #   9=Approved By | 10=Remarks | 11=Status

    benefits_count = 0
    medical_count  = 0

    for idx in range(2, len(df)):
        row = df.iloc[idx]
        sl_no       = row.iloc[0]
        date_val    = row.iloc[1]
        member_num  = row.iloc[2]
        member_name = row.iloc[3]
        benefit_raw = row.iloc[4]
        details_raw = row.iloc[5]
        amount_raw  = row.iloc[6]
        payment_raw = row.iloc[7]
        ref_raw     = row.iloc[8]
        approved_by = row.iloc[9]
        remarks_raw = row.iloc[10]
        status_raw  = row.iloc[11]

        # Skip empty rows
        if pd.isna(sl_no) or pd.isna(date_val) or pd.isna(benefit_raw):
            continue
        try:
            int(float(str(sl_no)))
        except (ValueError, TypeError):
            continue

        # Date
        if isinstance(date_val, pd.Timestamp):
            date_str = date_val.strftime('%Y-%m-%d')
        else:
            date_str = str(date_val)[:10]

        # Member lookup
        try:
            mnum = int(float(str(member_num)))
        except (ValueError, TypeError):
            mnum = None
        mongo_mid = member_id_map.get(mnum)
        mobile    = member_mobile_map.get(mnum, '')

        amount_val   = float(amount_raw) if not pd.isna(amount_raw) else 0.0
        benefit_type = str(benefit_raw).strip() if not pd.isna(benefit_raw) else ''
        mname        = str(member_name).strip() if not pd.isna(member_name) else ''
        details      = str(details_raw).strip() if not pd.isna(details_raw) else ''
        status       = 'paid' if str(status_raw).strip().lower() == 'paid' else 'pending'
        approved     = str(approved_by).strip() if not pd.isna(approved_by) else 'Committee'
        remarks      = str(remarks_raw).strip() if not pd.isna(remarks_raw) else ''
        created_at   = f"{date_str}T00:00:00+00:00"
        now          = now_iso()

        if benefit_type == 'Medical Emergency Fund':
            doc = {
                "applicant_name":     mname,
                "contact":            mobile,
                "address":            "Wariyad",
                "medical_condition":  details,
                "hospital":           "General",
                "estimated_expense":  amount_val,
                "recommended_amount": amount_val,
                "notes":              details + (f" — {remarks}" if remarks and remarks != 'nan' else ''),
                "member_id":          mongo_mid,
                "status":             status,
                "applied_by":         "migration",
                "created_at":         created_at,
            }
            if status == 'paid':
                doc.update({"approved_by": approved, "approved_at": now,
                            "paid_by": "migration", "paid_at": now})
            await db.medical_aid.insert_one(doc)
            medical_count += 1
            print(f"  Medical aid: {mname} — ₹{amount_val:,.0f} ({status})")

        elif benefit_type == 'House Warming Gift':
            doc = {
                "member_id":    mongo_mid or '',
                "member_name":  mname,
                "benefit_type": "housewarming",
                "event_date":   date_str,
                "notes":        details,
                "amount":       amount_val,
                "status":       status,
                "applied_by":   "migration",
                "created_at":   created_at,
            }
            if status == 'paid':
                doc.update({"committee_approved_by": approved, "committee_approved_at": now,
                            "paid_by": "migration", "paid_at": now})
            await db.benefits.insert_one(doc)
            benefits_count += 1
            print(f"  Benefit (housewarming): {mname} — ₹{amount_val:,.0f} ({status})")

        elif benefit_type == 'Marriage Gift':
            doc = {
                "member_id":    mongo_mid or '',
                "member_name":  mname,
                "benefit_type": "marriage",
                "event_date":   date_str,
                "notes":        details,
                "amount":       amount_val,
                "status":       status,
                "applied_by":   "migration",
                "created_at":   created_at,
            }
            if status == 'paid':
                doc.update({"committee_approved_by": approved, "committee_approved_at": now,
                            "paid_by": "migration", "paid_at": now})
            await db.benefits.insert_one(doc)
            benefits_count += 1
            print(f"  Benefit (marriage): {mname} — ₹{amount_val:,.0f} ({status})")

        elif benefit_type == 'Demise Support':
            doc = {
                "deceased_name":   details or mname,
                "member_id":       mongo_mid,
                "family_details":  details,
                "address":         "Wariyad",
                "contact_person":  mname,
                "date_of_death":   date_str,
                "grocery_kit_value": amount_val,
                "status":          status,
                "created_by":      "migration",
                "created_at":      created_at,
            }
            await db.death_assistance.insert_one(doc)
            print(f"  Death assistance: {mname} — ₹{amount_val:,.0f} ({status})")

    print(f"  Medical aid records: {medical_count}")
    print(f"  Benefit records:     {benefits_count}")


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    print("=" * 60)
    print("Twenty20 Wariyad — Data Migration")
    print("=" * 60)

    await clear_data()
    member_id_map, member_mobile_map = await import_members()
    await import_cashbook()
    await import_contributions(member_id_map)
    await import_benefits(member_id_map, member_mobile_map)

    print("\n" + "=" * 60)
    print("Migration complete — verification:")
    print(f"  Members:       {await db.members.count_documents({})}")
    print(f"  Contributions: {await db.contributions.count_documents({})}")
    print(f"  Cashbook:      {await db.cashbook.count_documents({})}")
    print(f"  Benefits:      {await db.benefits.count_documents({})}")
    print(f"  Medical Aid:   {await db.medical_aid.count_documents({})}")
    print("=" * 60)

    client.close()

if __name__ == '__main__':
    asyncio.run(main())
