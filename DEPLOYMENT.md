# 🚀 راهنمای استقرار روی سرور

این راهنما برای استقرار ربات روی سرور Ubuntu/Debian است.

## 📋 پیش‌نیازها

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y git python3.11 python3-pip python3-venv postgresql postgresql-contrib redis-server
```

## 1️⃣ نصب PostgreSQL

```bash
# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE course_bot;
CREATE USER bot_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE course_bot TO bot_user;
ALTER DATABASE course_bot OWNER TO bot_user;
\q
EOF
```

## 2️⃣ کلون پروژه

```bash
# Clone repository
cd /opt
sudo git clone https://github.com/YOUR_USERNAME/telegram-course-bot.git
cd telegram-course-bot

# Set permissions
sudo chown -R $USER:$USER /opt/telegram-course-bot
```

## 3️⃣ تنظیم محیط

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## 4️⃣ تنظیم Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env file
nano .env
```

**تنظیمات ضروری:**
```env
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_USER_IDS=123456789,987654321

DB_HOST=localhost
DB_PORT=5432
DB_NAME=course_bot
DB_USER=bot_user
DB_PASSWORD=your_secure_password

REDIS_HOST=localhost
LOG_LEVEL=INFO
```

## 5️⃣ مایگریشن دیتابیس

```bash
# Run migrations
alembic upgrade head
```

## 6️⃣ تست اجرا

```bash
# Test run
python bot.py
```

اگر همه چیز درست بود، ربات باید شروع به کار کند.

## 7️⃣ استقرار با Systemd (Production)

ایجاد فایل سرویس:

```bash
sudo nano /etc/systemd/system/telegram-course-bot.service
```

محتوای فایل:

```ini
[Unit]
Description=Telegram Course Bot
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/opt/telegram-course-bot
Environment="PATH=/opt/telegram-course-bot/venv/bin"
ExecStart=/opt/telegram-course-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

فعال‌سازی سرویس:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable telegram-course-bot

# Start service
sudo systemctl start telegram-course-bot

# Check status
sudo systemctl status telegram-course-bot

# View logs
sudo journalctl -u telegram-course-bot -f
```

## 🐳 استقرار با Docker (پیشنهادی)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create .env file
cp .env.example .env
nano .env

# Start containers
docker-compose up -d

# Check logs
docker-compose logs -f bot

# Stop containers
docker-compose down
```

## 📊 مدیریت

### مشاهده لاگ‌ها
```bash
# Systemd
sudo journalctl -u telegram-course-bot -f

# Docker
docker-compose logs -f bot

# File
tail -f bot.log
```

### ریستارت ربات
```bash
# Systemd
sudo systemctl restart telegram-course-bot

# Docker
docker-compose restart bot
```

### بروزرسانی کد
```bash
# Pull latest changes
git pull

# Systemd
sudo systemctl restart telegram-course-bot

# Docker
docker-compose down
docker-compose up -d --build
```

### مایگریشن دیتابیس
```bash
# Activate venv
source venv/bin/activate

# Run migrations
alembic upgrade head

# Restart bot
sudo systemctl restart telegram-course-bot
```

### پشتیبان‌گیری از دیتابیس
```bash
# Backup
pg_dump -U bot_user -d course_bot > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
psql -U bot_user -d course_bot < backup_20240209.sql
```

## 🔒 امنیت

1. **Firewall:**
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

2. **SSL/TLS** (اگر از webhook استفاده می‌کنید):
```bash
# Install Certbot
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d your-domain.com
```

3. **محافظت از .env:**
```bash
chmod 600 .env
```

## 🔧 عیب‌یابی

### ربات start نمی‌شود
```bash
# Check logs
sudo journalctl -u telegram-course-bot -n 50

# Check database connection
telnet localhost 5432

# Check Redis
redis-cli ping
```

### خطای دیتابیس
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check database exists
sudo -u postgres psql -l | grep course_bot
```

### خطای permission
```bash
# Fix ownership
sudo chown -R YOUR_USERNAME:YOUR_USERNAME /opt/telegram-course-bot

# Fix Python path
which python
```

## 📈 مانیتورینگ

### نصب htop
```bash
sudo apt install htop
htop
```

### بررسی استفاده از منابع
```bash
# CPU and Memory
docker stats

# Disk usage
df -h

# Database size
sudo -u postgres psql -d course_bot -c "SELECT pg_size_pretty(pg_database_size('course_bot'));"
```

