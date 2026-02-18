#!/bin/bash
# ============================================================
#  نمونه‌های curl برای تست ورکفلو n8n
#  هر ایونت دقیقاً مشابه payload واقعی سیستم است
# ============================================================
#
#  استفاده:
#    1. یکی از دستورات زیر رو کپی کنید
#    2. مقادیر رو بر اساس نیاز ویرایش کنید
#    3. اجرا کنید
#
#  نکته: responseMode=onReceived هست، یعنی فوری 200 برمیگرده
#        نتیجه واقعی رو باید از لیست Executions در n8n ببینید
# ============================================================

WEBHOOK_URL="https://irn8n.javidmgdm.com/webhook/course-bot"


# ──────────────────────────────────────────────────────
#  1. lead.register — ثبت‌نام کاربر جدید
#     Router: شاخه 0
#     زنجیره: Prep Register → Find Person → Process Person
#             → IF Person Exists → Create/Update Person
#             → Search Deal Reg → Create/Update Deal
#             → Happy Call → Respond Register
# ──────────────────────────────────────────────────────
curl -s -k -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
  "event_id": "test-lead-register-001",
  "event_time": "2026-02-18T14:00:00Z",
  "source": "jmgdmdore_bot@bale",
  "platform": "bale",
  "event": {
    "type": "lead",
    "action": "register",
    "status": "success"
  },
  "user": {
    "telegram_id": 296614867,
    "platform": "bale",
    "username": "javid_test",
    "first_name": "جاوید",
    "last_name": "محمدی",
    "registration_data": {
      "full_name": "جاوید محمدی",
      "phone": "09127411249",
      "monthly_income": "بالای ۲۰ میلیون",
      "investment_experience": "بله",
      "education_level": "کارشناسی ارشد"
    },
    "tags": [],
    "referral_code": null,
    "referred_by": null,
    "is_active": true,
    "is_completed": false,
    "lead_score": 15,
    "phone": "09127411249",
    "created_at": "2026-02-18T14:00:00",
    "last_activity_at": "2026-02-18T14:00:00"
  },
  "course": null,
  "lesson": null,
  "progress": null,
  "payload": {
    "fields_to_update": {
      "person.telegram_id": 296614867,
      "person.platform": "bale",
      "person.telegram_username": "javid_test",
      "person.first_name": "جاوید",
      "person.last_name": "محمدی"
    },
    "note_to_create": "monthly_income: بالای ۲۰ میلیون\ninvestment_experience: بله\neducation_level: کارشناسی ارشد"
  },
  "security": {
    "signature": "",
    "idempotency_key": "test-lead-register-001"
  }
}'

echo ""
echo "=== lead.register sent ==="


# ──────────────────────────────────────────────────────
#  2. lesson.complete — تکمیل درس (بدون trigger_sales)
#     Router: شاخه 1
#     زنجیره: Prep Lesson → Find Person Lesson
#             → Extract Person Lesson → Update Person Score
#             → Search Deal Lesson → Update Deal Stage
# ──────────────────────────────────────────────────────
: '
curl -s -k -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
  "event_id": "test-lesson-complete-001",
  "event_time": "2026-02-18T15:00:00Z",
  "source": "jmgdmdore_bot@bale",
  "platform": "bale",
  "event": {
    "type": "lesson",
    "action": "complete",
    "status": "success"
  },
  "user": {
    "telegram_id": 296614867,
    "platform": "bale",
    "username": "javid_test",
    "first_name": "جاوید",
    "last_name": "محمدی",
    "registration_data": {
      "full_name": "جاوید محمدی",
      "phone": "09127411249"
    },
    "tags": [],
    "referral_code": null,
    "referred_by": null,
    "is_active": true,
    "is_completed": false,
    "lead_score": 35,
    "phone": "09127411249",
    "created_at": "2026-02-18T14:00:00",
    "last_activity_at": "2026-02-18T15:00:00"
  },
  "course": {
    "id": 1,
    "title": "دوره IBM"
  },
  "lesson": {
    "id": 3,
    "title": "درس سوم - مبانی تحلیل",
    "order": 3,
    "lesson_number": 3
  },
  "progress": {
    "percent": 30,
    "completed": 3,
    "total": 10,
    "lead_score": 35
  },
  "payload": {
    "fields_to_update": {
      "person.telegram_id": 296614867,
      "person.platform": "bale"
    },
    "note_to_create": "",
    "trigger_sales": false,
    "completed_at": "2026-02-18T15:00:00Z",
    "lead_score_field_json": "{\"Field_996_12_30\":\"35\"}"
  },
  "security": {
    "signature": "",
    "idempotency_key": "test-lesson-complete-001"
  }
}'
'

