# n8n Workflows: Course Bot → Didar CRM Integration

## Overview

This directory contains n8n workflow JSON files that integrate the Telegram/Bale Course Bot
with **Didar CRM** using the **native `n8n-nodes-didar-crm` community nodes** (v0.0.36+).

When users interact with the bot (register, complete lessons, submit forms, take quizzes),
events are sent via webhooks to n8n, which then creates/updates records in Didar CRM through
the native Didar CRM nodes — providing proper credential management, dropdown selectors,
and built-in error handling.

### Events Handled

| Event | Action in Didar CRM |
|---|---|
| `lead.register` | Find/Create Person (dedup) + Find/Create Deal (dedup) + Happy Call Activity + **Returns assigned owner** |
| `lesson.complete` | Search Deal → Update stage (پایان درس ۱-۸) |
| `form.submit` | Find Person → Update custom fields (income, staff, job, etc.) |
| `quiz.pass` | Create Note with score |
| `quiz.fail` | Create Note with failure details |
| `inactivity.timeout` | Create Follow-up Activity for sales team |
| `course.complete` | Search Deal → Move to "در انتظار تماس فروش" + Sales Call Activity |
| `speed.change` | Create Note tracking engagement level |

### Key Features (v3)
- **Native Didar CRM Nodes**: Uses `n8n-nodes-didar-crm` instead of HTTP Request nodes
- **Centralized Credentials**: API key managed via n8n's credential system (not in workflow)
- **Weighted Owner Assignment**: Config defines OWNERS array with weights; each registration randomly selects an owner proportional to weight
- **Person Deduplication**: Searches by phone before creating — uses existing person if found
- **Deal Deduplication**: Searches for existing open deal before creating a new one
- **Webhook Response**: Register branch returns assigned owner info to the bot (lastNode mode)
- **Auto Stage Movement**: Deal stage updates automatically with lesson progress
- **Custom Field Mapping**: Form responses → CRM custom fields
- **Complete Branches**: All 8 event types have full action chains

### Node Statistics
- **40 total nodes**: 14 native Didar CRM + 22 Code/Logic + 2 Respond + 2 other (Webhook, Switch)

---

## Prerequisites

1. **n8n** running (self-hosted or cloud)
2. **n8n-nodes-didar-crm** v0.0.36+ installed (`npm install n8n-nodes-didar-crm` in `~/.n8n/nodes/`)
3. **Didar CRM** account with API key
4. **Course Bot** running with webhook support enabled

---

## Setup Instructions

### Step 1: Create Didar API Credentials

Before importing the workflow, create the credentials in n8n:

1. Open n8n dashboard
2. Go to **Credentials** → **Add Credential**
3. Search for **Didar API**
4. Fill in:
   - **Base URL**: `https://app.didar.me`
   - **API Key**: Your Didar CRM API key
   - **Use Cookie Header**: Enable only if required by your instance
5. Click **Test** to verify connectivity, then **Save**

### Step 2: Import Workflow

1. Go to **Workflows** → **Add Workflow** → **Import from File**
2. Select `course-bot-didar-crm.json`
3. n8n will show credential warnings — this is normal

### Step 3: Assign Credentials

After import, open each **Didar CRM** node (14 nodes) and select your "Didar API" credential:
- Find Person, Create Person, Search Deal Reg, Create Deal, Happy Call (register branch)
- Search Deal, Update Deal Stage (lesson branch)
- Find Person Form, Update Person Fields (form branch)
- Create Note (shared by quiz/speed branches)
- Create Followup (inactivity branch)
- Search Deal Complete, Update Deal Complete, Sales Call (complete branch)

### Step 4: Configure the Config Node

Open the **Config** Code node and fill in ALL placeholder GUIDs:

#### Required Configuration

