# n8n Workflows: Course Bot → Didar CRM Integration

## Overview

This directory contains n8n workflow JSON files that integrate the Telegram/Bale Course Bot
with **Didar CRM**. When users interact with the bot (register, complete lessons, submit forms,
take quizzes), events are sent via webhooks to n8n, which then creates/updates records in Didar CRM.

### Events Handled

| Event | Action in Didar CRM |
|---|---|
| `lead.register` | Create Person + Deal (stage: ثبت نام اولیه) + Happy Call Activity |
| `lesson.complete` | Update Deal stage (پایان درس ۱-۸) + Note with progress |
| `form.submit` | Update Person custom fields (income, staff, job, etc.) |
| `quiz.pass` | Create Note with score + Update lead score |
| `quiz.fail` | Create Note with failure details |
| `inactivity.timeout` | Create Follow-up Activity for sales team |
| `course.complete` | Move Deal to "در انتظار تماس فروش" + Sales Call Activity |
| `speed.change` | Create Note tracking engagement level |

### Additional Features
- **Lead Scoring**: Automatic score calculation based on user engagement
- **Auto Stage Movement**: Deal stage updates automatically with lesson progress
- **Hot Lead Detection**: Fast-track and high-engagement users flagged
- **Custom Field Mapping**: Form responses → CRM custom fields

---

## Prerequisites

1. **n8n** running (self-hosted or cloud)
2. **n8n-nodes-didar-crm** package installed (`npm install n8n-nodes-didar-crm` in n8n custom nodes dir)
3. **Didar CRM** account with API key
4. **Course Bot** running with webhook support enabled

---

## Setup Instructions

### Step 1: Import Workflow

1. Open n8n dashboard
2. Go to **Workflows** → **Add Workflow** → **Import from File**
3. Select `course-bot-didar-crm.json`

### Step 2: Configure the Workflow

Open the **🔧 Config & Validate** Code node and fill in ALL placeholder values:

#### Required Configuration

| Setting | Description | How to Find |
|---|---|---|
| `DIDAR_API_KEY` | Your Didar CRM API key | Didar → Settings → API |
| `WEBHOOK_SECRET` | Shared secret for HMAC validation | Same as `WEBHOOK_SECRET` in bot's `.env` |
| `OWNER_ID` | GUID of CRM user/sales rep | Didar API: `GET /api/user/getall` |
| `PIPELINE_ID` | GUID of "دوره خروج از بحران" pipeline | Didar API: `GET /api/pipeline/getall` |
| `COMPANY_ID` | Default company GUID (or leave zeros) | Didar → Companies |
| `ACTIVITY_TYPE_SALES` | GUID for "مذاکره فروش" activity type | Didar API: `GET /api/supplementary/getbaseinfo` |
| `ACTIVITY_TYPE_FOLLOWUP` | GUID for follow-up activity type | Same as above |

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

### Step 3: Finding GUIDs via Didar API

You can use curl or n8n HTTP Request node to find GUIDs:

```bash
# Get all pipelines (find Pipeline ID and Stage IDs)
curl -X POST "https://app.didar.me/api/pipeline/getall?apikey=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'

# Get base info (Activity Types, Custom Fields, etc.)
curl -X POST "https://app.didar.me/api/supplementary/getbaseinfo?apikey=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'

# Get all users (find Owner ID)
curl -X POST "https://app.didar.me/api/user/getall?apikey=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Step 4: Activate the Workflow

1. Toggle the workflow to **Active** in n8n
2. Note the webhook URL shown on the Webhook node (e.g., `https://your-n8n.com/webhook/course-bot`)

### Step 5: Register Webhook in Bot

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

### Step 6: Test

1. Send `/start` to the bot
2. Register and complete some lessons
3. Check n8n execution log for successful runs
4. Verify records appear in Didar CRM

---

## Architecture

```
Bot (Telegram/Bale)
  │
  ▼ (webhook POST)
n8n Webhook ─→ Config & Validate ─→ Find Person by Phone ─→ Process Result ─→ Event Router
                                                                                    │
  ┌──────────────────────────────────────────────────────────────────────────────────┤
  │              │              │            │             │            │             │
  ▼              ▼              ▼            ▼             ▼            ▼             ▼
Register    Lesson Complete  Form Submit  Quiz Result  Inactivity  Course Done   Speed Change
  │              │              │            │             │            │             │
  ▼              ▼              ▼            ▼             ▼            ▼             ▼
Create       Search Deal    Update       Create        Create      Search Deal    Create
Person       → Update Stage Person       Note          Follow-up   → Update Stage Note
→ Create     → Create Note  (Custom                   Activity    → Create Sales
  Deal                       Fields)                                 Activity
→ Happy Call                                                       → Create Note
  Activity
```

---

## Didar CRM API Endpoints Used

| Endpoint | Purpose |
|---|---|
| `POST /api/contact/getbyphonenumber` | Find person by phone |
| `POST /api/contact/save` | Create/Update person |
| `POST /api/deal/save_v2` | Create/Update deal |
| `POST /api/deal/search_v2` | Search deals |
| `POST /api/activity/save` | Create activity, note, or follow-up |

---

## Troubleshooting

### Webhook not receiving events
- Check bot logs for webhook delivery errors
- Verify webhook URL is accessible from bot server
- Check `WEBHOOK_SECRET` matches between bot and n8n

### Person not found in Didar
- Ensure phone numbers match format (with/without country code)
- The workflow handles missing persons gracefully (creates new ones on register)

### Deal stage not updating
- Verify Pipeline ID and Stage GUIDs are correct
- Check that the deal exists and is in "Open" status

### n8n execution failing
- Check n8n execution log for error details
- Verify Didar API key is valid
- Test API calls manually with curl

---

## Files

| File | Description |
|---|---|
| `course-bot-didar-crm.json` | Main CRM integration workflow |
| `README.md` | This documentation |