echo ""
echo "=== lesson.complete (no sales) - COMMENTED OUT ==="


# ──────────────────────────────────────────────────────
#  3. lesson.complete — تکمیل درس (با trigger_sales)
#     Router: شاخه 1
#     زنجیره: مثل بالا + Sales Call اگر trigger_sales=true
# ──────────────────────────────────────────────────────
: '
curl -s -k -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
  "event_id": "test-lesson-complete-sales-001",
  "event_time": "2026-02-18T16:00:00Z",
  "source": "jmgdmdore_bot@bale",
  "platform": "bale",
  "event": {
    "type": "lesson",
    "action": "complete",
    "status": "success"
  },
  "user": {
    "telegram_id": 296614867,
    "platform": "bale",
    "username": "javid_test",
    "first_name": "جاوید",
    "last_name": "محمدی",
    "registration_data": {
      "full_name": "جاوید محمدی",
      "phone": "09127411249"
    },
    "tags": [],
    "referral_code": null,
    "referred_by": null,
    "is_active": true,
    "is_completed": false,
    "lead_score": 50,
    "phone": "09127411249",
    "created_at": "2026-02-18T14:00:00",
    "last_activity_at": "2026-02-18T16:00:00"
  },
  "course": {
    "id": 1,
    "title": "دوره IBM"
  },
  "lesson": {
    "id": 5,
    "title": "درس پنجم - بازاریابی",
    "order": 5,
    "lesson_number": 5
  },
  "progress": {
    "percent": 50,
    "completed": 5,
    "total": 10,
    "lead_score": 50
  },
  "payload": {
    "fields_to_update": {
      "person.telegram_id": 296614867,
      "person.platform": "bale"
    },
    "note_to_create": "",
    "trigger_sales": true,
    "sales_trigger_reason": "reached_lesson_5",
    "completed_at": "2026-02-18T16:00:00Z",
    "lead_score_field_json": "{\"Field_996_12_30\":\"50\"}"
  },
  "security": {
    "signature": "",
    "idempotency_key": "test-lesson-complete-sales-001"
  }
}'
'

echo ""
echo "=== lesson.complete (trigger_sales) - COMMENTED OUT ==="


# ──────────────────────────────────────────────────────
#  4. form.submit — ارسال فرم
#     Router: شاخه 2
#     زنجیره: Prep Form → Find Person Form
#             → Extract Person Form → Update Person Form
#             → Create Note
# ──────────────────────────────────────────────────────
: '
curl -s -k -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
  "event_id": "test-form-submit-001",
  "event_time": "2026-02-18T17:00:00Z",
  "source": "jmgdmdore_bot@bale",
  "platform": "bale",
  "event": {
    "type": "form",
    "action": "submit",
    "status": "success"
  },
  "user": {
    "telegram_id": 296614867,
    "platform": "bale",
    "username": "javid_test",
    "first_name": "جاوید",
    "last_name": "محمدی",
    "registration_data": {
      "full_name": "جاوید محمدی",
      "phone": "09127411249"
    },
    "tags": [],
    "referral_code": null,
    "referred_by": null,
    "is_active": true,
    "is_completed": false,
    "lead_score": 40,
    "phone": "09127411249",
    "created_at": "2026-02-18T14:00:00",
    "last_activity_at": "2026-02-18T17:00:00"
  },
  "course": null,
  "lesson": {
    "id": 4,
    "title": "فرم نظرسنجی درس چهارم"
  },
  "progress": null,
  "payload": {
    "fields_to_update": {
      "person.telegram_id": 296614867,
      "person.platform": "bale"
    },
    "note_to_create": "",
    "form_responses": {
      "satisfaction": "خیلی راضی",
      "suggestion": "ادامه بدید عالیه",
      "rating": "5"
    },
    "form_fields": ["satisfaction", "suggestion", "rating"]
  },
  "security": {
    "signature": "",
    "idempotency_key": "test-form-submit-001"
  }
}'
'

