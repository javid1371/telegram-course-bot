# استقرار بات بله روی سرور ایرانی

## معماری دو-پلتفرمه

```
┌─────────────────────────────────┐     ┌─────────────────────────────────┐
│   سرور بین‌المللی (193.x.x.x)  │     │      سرور ایرانی (IR)           │
│                                  │     │                                  │
│  ┌──────────┐  ┌──────────┐     │     │  ┌──────────┐  ┌──────────┐     │
│  │ Telegram  │  │PostgreSQL│     │     │  │   Bale   │  │PostgreSQL│     │
│  │   Bot     │  │   DB     │     │     │  │   Bot    │  │   DB     │     │
│  └──────────┘  └──────────┘     │     │  └──────────┘  └──────────┘     │
│  ┌──────────┐                    │     │  ┌──────────┐                    │
│  │  Redis   │                    │     │  │  Redis   │                    │
│  └──────────┘                    │     │  └──────────┘                    │
│                                  │     │                                  │
│  PLATFORM=telegram               │     │  PLATFORM=bale                   │
└─────────────────────────────────┘     └─────────────────────────────────┘

           هر سرور کاملاً مستقل — حتی با قطعی اینترنت بین‌المللی
           بات بله در ایران بدون وقفه کار می‌کند
```

## پیش‌نیازها

1. **سرور ایرانی** (VPS یا دیکیتد) با:
   - Ubuntu 22.04+ یا Debian 12+
   - Docker + Docker Compose
   - حداقل 1GB RAM, 10GB disk
   - IP ایرانی (بله فقط از داخل ایران سرویس می‌دهد)

2. **توکن بات بله** از `@botfather` در پیام‌رسان بله

3. **دسترسی SSH** به سرور ایرانی

## مراحل استقرار

### ۱. آماده‌سازی سرور

```bash
# نصب Docker (اگر نصب نیست)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# نصب Docker Compose
sudo apt install docker-compose-plugin

# ساخت دایرکتوری پروژه
mkdir -p /opt/bale-course-bot
cd /opt/bale-course-bot
```

### ۲. انتقال کد

```bash
# از سیستم لوکال:
rsync -avz --exclude '__pycache__' --exclude '.git' --exclude 'logs' \
    /path/to/telegram-course-bot/ \
    root@IR_SERVER_IP:/opt/bale-course-bot/
```

### ۳. تنظیم فایل محیطی

```bash
cd /opt/bale-course-bot
cp .env.bale.example .env

# ویرایش .env
nano .env
```

مقادیر مهم:
```env
PLATFORM=bale
BOT_TOKEN=توکن_بات_بله_شما
BOT_USERNAME=نام_بات_بله
ADMIN_USER_IDS=شناسه_ادمین_در_بله
DB_PASSWORD=یک_رمز_قوی
```

> ⚠️ **نکته مهم**: شناسه کاربری (User ID) در بله با تلگرام **متفاوت** است.
> باید ID ادمین را در بله پیدا کنید.

### ۴. راه‌اندازی

```bash
# ساخت و اجرا
docker-compose -f docker-compose.bale.yml up -d --build

# بررسی لاگ‌ها
docker-compose -f docker-compose.bale.yml logs -f bot

# باید ببینید:
# 🚀 Starting Course Bot on بله...
# ✅ Database initialized successfully
# ✅ Bot started successfully
```

### ۵. اعمال مایگریشن دیتابیس

```bash
# ایجاد دیتابیس و کاربر
docker-compose -f docker-compose.bale.yml exec -T postgres \
    psql -U postgres -c "
        CREATE USER bot_user WITH PASSWORD 'رمز_شما';
        GRANT ALL PRIVILEGES ON DATABASE course_bot TO bot_user;
    "

# اعمال تمام مایگریشن‌ها (شامل جداول پایه + پلتفرم)
docker-compose -f docker-compose.bale.yml exec bot \
    python -c "
import asyncio
from database import init_db
asyncio.run(init_db())
print('DB initialized')
"
```

### ۶. تنظیم دوره‌ها

دوره‌ها و درس‌ها باید در بات بله هم تعریف شوند.
دو روش:

**روش الف: دستی از پنل ادمین**
- در بله به بات پیام دهید و `/admin` بزنید