| Setting | Description | How to Find |
|---|---|---|
| `WEBHOOK_SECRET` | Shared secret for HMAC validation | Same as `WEBHOOK_SECRET` in bot's `.env` |
| `OWNERS` | Array of `{id, name, weight}` for sales reps | Didar API: `POST /api/user/getall` |
| `PIPELINE_ID` | GUID of "دوره خروج از بحران" pipeline | Didar API: `POST /api/pipeline/getall` |
| `COMPANY_ID` | Default company GUID (or leave zeros) | Didar → Companies |
| `ACTIVITY_TYPE_SALES` | GUID for "مذاکره فروش" activity type | Didar API: `POST /api/supplementary/getbaseinfo` |
| `ACTIVITY_TYPE_FOLLOWUP` | GUID for follow-up activity type | Same as above |

**OWNERS Array Format:**
```js
const OWNERS = [
  { id: 'guid-owner-1', name: 'Ali', weight: 3 },
  { id: 'guid-owner-2', name: 'Sara', weight: 2 },
  { id: 'guid-owner-3', name: 'Reza', weight: 1 },
];
```
Higher weight = more leads assigned. Weighted random selection is done in the Prep Register node.

> **Note**: `DIDAR_API_KEY` is no longer in the Config node — it's managed via n8n credentials.
> **Note**: `OWNER_ID` was replaced by `OWNERS` array in v3 for weighted round-robin assignment.

#### Stage GUIDs

Fill in the GUID for each pipeline stage:

| Config Key | Stage Name (Persian) |
|---|---|
| `STAGES.register` | ثبت نام اولیه |
| `STAGES.lesson_1` | پایان درس ۱ |
| `STAGES.lesson_2` | پایان درس ۲ |
| `STAGES.lesson_3` | پایان درس ۳ |
| `STAGES.lesson_4` | پایان درس ۴ |
| `STAGES.lesson_5` | پایان درس ۵ |
| `STAGES.lesson_6` | پایان درس ۶ |
| `STAGES.lesson_7` | پایان درس ۷ |
| `STAGES.lesson_8` | پایان درس ۸ |
| `STAGES.sales_wait` | در انتظار تماس فروش |
| `STAGES.followup_1` | پیگیری اول |
| `STAGES.followup_2` | پیگیری دوم |
| `STAGES.followup_3` | پیگیری سوم |

#### Custom Field GUIDs

| Config Key | Field Name (Persian) |
|---|---|
| `CUSTOM_FIELDS.monthly_income` | میانگین درآمد ماهانه |
| `CUSTOM_FIELDS.staff_count` | تعداد پرسنل |
| `CUSTOM_FIELDS.job` | شغل مشتری |
| `CUSTOM_FIELDS.best_call_time` | بهترین زمان برای تماس |
| `CUSTOM_FIELDS.lead_score` | امتیاز لید |
| `CUSTOM_FIELDS.city` | شهر |
| `CUSTOM_FIELDS.income_class` | طبقه بندی درآمد |

### Step 5: Finding GUIDs via Didar API

Use curl or the **Didar CRM** → **Supplementary** → **Get Base Information** node in n8n:

```bash
# Get all pipelines (find Pipeline ID and Stage IDs)
curl -X POST "https://app.didar.me/api/pipeline/getall?apikey=YOUR_KEY" \
  -H "Content-Type: application/json" -d '{}'

# Get base info (Activity Types, Custom Fields, etc.)
curl -X POST "https://app.didar.me/api/supplementary/getbaseinfo?apikey=YOUR_KEY" \
  -H "Content-Type: application/json" -d '{}'

# Get all users (find Owner IDs for OWNERS array)
curl -X POST "https://app.didar.me/api/user/getall?apikey=YOUR_KEY" \
  -H "Content-Type: application/json" -d '{}'
```

💡 **Tip**: You can also use the native Didar CRM node's **Supplementary → Get Base Information**
operation directly in n8n to explore pipelines, stages, activity types, and custom fields interactively.

### Step 6: Activate the Workflow

