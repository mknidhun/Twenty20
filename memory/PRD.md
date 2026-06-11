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
6. **Auditor** - Read-only financial access + annual audit sign-off
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
- Reports (member, contribution, benefits) with Excel/PDF export
- Notifications (SMS/WhatsApp reminders for defaulters via Twilio)
- Annual Audit module (read-only trail + digital sign-off by auditor)
- User management with role assignment

## What's Been Implemented

### Phase 1 — Core MVP (Completed)
- ✅ JWT auth (login, logout, me, register)
- ✅ Users CRUD + role management (7 roles)
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
- ✅ Dashboard stats API + monthly collections chart
- ✅ Reports (members, contributions by year, benefits summary)
- ✅ Bulk member import — CSV & Excel (.csv/.xlsx/.xls)
- ✅ PDF receipt download — GET /api/contributions/{id}/receipt
- ✅ Demo data seeder (15 members, 4 months contributions)
- ✅ Admin seeding on startup

### Phase 2 — Completed (2026-06)
- ✅ Export Reports to Excel — GET /api/reports/export/excel?year=YYYY
  - 4 sheets: Contributions, Benefits, Cashbook, Members
- ✅ Export Reports to PDF — GET /api/reports/export/pdf?year=YYYY
  - Annual summary + monthly contribution table
- ✅ Twilio Notifications — SMS & WhatsApp reminders for contribution defaulters
  - GET /api/notifications/defaulters?month=M&year=YYYY
  - POST /api/notifications/send-reminders (graceful mock mode when Twilio not configured)
  - Logs notification attempts in `notification_logs` collection
- ✅ Annual Audit Module
  - GET /api/audit/report?year=YYYY (financial summary, read-only)
  - POST /api/audit/sign-off (Auditor role ONLY — one per auditor per year)
  - GET /api/audit/sign-offs (all roles can view)
  - Stored in `audit_sign_offs` collection

### P1 Features — Completed (2026-06)
- ✅ QR Code Member Card — GET /api/members/{mid}/qr-card
  - PDF wallet card with member name, ID, mobile + QR code (plain text for offline verification)
  - Download button in every Members row
- ✅ Meeting Minutes & Resolutions Enhancement
  - Structured resolutions_list: [{text, status: passed|failed|tabled}]
  - GET /api/meetings/{mid}/minutes-pdf — PDF export of full meeting minutes + resolutions
  - MinutesDialog updated with Add/Remove resolution items and status dropdown
  - PDF button per meeting row
- ✅ Committee Handover Records
  - POST /api/committee/handovers — record handover with full asset checklist
  - GET /api/committee/handovers — list all handovers
  - Documents checklist (8 items) + Registers checklist (6 items)
  - Fund balance at handover, outstanding items, notes
  - Stored in `committee_handovers` collection

### Frontend Pages
- ✅ Login, Dashboard, Members, Contributions, Benefits, Medical Aid, Death Assistance
- ✅ Cashbook/Financials, Committee, Meetings, Reports
- ✅ User Management
- ✅ Notifications (new — Phase 2)
- ✅ Audit (new — Phase 2)

## Key API Endpoints
- POST `/api/auth/login`
- GET/POST `/api/members`
- GET `/api/members/import-template`
- POST `/api/members/import`
- GET/POST `/api/contributions`
- GET `/api/contributions/{cid}/receipt`
- GET `/api/reports/export/excel?year=YYYY`
- GET `/api/reports/export/pdf?year=YYYY`
- GET `/api/notifications/defaulters?month=M&year=YYYY`
- POST `/api/notifications/send-reminders`
- GET `/api/audit/report?year=YYYY`
- POST `/api/audit/sign-off` (auditor only)
- GET `/api/audit/sign-offs`

## DB Collections
- users, members, contributions, benefits, medical_aid, death_assistance
- cashbook, committees, meetings
- notification_logs (new Phase 2)
- audit_sign_offs (new Phase 2)

## Environment Variables (backend/.env)
- MONGO_URL, DB_NAME, JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_URL
- TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_PHONE, TWILIO_WHATSAPP_FROM (optional — mock mode when absent)

## Prioritized Backlog

### P1 — All Completed
- QR Code Member Card (DONE)
- Meeting Minutes & Resolutions enhancement (DONE)
- Committee Handover records (DONE)
- UPI Payment Integration (skipped by user — revisit when needed)

### P2 (Future)
- Mobile App integration
- WhatsApp Bot
- E-signatures / Online Voting
- Public Charity Portal
- Donation Gateway
- Volunteer Management
- CSR Sponsorship Tracking
- Member self-service portal (online contributions)

## Test Results
- Iteration 1: Backend 100% (31/31), Frontend 95%
- Iteration 2: Backend 100%, Frontend 100%
- Iteration 3 (Phase 2): Backend 100% (16/16), Frontend 100%

## Route Ordering Note
When adding new backend routes, ALWAYS place literal paths BEFORE parameterized routes.
Example: `/reports/export/excel` must precede `/reports/contributions/{year}`.
