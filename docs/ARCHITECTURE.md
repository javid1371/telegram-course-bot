# 🏗️ معماری پروژه - Telegram Course Bot

## نمای کلی

این پروژه از معماری **لایه‌بندی شده (Layered Architecture)** استفاده می‌کند که شامل سه لایه اصلی است:

```
┌─────────────────────────────────────────┐
│            Handlers (Presentation)       │  ← ورودی تلگرام
├─────────────────────────────────────────┤
│            Services (Business Logic)     │  ← منطق تجاری
├─────────────────────────────────────────┤
│            Database (Data Access)        │  ← دسترسی داده
└─────────────────────────────────────────┘
```

## ساختار دایرکتوری

```
telegram-course-bot/
├── bot.py                  # نقطه ورود اصلی
├── config.py               # مدیریت تنظیمات از .env
│
├── database/
│   ├── __init__.py          # Engine, Session, Base, init_db()
│   ├── models.py            # مدل‌های SQLAlchemy (10 مدل)
│   └── migrations/          # مایگریشن‌های Alembic
│
├── handlers/
│   ├── __init__.py
│   ├── registration.py      # ثبت‌نام کاربر با FSM
│   ├── user.py              # تعاملات کاربر (درس، پیشرفت)
│   └── admin.py             # پنل ادمین کامل
│
├── services/
│   ├── __init__.py
│   ├── user_service.py      # سرویس مدیریت کاربران
│   ├── lesson_service.py    # سرویس مدیریت درس‌ها
│   ├── webhook_service.py   # سرویس وبهوک
│   ├── broadcast_service.py # سرویس ارسال پیام عمومی
│   ├── analytics_service.py # سرویس آمار و گزارش
│   ├── export_service.py    # سرویس اکسپورت Excel
│   └── reminder_service.py  # سرویس یادآوری
│
├── tasks/
│   └── scheduler.py         # زمان‌بندی وظایف (APScheduler)
│
├── utils/
│   ├── decorators.py        # دکوریتورهای دسترسی و لاگ
│   ├── helpers.py           # توابع کمکی متنوع
│   ├── keyboards.py         # کیبوردهای تلگرامی
│   └── validators.py        # اعتبارسنجی ورودی‌ها
│
├── docs/                    # مستندات پروژه
├── docker-compose.yml       # داکر کامپوز
├── Dockerfile               # داکرفایل
├── requirements.txt         # وابستگی‌ها
└── alembic.ini              # تنظیمات مایگریشن
```

## مدل‌های دیتابیس

### دیاگرام ارتباطات

```
Admin
  └── (standalone, admin user IDs)

User ─────────────┐
  │                │
  ├── UserProgress ├── Lesson
  │   (many-to-many with progress tracking)
  │
  ├── BroadcastLog
  │
  └── Campaign (via registration_data)

RegistrationField (dynamic form fields)

WebhookSetting (outgoing webhooks)

ScheduledMessage → User

DailyStat (aggregated analytics)
```

### مدل‌ها

| مدل | توضیح |
|-----|-------|
| `Admin` | اطلاعات ادمین‌ها |
| `User` | کاربران ثبت‌نامی + registration_data (JSON) |
| `Lesson` | درس‌ها با پشتیبانی text/video/audio/document/photo |
| `UserProgress` | پیشرفت کاربر در هر درس + زمان صرف شده |
| `RegistrationField` | فیلدهای ثبت‌نام داینامیک |
| `WebhookSetting` | تنظیمات وبهوک خروجی |
| `Campaign` | کمپین‌های ترکینگ |
| `ScheduledMessage` | پیام‌های زمان‌بندی شده |
| `BroadcastLog` | لاگ ارسال پیام عمومی |
| `DailyStat` | آمار روزانه aggregated |

## جریان داده‌ها

### ثبت‌نام کاربر
```
/start → registration.py
  ├── بدون فیلد ثبت‌نام → ذخیره مستقیم → خوش‌آمدگویی
  └── با فیلدهای ثبت‌نام → FSM flow:
       ├── نمایش فیلد اول
       ├── دریافت پاسخ + اعتبارسنجی
       ├── فیلد بعدی... (تکرار)
       └── ذخیره همه داده‌ها → وبهوک → خوش‌آمدگویی
```

### ارائه درس
```
"📚 ادامه دوره" → user.py
  ├── get_next_lesson_for_user()
  ├── نمایش درس (با توجه به content_type)
  ├── کاربر تایید می‌کند → mark_lesson_completed()
  ├── بررسی تکمیل دوره
  └── وبهوک (lesson_completed / course_completed)
```

### پنل ادمین
```
/admin → admin.py
  ├── 📊 داشبورد (آمار کلی)
  ├── 📚 درس‌ها (CRUD + آمار)
  ├── 👥 کاربران (لیست/جستجو/مدیریت)
  ├── 📢 ارسال پیام (broadcast)
  ├── 📝 فیلدهای ثبت‌نام
  ├── 📈 گزارش‌ها
  ├── 🔗 وبهوک
  └── ⚙️ تنظیمات
```

## تکنولوژی‌ها

| تکنولوژی | نسخه | کاربرد |
|-----------|-------|--------|
| Python | 3.11+ | زبان اصلی |
| aiogram | 3.x | فریمورک تلگرام (async) |
| PostgreSQL | 15+ | دیتابیس اصلی |
| SQLAlchemy | 2.0 | ORM |
| asyncpg | - | درایور async برای PostgreSQL |
| APScheduler | - | زمان‌بندی وظایف |
| Redis | اختیاری | کشینگ (Phase 4) |
| Docker | - | Containerization |
| pandas + openpyxl | - | اکسپورت Excel |
| aiohttp | - | ارسال وبهوک |

## الگوهای طراحی

1. **Service Layer Pattern**: جداسازی منطق تجاری از هندلرها
2. **Repository Pattern**: دسترسی به داده از طریق سرویس‌ها
3. **FSM (Finite State Machine)**: مدیریت state ثبت‌نام و عملیات ادمین
4. **Decorator Pattern**: کنترل دسترسی (`@admin_only`, `@registered_only`)
5. **Builder Pattern**: ساخت کیبوردها با `InlineKeyboardBuilder`
6. **Async/Await**: معماری غیرهمزمان در تمام لایه‌ها