## 🎯 مراحل بعدی

1. افزودن ادمین اول از طریق دستور `/start`
2. راه‌اندازی پنل ادمین با `/admin`
3. افزودن درس‌های اولیه
4. تنظیم فیلدهای ثبت‌نام
5. تست کامل با یک کاربر آزمایشی

---

## 🔄 استقرار سینک بین‌پلتفرمی (تلگرام ↔ بله)

اگر می‌خواهید ربات روی هر دو پلتفرم (تلگرام و بله) اجرا شود و پیشرفت کاربران بین آن‌ها سینک شود:

### معماری
```
سرور ۱ (بین‌الملل)              سرور ۲ (ایران)
┌──────────────────┐         ┌──────────────────┐
│  Telegram Bot     │ ←────→ │  Bale Bot         │
│  PLATFORM=telegram│  sync  │  PLATFORM=bale    │
│  :8080/api/sync   │         │  :8080/api/sync   │
└──────────────────┘         └──────────────────┘
```

### پیش‌نیاز
- دو سرور مجزا (یکی برای تلگرام، یکی برای بله)
- هر سرور Docker + PostgreSQL + Redis خودش را دارد
- پورت `8080` وب (FastAPI) بین دو سرور باز باشد

### تنظیم `.env` سرور تلگرام
```env
PLATFORM=telegram
BOT_TOKEN=your_telegram_bot_token

# Sync — point to the Bale server's web API
SYNC_PEER_URL=http://BALE_SERVER_IP:8080/api/sync
SYNC_SECRET=a_shared_secret_between_servers

# Show Bale bot link to Telegram users
CROSS_PLATFORM_BOT_LINK=https://ble.ir/your_bale_bot
CROSS_PLATFORM_BOT_NAME=بله
```

### تنظیم `.env` سرور بله
```env
PLATFORM=bale
BOT_TOKEN=your_bale_bot_token

# Sync — point to the Telegram server's web API
SYNC_PEER_URL=http://TELEGRAM_SERVER_IP:8080/api/sync
SYNC_SECRET=a_shared_secret_between_servers

# Show Telegram bot link to Bale users
CROSS_PLATFORM_BOT_LINK=https://t.me/your_telegram_bot
CROSS_PLATFORM_BOT_NAME=تلگرام
```

### مایگریشن
قبل از اجرا، مایگریشن جداول سینک را اعمال کنید:
```bash
alembic upgrade head
```

### نحوه کار سینک
1. **ثبت ایونت**: وقتی کاربر درسی تکمیل/کوئیز پاس/فرم ثبت می‌کند → ایونت در `sync_events` ذخیره می‌شود
2. **Push فوری**: سیستم فوراً تلاش می‌کند ایونت را به سرور peer بفرستد
3. **Retry خودکار**: اگر push شکست بخورد → ایونت `pending` می‌ماند → scheduler هر ۳۰ ثانیه retry می‌کند
4. **Shadow Profile**: سرور peer ایونت دریافتی را در `sync_user_snapshots` ذخیره می‌کند
5. **بازیابی پیشرفت**: وقتی کاربر در پلتفرم دوم `/start` می‌زند → اگر شماره تلفنش با یک snapshot مطابقت داشت → پیشرفت خودکار بازیابی می‌شود

### مانیتورینگ
- از پنل ادمین ربات: دکمه **🔄 سینک پلتفرم**
- API endpoint: `GET /api/sync/events/stats`
- API endpoint: `GET /api/sync/snapshots`

### عیب‌یابی
```bash
# بررسی ایونت‌های معلق
docker exec -it <bot_container> python -c "
import asyncio
from database import init_db, async_session_maker
from database.models import SyncEvent
from sqlalchemy import select, func

async def check():
    await init_db()
    async with async_session_maker() as s:
        for st in ('pending', 'synced', 'failed', 'skipped'):
            c = (await s.execute(select(func.count(SyncEvent.id)).where(SyncEvent.status == st))).scalar()
            print(f'{st}: {c}')

asyncio.run(check())
"
```

## 💡 نکات

- همیشه قبل از بروزرسانی، backup بگیرید
- لاگ‌ها را به صورت منظم بررسی کنید
- از `.env` برای تنظیمات محرمانه استفاده کنید
- توکن ربات را هرگز commit نکنید
- برای production استفاده از Docker پیشنهاد می‌شود
