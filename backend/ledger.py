"""Contribution ledger engine — pure functions, no DB.

Models the org's running per-member, per-month ledger exactly like the
T20_Monthly_Contributions workbook:

  Balance(month) = Prior Advance − Prior Pending − Rate(month) + Paid(month)
                 = running, where  running += Paid − Rate  each month

Rules:
  * New members pay an intro rate for their first `intro_months` months,
    then the standard rate.
  * A payment clears OLDEST arrears first; any leftover becomes advance.
  * Status is derived from the running balance, in whole-month units of the
    *current* month's rate (matches the sheet's "N Months Pending/Advance").
"""
from dataclasses import dataclass, field
from typing import Optional


def month_index(year: int, month: int) -> int:
    """Absolute month number, so differences are easy. Jan = month 1."""
    return year * 12 + (month - 1)


def resolve_rate(member_join_year: int, member_join_month: int,
                 year: int, month: int, *,
                 standard_rate: int, intro_rate: int, intro_months: int,
                 member_intro_rate: Optional[int] = None) -> int:
    """Rate due for `member` in (year, month).

    First `intro_months` months from join → intro rate (per-member override if set);
    afterwards → standard rate. Months before join → 0 (not a member yet)."""
    delta = month_index(year, month) - month_index(member_join_year, member_join_month)
    if delta < 0:
        return 0
    if delta < intro_months:
        return member_intro_rate if member_intro_rate is not None else intro_rate
    return standard_rate


@dataclass
class MonthRow:
    year: int
    month: int
    prior_pending: int      # arrears carried INTO this month (positive number)
    prior_advance: int      # credit carried INTO this month (positive number)
    rate: int               # dues for this month
    paid: int               # total paid toward this month-cycle
    balance: int            # running balance AFTER this month (− = owes, + = credit)
    status: str             # human label


def _status(balance: int, rate: int) -> str:
    if balance == 0 or rate == 0:
        return "Up to Date" if balance >= 0 else _pending_label(balance, rate)
    if balance > 0:
        n = round(balance / rate) if rate else 0
        if n <= 0:
            return "Up to Date"
        return f"{n} Month{'s' if n != 1 else ''} Advance Paid"
    return _pending_label(balance, rate)


def _pending_label(balance: int, rate: int) -> str:
    n = round(-balance / rate) if rate else 0
    if n <= 0:
        return "Up to Date"
    return f"{n} Month{'s' if n != 1 else ''} Pending"


def build_ledger(join_year: int, join_month: int,
                 payments_by_month: dict,           # {(year,month): paid_amount}
                 *, standard_rate: int, intro_rate: int, intro_months: int,
                 member_intro_rate: Optional[int] = None,
                 through_year: int, through_month: int,
                 opening_balance: int = 0,
                 inactive_from: Optional[tuple] = None,
                 start_year: Optional[int] = None,
                 start_month: Optional[int] = None) -> list:
    """Walk months from the ledger START to (through_year, through_month) and
    produce the running ledger.

    Distinguish two dates:
      * join_year/join_month — when the member JOINED (drives intro-rate timing).
      * start_year/start_month — where the app's ledger view BEGINS; the
        `opening_balance` is the balance carried INTO this start month. Defaults
        to the join month (i.e. the member is new and we have full history).

    `opening_balance`: − = pending, + = advance, for history that predates the
    app's records. Intro rate still keys off the real join date, so an existing
    member whose join is long past correctly pays the standard rate."""
    rows = []
    running = opening_balance  # + advance, − pending, seeded with opening balance
    start = month_index(start_year if start_year else join_year,
                        start_month if start_month else join_month)
    end = month_index(through_year, through_month)
    inactive_idx = month_index(*inactive_from) if inactive_from else None
    for idx in range(start, end + 1):
        y, m = divmod(idx, 12)
        m += 1
        # Inactive members stop accruing dues from their inactive month onward.
        if inactive_idx is not None and idx >= inactive_idx:
            rate = 0
        else:
            rate = resolve_rate(join_year, join_month, y, m,
                                standard_rate=standard_rate, intro_rate=intro_rate,
                                intro_months=intro_months, member_intro_rate=member_intro_rate)
        prior_pending = max(0, -running)
        prior_advance = max(0, running)
        paid = int(payments_by_month.get((y, m), 0))
        running = running - rate + paid
        rows.append(MonthRow(
            year=y, month=m, prior_pending=prior_pending, prior_advance=prior_advance,
            rate=rate, paid=paid, balance=running, status=_status(running, rate)))
    return rows


@dataclass
class Allocation:
    """Result of applying one payment, oldest-arrears-first."""
    applied_to_arrears: int = 0
    applied_to_current: int = 0
    advance: int = 0
    detail: list = field(default_factory=list)   # [(year, month, amount)]


def allocate_payment(amount: int, prior_balance: int, current_rate: int,
                     arrears_months: list) -> Allocation:
    """Split a payment. `prior_balance` < 0 means arrears exist.
    `arrears_months` = oldest-first list of (year, month, owed_for_that_month).
    Returns how the amount is consumed: oldest arrears → current month → advance."""
    alloc = Allocation()
    remaining = amount
    # 1) oldest arrears first
    for (y, m, owed) in arrears_months:
        if remaining <= 0:
            break
        pay = min(remaining, owed)
        if pay > 0:
            alloc.applied_to_arrears += pay
            alloc.detail.append((y, m, pay))
            remaining -= pay
    # 2) current month
    if remaining > 0 and current_rate > 0:
        pay = min(remaining, current_rate)
        alloc.applied_to_current = pay
        remaining -= pay
    # 3) leftover → advance
    if remaining > 0:
        alloc.advance = remaining
    return alloc