echo ""
echo "=== form.submit - COMMENTED OUT ==="


# ──────────────────────────────────────────────────────
#  5. quiz.pass — قبولی در آزمون
#     Router: شاخه 3
#     زنجیره: Prep Quiz Pass → Create Note → Respond OK
# ──────────────────────────────────────────────────────
: '
curl -s -k -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
  "event_id": "test-quiz-pass-001",
  "event_time": "2026-02-18T18:00:00Z",
  "source": "jmgdmdore_bot@bale",
  "platform": "bale",
  "event": {
    "type": "quiz",
    "action": "pass",
    "status": "success"
  },
  "user": {
    "telegram_id": 296614867,
    "platform": "bale",
    "username": "javid_test",
    "first_name": "جاوید",
    "last_name": "محمدی",
    "registration_data": {
      "full_name": "جاوید محمدی",
      "phone": "09127411249"
    },
    "tags": [],
    "referral_code": null,
    "referred_by": null,
    "is_active": true,
    "is_completed": false,
    "lead_score": 55,
    "phone": "09127411249",
    "created_at": "2026-02-18T14:00:00",
    "last_activity_at": "2026-02-18T18:00:00"
  },
  "course": {
    "id": 1,
    "title": "دوره IBM"
  },
  "lesson": {
    "id": 3,
    "title": "درس سوم - مبانی تحلیل",
    "order": 3,
    "lesson_number": 3
  },
  "progress": null,
  "payload": {
    "fields_to_update": {
      "person.telegram_id": 296614867,
      "person.platform": "bale"
    },
    "note_to_create": "",
    "score": 85,
    "total": 100,
    "percentage": 85,
    "passed": true
  },
  "security": {
    "signature": "",
    "idempotency_key": "test-quiz-pass-001"
  }
}'
'

echo ""
echo "=== quiz.pass - COMMENTED OUT ==="


# ──────────────────────────────────────────────────────
#  6. quiz.fail — مردودی در آزمون
#     Router: شاخه 4
#     زنجیره: Prep Quiz Fail → Create Note → Respond OK
# ──────────────────────────────────────────────────────
: '
curl -s -k -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
  "event_id": "test-quiz-fail-001",
  "event_time": "2026-02-18T18:30:00Z",
  "source": "jmgdmdore_bot@bale",
  "platform": "bale",
  "event": {
    "type": "quiz",
    "action": "fail",
    "status": "success"
  },
  "user": {
    "telegram_id": 296614867,
    "platform": "bale",
    "username": "javid_test",
    "first_name": "جاوید",
    "last_name": "محمدی",
    "registration_data": {
      "full_name": "جاوید محمدی",
      "phone": "09127411249"
    },
    "tags": [],
    "referral_code": null,
    "referred_by": null,
    "is_active": true,
    "is_completed": false,
    "lead_score": 55,
    "phone": "09127411249",
    "created_at": "2026-02-18T14:00:00",
    "last_activity_at": "2026-02-18T18:30:00"
  },
  "course": {
    "id": 1,
    "title": "دوره IBM"
  },
  "lesson": {
    "id": 3,
    "title": "درس سوم - مبانی تحلیل",
    "order": 3,
    "lesson_number": 3
  },
  "progress": null,
  "payload": {
    "fields_to_update": {
      "person.telegram_id": 296614867,
      "person.platform": "bale"
    },
    "note_to_create": "",
    "score": 30,
    "total": 100,
    "percentage": 30,
    "passed": false
  },
  "security": {
    "signature": "",
    "idempotency_key": "test-quiz-fail-001"
  }
}'
'

echo ""
echo "=== quiz.fail - COMMENTED OUT ==="