**روش ب: کپی از دیتابیس تلگرام (پیشنهادی)**
```bash
# در سرور تلگرام: خروجی گرفتن
docker-compose exec -T postgres pg_dump -U bot_user -d course_bot \
    --table=courses --table=lessons --table=registration_fields \
    --data-only --inserts > /tmp/course_data.sql

# انتقال به سرور ایرانی
scp /tmp/course_data.sql root@IR_SERVER:/tmp/

# در سرور ایرانی: وارد کردن
docker-compose -f docker-compose.bale.yml exec -T postgres \
    psql -U bot_user -d course_bot < /tmp/course_data.sql
```

> ⚠️ **نکته**: فیلد `file_id` درس‌ها فقط در تلگرام معتبر است.
> اولین باری که هر درس در بله ارسال شود، باید فایل‌ها مجدداً آپلود شوند.

## انتقال کاربران (Migration)

وقتی اینترنت بین‌المللی قطع شود و بخواهید کاربران تلگرام را به بله منتقل کنید:

### برای کاربر:
1. در **تلگرام** (وقتی هنوز دسترسی هست): `/migrate` → کد ۸ کاراکتری دریافت می‌کند
2. در **بله**: `/migrate XXXXXXXX` → پیشرفت منتقل می‌شود

### اگر اینترنت قبلاً قطع شده:
- کد migration فقط روی سرور مبدأ ذخیره می‌شود
- اگر دو دیتابیس مجزا هستند، کد در سرور بله وجود ندارد
- **راه‌حل**: قبل از قطعی، sync خودکار انجام شود (بخش بعد)

## همگام‌سازی خودکار (Sync)

برای اینکه اطلاعات بین دو سرور sync باشد **وقتی اینترنت وصل است**:

### اگر از n8n استفاده می‌کنید (پیشنهادی):
هر دو بات event‌ها را به n8n ارسال می‌کنند. n8n می‌تواند:
- لیست کاربران هر دو پلتفرم را یکجا ببیند
- وقتی کاربر جدید در تلگرام ثبت‌نام کرد، یک pre-migration code آماده کند
- داده دوره‌ها را بین دو سرور sync کند

### Webhook event format:
```json
{
    "event_id": "uuid",
    "platform": "bale",
    "source": "bale_bot@bale",
    "event": { "type": "lead", "action": "register" },
    "user": {
        "telegram_id": 123456,
        "platform": "bale",
        ...
    }
}
```

فیلد `platform` در تمام event‌ها وجود دارد و n8n می‌تواند بر اساس آن فیلتر کند.

## آپدیت کد

```bash
# از سیستم لوکال:
rsync -avz --exclude '__pycache__' --exclude '.git' --exclude '.env' \
    /path/to/telegram-course-bot/ \
    root@IR_SERVER_IP:/opt/bale-course-bot/

# در سرور ایرانی:
cd /opt/bale-course-bot
docker-compose -f docker-compose.bale.yml up -d --build bot
```

## عیب‌یابی

| مشکل | راه‌حل |
|------|--------|
| بات پاسخ نمی‌دهد | `docker logs bale_bot_app` را بررسی کنید |
| خطای API | مطمئن شوید توکن بله درست است (نه تلگرام) |
| فایل‌ها ارسال نمی‌شوند | `file_id` تلگرام در بله کار نمی‌کند — فایل‌ها باید مجدد آپلود شوند |
| فرمت پیام خراب | بله فقط Markdown پشتیبانی می‌کند — `PlatformBot` خودکار تبدیل می‌کند |
| ادمین شناسایی نمی‌شود | مطمئن شوید `ADMIN_USER_IDS` شناسه بله است (نه تلگرام) |

## تفاوت‌های بله با تلگرام

| موضوع | تلگرام | بله |
|--------|--------|-----|
| API URL | api.telegram.org | tapi.bale.ai |
| Parse Mode | HTML / MarkdownV2 | فقط Markdown |
| Webhook Ports | 443, 80, 88, 8443 | 443, 88 |
| file_id | مختص تلگرام | مختص بله |
| User ID | منحصربفرد تلگرام | منحصربفرد بله |
| Inline Query | ✅ | ❌ |
| پرداخت | ندارد | کیف‌پول بله |
