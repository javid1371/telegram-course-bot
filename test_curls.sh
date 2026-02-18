#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  تست ورکفلو n8n — نمونه‌های curl آماده اجرا
#  هر بلاک رو جداگانه کپی و اجرا کن
# ═══════════════════════════════════════════════════════════

URL="https://irn8n.javidmgdm.com/webhook/course-bot"

echo "انتخاب کنید:"
echo "  1) lead.register        — ثبت‌نام (شاخه 0)"
echo "  2) lesson.complete      — تکمیل درس (شاخه 1)"
echo "  3) lesson.complete+sale — تکمیل درس + فروش (شاخه 1)"
echo "  4) form.submit          — ارسال فرم (شاخه 2)"
echo "  5) quiz.pass            — قبولی آزمون (شاخه 3)"
echo "  6) quiz.fail            — مردودی آزمون (شاخه 4)"
echo "  7) course.complete      — تکمیل دوره (شاخه 6)"
echo "  8) speed.change         — تغییر سرعت (شاخه 7)"
echo "  9) lesson.open          — باز شدن درس (Fallback)"
echo "  0) همه"
echo ""
read -p "شماره: " choice

send_event() {
  local name=$1
  local data=$2
  echo ""
  echo "━━━ $name ━━━"
  resp=$(curl -s -k -X POST "$URL" -H "Content-Type: application/json" -d "$data")
  echo "Response: $resp"
}

# ─── 1. lead.register ───
E1='{
  "event_id": "manual-test-lead-register",
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
    "idempotency_key": "manual-test-lead-register"
  }
}'

# ─── 2. lesson.complete (بدون فروش) ───
E2='{
  "event_id": "manual-test-lesson-complete",
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
    "idempotency_key": "manual-test-lesson-complete"
  }
}'

# ─── 3. lesson.complete (با trigger_sales) ───
E3='{
  "event_id": "manual-test-lesson-sales",
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
    "idempotency_key": "manual-test-lesson-sales"
  }
}'

# ─── 4. form.submit ───
E4='{
  "event_id": "manual-test-form-submit",
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
    "idempotency_key": "manual-test-form-submit"
  }
}'

# ─── 5. quiz.pass ───
E5='{
  "event_id": "manual-test-quiz-pass",
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
    "idempotency_key": "manual-test-quiz-pass"
  }
}'

# ─── 6. quiz.fail ───
E6='{
  "event_id": "manual-test-quiz-fail",
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
    "idempotency_key": "manual-test-quiz-fail"
  }
}'

# ─── 7. course.complete ───
E7='{
  "event_id": "manual-test-course-complete",
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
    "idempotency_key": "manual-test-course-complete"
  }
}'

# ─── 8. speed.change ───
E8='{
  "event_id": "manual-test-speed-change",
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
    "idempotency_key": "manual-test-speed-change"
  }
}'

# ─── 9. lesson.open (Fallback) ───
E9='{
  "event_id": "manual-test-lesson-open",
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
    "registration_data": {
      "full_name": "جاوید محمدی",
      "phone": "09127411249"
    },
    "tags": [],
    "referral_code": null,
    "referred_by": null,
    "is_active": true,
    "is_completed": false,
    "lead_score": 20,
    "phone": "09127411249",
    "created_at": "2026-02-18T14:00:00",
    "last_activity_at": "2026-02-18T14:30:00"
  },
  "course": {
    "id": 1,
    "title": "دوره IBM"
  },
  "lesson": {
    "id": 2,
    "title": "درس دوم - آشنایی",
    "order": 2,
    "lesson_number": 2,
    "type": "video"
  },
  "progress": null,
  "payload": {
    "fields_to_update": {
      "person.telegram_id": 296614867
    },
    "note_to_create": "",
    "has_quiz": false,
    "has_form": false
  },
  "security": {
    "signature": "",
    "idempotency_key": "manual-test-lesson-open"
  }
}'

# ─── اجرا ───
case $choice in
  1) send_event "lead.register" "$E1" ;;
  2) send_event "lesson.complete" "$E2" ;;
  3) send_event "lesson.complete+sale" "$E3" ;;
  4) send_event "form.submit" "$E4" ;;
  5) send_event "quiz.pass" "$E5" ;;
  6) send_event "quiz.fail" "$E6" ;;
  7) send_event "course.complete" "$E7" ;;
  8) send_event "speed.change" "$E8" ;;
  9) send_event "lesson.open" "$E9" ;;
  0)
    send_event "lead.register" "$E1"
    sleep 2
    send_event "lesson.complete" "$E2"
    sleep 1
    send_event "lesson.complete+sale" "$E3"
    sleep 1
    send_event "form.submit" "$E4"
    sleep 1
    send_event "quiz.pass" "$E5"
    sleep 1
    send_event "quiz.fail" "$E6"
    sleep 1
    send_event "course.complete" "$E7"
    sleep 1
    send_event "speed.change" "$E8"
    sleep 1
    send_event "lesson.open" "$E9"
    ;;
  *) echo "شماره نامعتبر" ;;
esac

echo ""
echo "✅ تمام — نتیجه رو از Executions در n8n ببین"