1. Toggle the workflow to **Active** in n8n
2. Note the webhook URL shown on the Webhook node (e.g., `https://your-n8n.com/webhook/course-bot`)

### Step 7: Register Webhook in Bot

Connect to the bot's database and register the webhook:

```sql
-- Connect to the bot's PostgreSQL database
INSERT INTO webhook_settings (url, secret, events, is_active, created_at)
VALUES (
    'https://irn8n.javidmgdm.com/webhook/course-bot',
    'YOUR_WEBHOOK_SECRET_HERE',
    '["lead.register","lesson.complete","form.submit","quiz.pass","quiz.fail","inactivity.timeout","course.complete","speed.change"]',
    true,
    NOW()
);
```

Or set via environment variables in the bot's `.env`:
```
WEBHOOK_URL=https://irn8n.javidmgdm.com/webhook/course-bot
WEBHOOK_SECRET=YOUR_WEBHOOK_SECRET_HERE
```

### Step 8: Test

1. Send `/start` to the bot
2. Register and complete some lessons
3. Check n8n execution log for successful runs
4. Verify records appear in Didar CRM

---

## Architecture

```
Bot (Telegram/Bale)
  │
  ▼ (webhook POST with HMAC, responseMode=lastNode)
n8n Webhook ─→ Config (Code) ─→ Router (Switch on action)
                                    │
  ┌─────────────┬──────────┬────────┼───────────┬────────────┬──────────────┬──────────┐
  │             │          │        │           │            │              │          │
  ▼             ▼          ▼        ▼           ▼            ▼              ▼          ▼
Register     Lesson    Form      Quiz Pass   Quiz Fail   Inactivity   Course Done  Speed
  │          Complete  Submit       │           │            │              │        Change
  ▼             ▼          ▼        ▼           ▼            ▼              ▼          │
[Code]       [Code]     [Code]   [Code]      [Code]       [Code]        [Code]       │
Prep+Owner   Prep       Prep     Prep        Prep         Prep          Prep         │
Assign         │          │       │            │            │              │          │
  │            ▼          ▼       └──────┬─────┘            ▼              ▼          │
  ▼          🔶 Search  🔶 Find       ▼               🔶 Create     🔶 Search       │
🔶 Find      Deal       Person   🔶 Create Note       Followup      Deal           │
Person       (search)   (getByPh.)  (note/create)    (activity)    (search)         │
(getByPhone)   │          │                                            │             │
  │            ▼          ▼                                            ▼             │
[Code]       [Code]     [Code]                                       [Code]          │
Process      Extract    Extract                                      Extract         │
Person       Deal       Person                                       Deal            │
  │            │          │                                            │             │
  ▼            ▼          ▼                                            ▼             │
⟐ IF Person 🔶 Update  🔶 Update                                   🔶 Update       │
Exists?      Deal       Person                                       Deal            │
  │╲           (update)   (update)                                     (update)        │
  │  ╲                                                                   │             │
  ▼    ▼                                                                 ▼             ▼
Use  🔶Create                                                       🔶 Sales     🔶 Create
Exist Person                                                         Call         Note
  │    │                                                             (activity)   (note)
  │    ▼
  │  [Code] Get New Person ID
  │    │
  └──┬─┘
     ▼
🔶 Search Deal (deal/search) ── person dedup complete
     │
  [Code] Process Deal
     │
  ⟐ IF Deal Exists?
     │╲
     │  ╲
     ▼    ▼
  Skip  🔶 Create Deal (deal/create)
     │    │
     │  [Code] After Create Deal
     │    │
     └──┬─┘
        ▼
  🔶 Happy Call (activity/create)
        │
  [Code] Prep Response (owner info)
        │
  ◀ Respond Register ── returns {owner.id, owner.name} to bot

All other branches end with:
  [Code] Prep Respond OK → ◀ Respond OK

🔶 = Native Didar CRM Node (n8n-nodes-didar-crm)
[Code] = JavaScript Code Node
⟐ = IF Node (conditional branch)
◀ = Respond to Webhook Node
```