# ──────────────────────────────────────────────────────
#  7. course.complete — تکمیل کل دوره
#     Router: شاخه 6
#     زنجیره: Prep Complete → Find Person Complete
#             → Extract Person Complete → Update Score Complete
#             → Search Deal Complete → Update Deal Complete
# ──────────────────────────────────────────────────────
: '
curl -s -k -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
  "event_id": "test-course-complete-001",
  "event_time": "2026-02-18T20:00:00Z",
  "source": "jmgdmdore_bot@bale",
  "platform": "bale",
  "event": {
    "type": "course",
    "action": "complete",
    "status": "success"
  },
  "user": {
    "telegram_id": 296614867,
    "platform": "bale",
    "username": "javid_test",
    "first_name": "جاوید",
    "last_name": "محمدی",
    "registration_data": {
      "full_name": "جاوید محمدی",
      "phone": "09127411249"
    },
    "tags": [],
    "referral_code": null,
    "referred_by": null,
    "is_active": true,
    "is_completed": true,
    "lead_score": 100,
    "phone": "09127411249",
    "created_at": "2026-02-18T14:00:00",
    "last_activity_at": "2026-02-18T20:00:00"
  },
  "course": {
    "id": 1,
    "title": "دوره IBM"
  },
  "lesson": null,
  "progress": {
    "percent": 100,
    "completed": 10,
    "total": 10,
    "lead_score": 100
  },
  "payload": {
    "fields_to_update": {
      "person.telegram_id": 296614867,
      "person.platform": "bale"
    },
    "note_to_create": ""
  },
  "security": {
    "signature": "",
    "idempotency_key": "test-course-complete-001"
  }
}'
'

echo ""
echo "=== course.complete - COMMENTED OUT ==="


# ──────────────────────────────────────────────────────
#  8. speed.change — تغییر سرعت 2x
#     Router: شاخه 7
#     زنجیره: Prep Speed → Create Note → Respond OK
# ──────────────────────────────────────────────────────
: '
curl -s -k -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
  "event_id": "test-speed-change-001",
  "event_time": "2026-02-18T19:00:00Z",
  "source": "jmgdmdore_bot@bale",
  "platform": "bale",
  "event": {
    "type": "speed",
    "action": "change",
    "status": "success"
  },
  "user": {
    "telegram_id": 296614867,
    "platform": "bale",
    "username": "javid_test",
    "first_name": "جاوید",
    "last_name": "محمدی",
    "registration_data": {
      "full_name": "جاوید محمدی",
      "phone": "09127411249"
    },
    "tags": [],
    "referral_code": null,
    "referred_by": null,
    "is_active": true,
    "is_completed": false,
    "lead_score": 50,
    "phone": "09127411249",
    "created_at": "2026-02-18T14:00:00",
    "last_activity_at": "2026-02-18T19:00:00"
  },
  "course": {
    "id": 1,
    "title": "دوره IBM"
  },
  "lesson": null,
  "progress": null,
  "payload": {
    "fields_to_update": {
      "person.telegram_id": 296614867,
      "person.platform": "bale"
    },
    "note_to_create": "",
    "mode": "2x",
    "enabled": true
  },
  "security": {
    "signature": "",
    "idempotency_key": "test-speed-change-001"
  }
}'
'

echo ""
echo "=== speed.change - COMMENTED OUT ==="


# ──────────────────────────────────────────────────────
#  9-11. Fallback events — lesson.open, quiz.start, course.select
#        Router: شاخه 8 (Fallback)
#        زنجیره: Prep Respond OK → Respond OK
# ──────────────────────────────────────────────────────
: '
# lesson.open
curl -s -k -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
  "event_id": "test-lesson-open-001",
  "event_time": "2026-02-18T14:30:00Z",
  "source": "jmgdmdore_bot@bale",
  "platform": "bale",
  "event": {
    "type": "lesson",
    "action": "open",
    "status": "success"
  },
  "user": {
    "telegram_id": 296614867,
    "platform": "bale",
    "username": "javid_test",
    "first_name": "جاوید",
    "last_name": "محمدی",
    "registration_data": {"full_name": "جاوید محمدی", "phone": "09127411249"},
    "tags": [], "referral_code": null, "referred_by": null,
    "is_active": true, "is_completed": false, "lead_score": 20,
    "phone": "09127411249",
    "created_at": "2026-02-18T14:00:00",
    "last_activity_at": "2026-02-18T14:30:00"
  },
  "course": {"id": 1, "title": "دوره IBM"},
  "lesson": {"id": 2, "title": "درس دوم", "order": 2, "lesson_number": 2, "type": "video"},
  "progress": null,
  "payload": {
    "fields_to_update": {"person.telegram_id": 296614867},
    "note_to_create": "",
    "has_quiz": false,
    "has_form": false
  },
  "security": {"signature": "", "idempotency_key": "test-lesson-open-001"}
}'
'

echo ""
echo "=== Done ==="
