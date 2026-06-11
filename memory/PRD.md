# Twenty20 Charity Group Wariyad — PRD

## Organization
Twenty Twenty Charity Group Wariyad

## Problem Statement
Build a complete Charity & Membership Management Platform that digitizes member management, monthly contribution collection, benefit disbursement, medical aid requests, death benefit tracking, financial accounting, committee administration, meeting management, annual auditing, and reports.

## Architecture
- **Frontend**: React (CRA + Craco), Tailwind CSS, Shadcn UI, Phosphor Icons, Recharts
- **Backend**: FastAPI (Python), motor (async MongoDB)
- **Database**: MongoDB (`twenty20_wariyad`)
- **Auth**: JWT via httpOnly cookies, bcrypt password hashing
- **Hosting**: Kubernetes (preview env)

## User Personas
1. **Super Admin** - Full system control
2. **President** - View all, approve payments
3. **Secretary** - Manage members, meetings, benefit processing
4. **Treasurer** - Record contributions, manage cashbook, approve payments
5. **Committee Member** - Review & vote on requests
6. **Auditor** - Read-only financial access
7. **Member** - View own profile, contributions, apply for benefits

## Core Requirements (Static)
- JWT authentication with role-based access (7 roles)
- Member registration with auto-generated member IDs (TW-001)
- Monthly contribution tracking with receipt generation
- Marriage (₹5,000) and Housewarming (₹3,000) benefit workflows
- Medical aid application & approval workflow
- Death assistance tracking
- Cashbook with running balance, voucher numbers (VCH-YYYY-NNNN)
- Committee management by year
- Meeting scheduling and minutes recording
- Dashboard with role-based stats and charts
- Reports (member, contribution, benefits)
- User management with role assignment

## What's Been Implemented (2026-06, Iteration 2 update)

### New Features Added
- ✅ Bulk member import — CSV & Excel (.csv/.xlsx/.xls) with template download
  - POST /api/members/import
  - GET /api/members/import-template (CSV template download)
  - Frontend: drag-and-drop file upload dialog, shows import results
- ✅ PDF receipt download — GET /api/contributions/{id}/receipt
  - fpdf2-generated A4 PDF with header, member details, amount box
  - Download button next to all paid contributions
- ✅ Demo data seeding — POST /api/demo/seed (admin only)
  - 15 realistic member profiles with Indian names
  - 4 months of contribution history
  - Sample marriage benefit (committee_approved) and medical aid (approved)
- ✅ Load Demo Data button in Members page (super_admin only)
- ✅ Fixed FastAPI route ordering bug: /members/import-template must precede /members/{mid}

### Test Data Status
- 23 total members (15 demo + 3 CSV import test + manual)
- 60+ cashbook entries
- Fund balance: ~₹7,800
- 1 pending marriage benefit (Mohammed Ashraf — committee_approved, needs treasurer to mark paid)
- 1 medical aid approved (Basheer Ibrahim Demo)



### Backend (server.py)
- ✅ JWT auth (login, logout, me, register)
- ✅ Users CRUD + role management
- ✅ Members CRUD (auto-generated TW-XXX IDs)
- ✅ Contributions (monthly tracking, receipt numbers RCP-YYYY-NNNN)
- ✅ Contribution status API (month/year grid view)
- ✅ Benefits (marriage/housewarming) with full workflow
- ✅ Medical Aid applications and approval workflow
- ✅ Death Assistance tracking
- ✅ Cashbook with auto running balance + voucher numbers
- ✅ Auto cashbook entries on contribution record and benefit payment
- ✅ Committee management
- ✅ Meeting management (schedule, minutes, resolutions)
- ✅ Dashboard stats API
- ✅ Monthly collections chart API
- ✅ Reports (members, contributions by year, benefits summary)
- ✅ Admin seeding on startup + test_credentials.md auto-written

### Frontend
- ✅ Login page (Kerala tropical background)
- ✅ Role-based sidebar navigation
- ✅ Dashboard with stat cards and bar chart
- ✅ Members list/table with search, filter, add/edit
- ✅ Contributions monthly tracker with payment recording
- ✅ Benefits with full approval workflow buttons
- ✅ Medical Aid with status updates
- ✅ Death Assistance case management
- ✅ Cashbook/Financials with credit/debit entries
- ✅ Committee formation with position management
- ✅ Meetings scheduling and minutes recording
- ✅ Reports with charts (member pie, contribution bar, benefits breakdown)
- ✅ User Management

## Test Results (Iteration 1)
- Backend: 100% (31/31 tests passed)
- Frontend: 95% - all pages load, login/logout works, add member works

## Prioritized Backlog

### P0 (Critical — already done)
- Member management ✅
- Contribution tracking ✅
- Dashboard ✅
- Auth ✅

### P1 (Important — already done)
- Benefits management ✅
- Medical Aid ✅
- Death Assistance ✅
- Cashbook ✅
- Committee ✅
- Meetings ✅
- Reports ✅
- User Management ✅

### P2 (Future Enhancements)
- PDF receipt generation for contributions
- Bulk contribution upload (CSV)
- SMS/WhatsApp/Email notifications (defer Phase 2)
- Mobile app
- QR Code Member Card
- UPI Payment Integration
- WhatsApp Bot
- E-signatures / Online Voting
- Audit trail log
- Annual audit module with auditor approval
- Member self-service portal (contribute online)
- Public charity portal

## Next Tasks
1. PDF receipt download for contributions
2. Bulk member import from CSV/Excel
3. Notification system (SMS/WhatsApp via Twilio)
4. Audit module (auditor role read-only views + audit report)
5. Member self-portal (member can see own contributions and apply for benefits)
