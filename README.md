# 🤖 Telegram Course Bot

ربات تلگرامی هوشمند برای ارائه دوره‌های آموزشی با پنل ادمین پیشرفته

## ✨ امکانات

### برای کاربران:
- ✅ ثبت‌نام با فیلدهای قابل تنظیم
- 📚 دریافت درس‌های آموزشی (ویدیو/صوت/متن)
- ✔️ سیستم تایید دیدن درس
- 🔔 یادآوری خودکار برای کاربران غیرفعال
- 🎯 پیشرفت شخصی‌سازی شده

### برای ادمین:
- 👥 مدیریت کامل کاربران
- 📝 مدیریت درس‌ها (CRUD)
- 🎨 تنظیم فیلدهای ثبت‌نام بدون کد نویسی
- 📊 آمار و گزارش‌گیری پیشرفته
- 📤 اکسپورت Excel
- 📢 ارسال پیام عمومی با rate limiting
- 💬 ارسال پیام خصوصی به کاربران
- 🔗 تنظیم وبهوک قابل شخصی‌سازی
- 🏷️ سیستم تگ‌گذاری و کمپین

## 🛠️ تکنولوژی‌ها

- **Python 3.11+**
- **aiogram 3.x** - فریمورک async تلگرام
- **PostgreSQL** - دیتابیس قدرتمند
- **SQLAlchemy 2.0** - ORM
- **Redis** - کش و rate limiting
- **APScheduler** - زمان‌بندی وظایف
- **Docker** - کانتینریزیشن

## 📦 نصب و راه‌اندازی

### پیش‌نیازها:
```bash
Python 3.11+
PostgreSQL 15+
Redis (اختیاری)
```

### مراحل نصب:

1. **کلون پروژه:**
```bash
git clone https://github.com/YOUR_USERNAME/telegram-course-bot.git
cd telegram-course-bot
```

2. **ایجاد محیط مجازی:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
```

3. **نصب پکیج‌ها:**
```bash
pip install -r requirements.txt
```

4. **تنظیم environment:**
```bash
cp .env.example .env
# ویرایش .env و اضافه کردن توکن ربات و اطلاعات دیتابیس
```

5. **مایگریشن دیتابیس:**
```bash
alembic upgrade head
```

6. **اجرای ربات:**
```bash
python bot.py
```

## 🐳 اجرا با Docker

```bash
docker-compose up -d
```

## ⚙️ تنظیمات

فایل `.env` را ویرایش کنید:

```env
# Telegram Bot
BOT_TOKEN=your_bot_token_here
ADMIN_USER_IDS=123456789,987654321

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=course_bot
DB_USER=postgres
DB_PASSWORD=your_password

# Redis (optional)
REDIS_HOST=localhost
REDIS_PORT=6379

# Webhook (optional)
WEBHOOK_URL=https://your-domain.com
WEBHOOK_PATH=/webhook
```

## 📖 استفاده

### اولین ادمین:
1. ربات را اجرا کنید
2. User ID تلگرام خود را در `.env` قرار دهید
3. `/start` را در ربات بزنید
4. به پنل ادمین دسترسی پیدا می‌کنید

### اضافه کردن درس:
1. پنل ادمین > مدیریت درس‌ها
2. افزودن درس جدید
3. آپلود فایل یا متن
4. تنظیم ترتیب و فعال‌سازی

## 📁 ساختار پروژه

```
telegram-course-bot/
├── bot.py              # فایل اصلی
├── config.py           # تنظیمات
├── database/           # مدل‌ها و دیتابیس
├── handlers/           # هندلرهای ربات
├── services/           # لایه منطق
├── utils/              # توابع کمکی
└── tasks/              # وظایف زمان‌بندی
```

## 🤝 مشارکت

برای مشارکت در پروژه:
1. Fork کنید
2. یک branch جدید بسازید
3. تغییرات خود را commit کنید
4. Push کنید
5. Pull Request بزنید

## 📄 لایسنس

MIT License

## 💬 پشتیبانی

برای سوالات و پشتیبانی، یک Issue باز کنید.

---

ساخته شده با ❤️ برای آموزش بهتر