---

## Native Didar CRM Node Operations Used

| Node | Resource | Operation | Purpose |
|---|---|---|---|
| Find Person | person | getByPhone | Look up contact by phone (register dedup) |
| Create Person | person | create | Create new CRM contact (if not exists) |
| Update Person Fields | person | update | Update custom fields from form data |
| Create Deal | deal | create | Create deal in pipeline (register + form) |
| Search Deal Reg | deal | search | Search for existing deal (register dedup) |
| Search Deal Lesson | deal | search | Find deal for stage update (lesson) |
| Search Deal Complete | deal | search | Find deal for completion (course done) |
| Update Deal Stage | deal | update | Move deal to next pipeline stage |
| Update Deal Complete | deal | update | Mark deal as completed stage |
| Happy Call | activity | create | Welcome call activity (register) |
| Create Followup | activity | create | Follow-up for inactive users |
| Sales Call | activity | create | Sales call when course completed |
| Create Note Quiz | note | create | Record quiz pass/fail results |
| Create Note Speed | note | create | Record speed changes |

---

## Troubleshooting

### Credentials error on Didar CRM nodes
- Open each Didar CRM node and select your "Didar API" credential
- Click **Test** in the credential editor to verify API key validity
- If using cookie auth, enable "Use Cookie Header" and set the cookie value

### Webhook not receiving events
- Check bot logs for webhook delivery errors
- Verify webhook URL is accessible from bot server
- Check `WEBHOOK_SECRET` matches between bot and n8n Config node

### Person not found in Didar
- Ensure phone numbers match format (with/without country code)
- The workflow handles missing persons gracefully (creates new ones on register)

### Deal stage not updating
- Verify Pipeline ID and Stage GUIDs are correct in Config node
- Check that the deal exists and is in "Pending" status
- Use the native Didar CRM **Deal → Search** to verify deals exist

### n8n execution failing
- Check n8n execution log for error details
- Verify Didar API credentials are valid (test button)
- Check that all 14 Didar CRM nodes have credentials assigned
- For custom fields, ensure Field GUIDs match your Didar CRM instance

### Dropdown selectors empty
- Ensure credential test passes
- Your API user must have permission to view entities
- Try switching to "Enter ID manually" mode and paste GUIDs directly

---

## Files

| File | Description |
|---|---|
| `course-bot-didar-crm.json` | Main CRM integration workflow (v3 - smart owner + dedup) |
| `generate_workflow.py` | Python script to regenerate the workflow JSON |
| `README.md` | This documentation |

---

## Changelog

### v3 (Current)
- **Weighted owner assignment**: `OWNERS` array with weights for smart round-robin lead distribution
- **Person deduplication**: Find Person (getByPhone) + IF exists → reuse, else create new
- **Deal deduplication**: Search Deal + IF exists → skip, else create new
- **Webhook response**: Register branch returns `{owner.id, owner.name}` to bot via Respond to Webhook
- **responseMode=lastNode**: n8n holds HTTP response until workflow completes (all branches)
- 40 total nodes (14 Didar CRM + 22 Code/Logic + 2 Respond + 2 base)

### v2
- **Migrated from HTTP Request to native `n8n-nodes-didar-crm` nodes** (13 native nodes)
- Added credential-based API key management (no more API key in Config node)
- **Fixed**: lesson.complete now actually updates the deal stage (was missing in v1)
- **Fixed**: form.submit now finds the person and updates custom fields (was incomplete in v1)
- **Fixed**: course.complete now searches deal, updates stage, and creates sales activity (was incomplete in v1)
- 29 total nodes (13 Didar CRM + 14 Code + 2 base)

### v1
- Initial workflow with HTTP Request nodes
- 21 nodes, some branches were incomplete
