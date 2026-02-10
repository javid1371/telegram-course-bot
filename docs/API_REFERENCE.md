# 🔌 مستندات API سرویس‌ها

## UserService

```python
from services.user_service import UserService

async with async_session_maker() as session:
    service = UserService(session)
```

| متد | توضیح |
|-----|-------|
| `get_user_by_telegram_id(tid)` | دریافت کاربر با آیدی تلگرام |
| `get_user_by_id(user_id)` | دریافت کاربر با آیدی دیتابیس |
| `create_user(telegram_user_id, ...)` | ایجاد کاربر جدید |
| `update_user(user_id, **kwargs)` | بروزرسانی اطلاعات |
| `delete_user(user_id)` | حذف کاربر |
| `get_all_users(is_active, is_completed, offset, limit)` | لیست + تعداد کل |
| `search_users(query)` | جستجو (نام، یوزرنیم، آیدی) |
| `block_user(user_id)` / `unblock_user(user_id)` | بلاک/آنبلاک |
| `add_tag(user_id, tag)` / `remove_tag(user_id, tag)` | مدیریت تگ |
| `get_user_stats(user_id)` | آمار کامل کاربر |
| `get_active_registration_fields()` | فیلدهای ثبت‌نام فعال |
| `reset_user_progress(user_id)` | ریست پیشرفت درس‌ها |

## LessonService

```python
from services.lesson_service import LessonService

async with async_session_maker() as session:
    service = LessonService(session)
```

| متد | توضیح |
|-----|-------|
| `create_lesson(title, content_type, ...)` | ایجاد درس جدید |
| `get_lesson_by_id(lesson_id)` | دریافت درس |
| `get_all_lessons(active_only)` | لیست همه درس‌ها |
| `update_lesson(lesson_id, **kwargs)` | بروزرسانی درس |
| `delete_lesson(lesson_id)` | حذف درس |
| `toggle_lesson(lesson_id)` | فعال/غیرفعال |
| `get_next_lesson_for_user(user_id)` | درس بعدی برای کاربر |
| `mark_lesson_started(user_id, lesson_id)` | شروع درس |
| `mark_lesson_completed(user_id, lesson_id)` | تکمیل درس |
| `get_user_progress(user_id)` | پیشرفت کاربر |
| `get_lesson_stats(lesson_id)` | آمار درس (started, completed, rate) |
| `reorder_lessons(lesson_ids)` | تغییر ترتیب درس‌ها |

## WebhookService

```python
from services.webhook_service import WebhookService

async with async_session_maker() as session:
    service = WebhookService(session)
```

| متد | توضیح |
|-----|-------|
| `create_webhook(name, url, ...)` | ایجاد وبهوک |
| `get_all_webhooks()` | لیست همه وبهوک‌ها |
| `get_active_webhooks()` | فقط فعال‌ها |
| `delete_webhook(webhook_id)` | حذف وبهوک |
| `send_webhook(webhook, event, data)` | ارسال با retry |
| `send_all_active_webhooks(event, data)` | ارسال به همه |
| `test_webhook(webhook_id)` | تست وبهوک |

رویدادهای پشتیبانی شده:
- `user_registered` - ثبت‌نام کاربر جدید
- `lesson_completed` - تکمیل درس
- `course_completed` - تکمیل دوره

## BroadcastService

```python
from services.broadcast_service import BroadcastService

async with async_session_maker() as session:
    service = BroadcastService(session)
```

| متد | توضیح |
|-----|-------|
| `broadcast_message(bot, text, target, tag)` | ارسال عمومی |
| `send_private_message(bot, user_id, text)` | پیام خصوصی |
| `get_broadcast_history(limit)` | تاریخچه ارسال |

پارامتر `target`:
- `"all"` - همه کاربران
- `"active"` - فقط فعال‌ها
- `"inactive"` - فقط غیرفعال‌ها
- `"bytag"` - بر اساس تگ (پارامتر `tag` لازم)

## AnalyticsService

```python
from services.analytics_service import AnalyticsService

async with async_session_maker() as session:
    service = AnalyticsService(session)
```

| متد | توضیح |
|-----|-------|
| `get_dashboard_stats()` | آمار کلی داشبورد |
| `get_period_stats(period)` | آمار دوره‌ای (today/week/month/all) |
| `get_lesson_completion_stats()` | نرخ تکمیل هر درس |
| `save_daily_stats()` | ذخیره آمار روزانه |
| `get_campaign_stats()` | آمار کمپین‌ها |

## ExportService

```python
from services.export_service import ExportService

async with async_session_maker() as session:
    service = ExportService(session)
```

| متد | خروجی |
|-----|--------|
| `export_users_to_excel()` | `bytes` (فایل Excel) |
| `export_progress_to_excel()` | `bytes` (فایل Excel) |
| `export_analytics_to_excel()` | `bytes` (فایل Excel) |

## ReminderService

```python
from services.reminder_service import ReminderService

async with async_session_maker() as session:
    service = ReminderService(session)
```

| متد | توضیح |
|-----|-------|
| `find_inactive_users(days)` | کاربران غیرفعال بیش از X روز |
| `send_reminder(bot, user)` | ارسال یادآوری |
| `send_reminders_to_inactive(bot, days)` | ارسال به همه غیرفعال‌ها |
| `schedule_message(user_id, text, send_at)` | زمان‌بندی پیام |
| `process_scheduled_messages(bot)` | پردازش پیام‌های معلق |
