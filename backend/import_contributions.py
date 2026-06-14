"""Importer — load T20_Monthly_Contributions List.xlsx into the ledger tables.

Reads each monthly sheet, creates Members with their opening balance (from the
FIRST sheet's Prior Pending/Advance columns) and intro rate (⭐ rows = new
members on the intro rate), then records each month's 'Paid This Month' as a
Payment + MonthlyDues paid figure. Skips the TOTALS summary row.

Usage (from backend/, with DATABASE_URL set the same as the app):
    python import_contributions.py "/path/to/T20_Monthly_Contributions List.xlsx"
"""
import sys, asyncio, openpyxl
from datetime import datetime, timezone
from sqlalchemy import select
from db import async_session_maker, init_db
from models import Member, OrgSettings, MonthlyDues, Payment

MONTHS = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}


def parse_ym(sheet_title):
    mon, yr = sheet_title.split()
    return int(yr), MONTHS[mon]


async def run(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    month_sheets = [s for s in wb.sheetnames if s != "Summary"]
    if not month_sheets:
        print("No monthly sheets found."); return
    first_y, first_m = parse_ym(month_sheets[0])

    # Pre-scan: detect inactive members — those whose Balance freezes (stops
    # changing) and stays constant through the last sheet. Records the month their
    # balance first goes flat-to-end as inactive_from.
    by_name_bal = {}
    for sheet in month_sheets:
        ws = wb[sheet]; yy, mm = parse_ym(sheet)
        for r in range(5, ws.max_row + 1):
            nm = ws.cell(r, 2).value
            if not nm:
                continue
            nm = str(nm).strip()
            if nm.upper().startswith("TOTAL"):
                continue
            bal = ws.cell(r, 8).value
            by_name_bal.setdefault(nm, []).append(((yy, mm), None if bal is None else int(bal)))
    inactive_from = {}
    for nm, seq_ in by_name_bal.items():
        seqv = [(k, v) for k, v in seq_ if v is not None]
        for i in range(1, len(seqv)):
            (k, v) = seqv[i]; (_, pv) = seqv[i - 1]
            if v == pv and all(bb == v for (_, bb) in seqv[i:]):
                inactive_from[nm] = k   # (year, month) it froze
                break

    await init_db()
    async with async_session_maker() as session:
        # settings (defaults; intro 200 / standard 100 / 12 months)
        s = (await session.execute(select(OrgSettings).limit(1))).scalar_one_or_none()
        if not s:
            s = OrgSettings(); session.add(s); await session.commit()

        # --- members from the first sheet (defines opening balance + intro/star) ---
        ws0 = wb[month_sheets[0]]
        members_by_name = {}
        seq = 0
        for r in range(5, ws0.max_row + 1):
            name = ws0.cell(r, 2).value
            if not name:
                continue
            name = str(name).strip()
            if name.upper().startswith("TOTAL"):
                continue
            is_star = "⭐" in name
            clean = name.replace("⭐", "").strip()
            pend = ws0.cell(r, 3).value or 0
            adv = ws0.cell(r, 4).value or 0
            rate = int(ws0.cell(r, 5).value or 100)
            opening = int(adv) - int(pend)          # + advance / − pending
            seq += 1
            mid = f"TW-{seq:03d}"
            inact = inactive_from.get(name)
            m = Member(
                member_id=mid, name=clean, mobile="", address="",
                joining_date=(f"{first_y}-{first_m:02d}-01" if is_star else "2024-01-01"),
                status="active",   # frozen members stay counted; dues stop via inactive_from
                intro_rate=(rate if is_star else None),
                opening_balance=opening,
                ledger_start=f"{first_y}-{first_m:02d}",
                inactive_from=(f"{inact[0]}-{inact[1]:02d}" if inact else None),
            )
            session.add(m)
            members_by_name[name] = m
        await session.commit()
        for m in members_by_name.values():
            await session.refresh(m)

        # --- per month: record Paid as MonthlyDues.paid + a Payment ---
        pay_count = dues_count = 0
        for sheet in month_sheets:
            ws = wb[sheet]; yy, mm = parse_ym(sheet)
            for r in range(5, ws.max_row + 1):
                name = ws.cell(r, 2).value
                if not name:
                    continue
                name = str(name).strip()
                if name.upper().startswith("TOTAL") or name not in members_by_name:
                    continue
                m = members_by_name[name]
                rate = int(ws.cell(r, 5).value or 0)
                # inactive from this month onward → no dues accrue
                inact = inactive_from.get(name)
                if inact and (yy * 12 + mm) >= (inact[0] * 12 + inact[1]):
                    rate = 0
                paid = int(ws.cell(r, 6).value or 0)
                method = (ws.cell(r, 7).value or "cash")
                method = str(method).strip().lower() or "cash"
                # dues row for the month
                session.add(MonthlyDues(member_id=m.id, year=yy, month=mm, rate=rate, paid=paid,
                                        status=("up_to_date" if paid >= rate else "pending")))
                dues_count += 1
                if paid > 0:
                    session.add(Payment(member_id=m.id, amount=paid, payment_method=method,
                                        year=yy, month=mm,
                                        receipt_number=f"IMP-{yy}-{mm:02d}-{m.member_id}",
                                        allocation=[{"year": yy, "month": mm, "amount": paid, "kind": "current"}]))
                    pay_count += 1
            await session.commit()

        print(f"Imported {len(members_by_name)} members, {dues_count} monthly dues rows, {pay_count} payments.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "T20_Monthly_Contributions List.xlsx"
    asyncio.run(run(path))
