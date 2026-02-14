"""
📝 پیکربندی متن‌های ربات - Bot Messages Configuration

تمام متن‌هایی که ربات به کاربران و ادمین‌ها نمایش می‌دهد در این فایل قرار دارند.
برای تغییر هر متنی، کافیست مقدار مربوطه را ویرایش کنید.

🔹 از {variable} برای مقادیر پویا استفاده شده (مثلاً نام کاربر، تعداد درس و ...)
🔹 از <b>text</b> برای بولد کردن متن در تلگرام استفاده کنید
🔹 از \\n برای خط جدید استفاده کنید
"""


# ╔══════════════════════════════════════════════╗
# ║           پیام‌های عمومی / خطاها              ║
# ╚══════════════════════════════════════════════╝

GENERAL = {
    "error": "❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
    "unauthorized": "⛔️ شما اجازه دسترسی به این بخش را ندارید.",
    "cancelled": "❌ لغو شد.",
    "not_found": "❌ یافت نشد.",
    "confirm_yes": "✅ بله",
    "confirm_no": "❌ خیر",
    "back": "🔙 بازگشت",
    "status_active": "✅ فعال",
    "status_inactive": "❌ غیرفعال",
}


# ╔══════════════════════════════════════════════╗
# ║          دکمه‌های منوی کاربران               ║
# ╚══════════════════════════════════════════════╝

USER_BUTTONS = {
    # منوی اصلی کاربر
    "continue_course": "📚 ادامه دوره",
    "my_progress": "📊 پیشرفت من",
    "about_course": "ℹ️ درباره دوره",
    "support": "📞 پشتیبانی",

    # دکمه تایید درس
    "lesson_seen": "✅ درس رو دیدم",
    "lesson_seen_delayed": "✅ دیدم، ادامه بده",

    # دکمه انصراف
    "cancel": "❌ انصراف",
}


# ╔══════════════════════════════════════════════╗
# ║         دکمه‌های منوی ادمین                   ║
# ╚══════════════════════════════════════════════╝

ADMIN_BUTTONS = {
    # منوی اصلی ادمین
    "dashboard": "📊 داشبورد",
    "users": "👥 کاربران",
    "lessons": "📚 درس‌ها",
    "reg_fields": "📝 فیلدهای ثبت‌نام",
    "broadcast": "📢 ارسال پیام",
    "reports": "📈 گزارش‌ها",
    "webhook": "🔗 وبهوک",
    "settings": "⚙️ تنظیمات",

    # مدیریت درس‌ها
    "add_lesson": "➕ افزودن درس",
    "lesson_list": "📋 لیست درس‌ها",
    "reorder_lessons": "🔄 ترتیب درس‌ها",
    "edit_lesson": "✏️ ویرایش",
    "toggle_status": "🔄 تغییر وضعیت",
    "quiz": "📝 آزمون",
    "stats": "📊 آمار",
    "delete": "🗑 حذف",
    "back_to_lessons": "🔙 بازگشت به درس‌ها",
    "back_to_course": "🔙 بازگشت به دوره",

    # مدیریت دوره‌ها
    "add_course": "➕ ساخت دوره جدید",
    "edit_title": "✏️ ویرایش عنوان",
    "toggle_course": "🔄 تغییر وضعیت",
    "delete_course": "🗑 حذف دوره",

    # مدیریت کاربران
    "all_users": "👥 همه کاربران",
    "active_users": "✅ فعال‌ها",
    "inactive_users": "❌ غیرفعال‌ها",
    "completed_users": "🎓 تکمیل کننده‌ها",
    "search_users": "🔍 جستجو",
    "export_excel": "📥 اکسپورت Excel",
    "send_message": "💬 ارسال پیام",
    "manage_tags": "🏷 مدیریت تگ‌ها",
    "reset_progress": "🔄 ریست پیشرفت",
    "block_user": "🚫 بلاک",
    "delete_user": "🗑 حذف",

    # ارسال پیام گروهی
    "broadcast_all": "📢 همه کاربران",
    "broadcast_active": "✅ فقط فعال‌ها",
    "broadcast_inactive": "❌ فقط غیرفعال‌ها",
    "broadcast_bytag": "🏷 بر اساس تگ",

    # فیلدهای ثبت‌نام
    "add_field": "➕ افزودن فیلد",
    "field_list": "📋 لیست فیلدها",
    "reorder_fields": "🔄 ترتیب فیلدها",
    "edit_field_label": "✏️ ویرایش عنوان",
    "toggle_required": "🔄 تغییر اجباری",
    "toggle_active": "✅/❌ فعال/غیرفعال",
    "delete_field": "🗑 حذف",

    # انواع فیلد
    "field_text": "📝 متن",
    "field_number": "🔢 عدد",
    "field_email": "📧 ایمیل",
    "field_phone": "📱 شماره تلفن",
    "field_date": "📅 تاریخ",
    "field_select": "☑️ انتخابی",
    "field_cancel": "🔙 انصراف",

    # وبهوک
    "add_webhook": "➕ افزودن وبهوک",
    "webhook_list": "📋 لیست وبهوک‌ها",
    "test_webhook": "🧪 تست وبهوک",

    # گزارش‌ها
    "stats_today": "📊 امروز",
    "stats_week": "📅 هفته",
    "stats_month": "📆 ماه",
    "stats_all": "📈 کل",
    "export_data": "📥 اکسپورت داده",

    # صفحه‌بندی
    "prev_page": "◀️ قبلی",
    "next_page": "بعدی ▶️",

    # انواع محتوا
    "content_text": "📝 متن",
    "content_video": "🎥 ویدیو",
    "content_audio": "🎵 صوت",
    "content_voice": "🎤 ویس",
    "content_document": "📄 فایل",
    "content_photo": "🖼 تصویر",
    "content_form": "📋 فرم",

    # آزمون
    "add_quiz": "➕ ساخت آزمون",
    "delete_quiz": "🗑 حذف آزمون",
    "rebuild_quiz": "✏️ ساخت مجدد",
    "next_question": "➕ سوال بعدی",
    "save_quiz": "✅ ذخیره آزمون",

    # ویرایش درس
    "edit_title_field": "📝 عنوان",
    "edit_description": "📄 توضیحات",
    "edit_delay": "⏱ فاصله زمانی",
    "edit_content": "🔄 محتوا",
    "edit_cta_text": "🔗 متن CTA",
    "edit_cta_url": "🌐 لینک CTA",
    "add_more_content": "➕ اضافه کردن محتوای دیگر",
    "content_done": "✅ ادامه",
    "content_save": "✅ ذخیره",
    "finish_form": "✅ اتمام فرم",
    "add_another_field": "➕ افزودن فیلد دیگر",

    # تحلیل
    "funnel_analysis": "📊 فانل تحلیل",
    "courses_analytics": "📈 آمار دوره‌ها",

    # تایید حذف
    "confirm_delete": "✅ بله، حذف شود",
}


# ╔══════════════════════════════════════════════╗
# ║       پیام‌های ثبت‌نام و شروع                 ║
# ╚══════════════════════════════════════════════╝

REGISTRATION = {
    "welcome": "🎓 به دوره آموزشی ما خوش آمدید!\n\nبرای شروع، لطفاً اطلاعات خود را وارد کنید.",
    "registration_complete": "✅ ثبت‌نام شما با موفقیت انجام شد!\n\nدرس اول به زودی برای شما ارسال می‌شود.",
    "welcome_back": "👋 خوش برگشتید {name}!\n\nاز منوی زیر می‌توانید ادامه دوره را دنبال کنید.",
    "registration_cancelled": "❌ ثبت‌نام لغو شد.\n\nبرای شروع مجدد دستور /start را ارسال کنید.",
    "validation_error": "⚠️ {error}\n\nلطفاً دوباره وارد کنید:",
    "field_prompt": "📝 {label}{required}\n\n{hint}",
    "field_required": " (اجباری)",
    "field_optional": " (اختیاری)",
    "field_hints": {
        "text": "متن را وارد کنید:",
        "number": "عدد را وارد کنید:",
        "email": "ایمیل خود را وارد کنید:\nمثال: example@gmail.com",
        "phone": "شماره موبایل خود را وارد کنید:\nمثال: 09123456789",
        "date": "تاریخ را وارد کنید:\nفرمت: YYYY/MM/DD",
        "select": "یکی از گزینه‌ها را انتخاب کنید:",
        "default": "مقدار را وارد کنید:",
    },
}


# ╔══════════════════════════════════════════════╗
# ║        پیام‌های کاربر (درس و پیشرفت)          ║
# ╚══════════════════════════════════════════════╝

USER = {
    # درس
    "please_register": "⚠️ لطفاً ابتدا ثبت‌نام کنید.\nدستور /start را ارسال کنید.",
    "no_active_course": "📭 هنوز دوره‌ای فعال نیست. لطفاً بعداً مراجعه کنید.",
    "select_course": "📚 <b>انتخاب دوره</b>\n\nکدام دوره را می‌خواهید ادامه دهید؟",
    "course_not_found": "❌ دوره یافت نشد.",
    "course_already_completed": "🎉 شما دوره «{title}» را تکمیل کرده‌اید!\n\nبرای انتخاب دوره دیگر، دوباره «📚 ادامه دوره» را بزنید.",
    "lesson_not_ready": "⏳ درس بعدی هنوز آماده نیست.\nدرس بعدی به‌صورت خودکار برای شما ارسال خواهد شد. لطفاً صبور باشید. 🙏",
    "course_no_lessons": "📭 دوره «{title}» هنوز درسی ندارد.",
    "lesson_sent": "📚 درس {lesson_number} - {lesson_title}\n\n{description}",
    "lesson_completed": "✅ تبریک! درس {lesson_number} را تکمیل کردید.\n\n🎯 پیشرفت شما: {progress}%",
    "lesson_completed_auto": "\n\n📩 درس بعدی به‌صورت خودکار برای شما ارسال خواهد شد.",
    "lesson_completed_manual": "\n\n📚 برای دریافت درس بعدی روی «ادامه دوره» کلیک کنید.",
    "course_completed": "🎉 تبریک! شما دوره را با موفقیت تکمیل کردید!\n\n🏆 آفرین!",
    "lesson_confirmed": "✅ تایید شد!",

    # فرم
    "form_intro": "📋 <b>{title}</b>\n\n{description}\n\nلطفاً به سوالات زیر پاسخ دهید ({count} سوال):",
    "form_question": "📝 سوال {idx} از {total}:\n\n<b>{label}</b>",
    "form_select_hint": "یکی از گزینه‌ها را انتخاب کنید:",
    "form_text_hint": "پاسخ خود را تایپ کنید:",
    "form_number_hint": "یک عدد وارد کنید:",
    "form_default_hint": "پاسخ خود را وارد کنید:",
    "form_invalid": "⚠️ فرم نامعتبر. لطفاً دوباره تلاش کنید.",
    "form_number_error": "⚠️ لطفاً یک عدد معتبر وارد کنید:",
    "form_empty_error": "⚠️ پاسخ نمی‌تواند خالی باشد. لطفاً دوباره وارد کنید:",
    "form_submitted": "✅ <b>فرم با موفقیت ارسال شد!</b>",

    # آزمون
    "quiz_intro": "📝 <b>آزمون درس: {title}</b>\n\nتعداد سوالات: {count}\nحد نصاب قبولی: {passing_score}%\n\nبیایید شروع کنیم! 🚀",
    "quiz_question": "❓ سوال {idx} از {total}:\n\n<b>{text}</b>",
    "quiz_invalid": "⚠️ آزمون نامعتبر. لطفاً درس را دوباره تایید کنید.",
    "quiz_correct": "✅ صحیح! {answer}",
    "quiz_wrong": "❌ اشتباه! پاسخ صحیح: {answer}",
    "quiz_passed": "🎉 <b>تبریک! آزمون قبول شد!</b>\n\n📝 {title}\n✅ پاسخ‌های صحیح: {correct} از {total}\n📊 نمره: {score}%\n🎯 حد نصاب: {passing_score}%",
    "quiz_failed": "❌ <b>متأسفانه آزمون قبول نشد.</b>\n\n📝 {title}\n✅ پاسخ‌های صحیح: {correct} از {total}\n📊 نمره: {score}%\n🎯 حد نصاب: {passing_score}%\n\nمی‌توانید دوباره تلاش کنید:",
    "quiz_retry": "🔄 تلاش مجدد",
    "quiz_retry_start": "🔄 شروع مجدد آزمون...",
    "quiz_not_found": "⚠️ آزمون یافت نشد.",

    # پیشرفت
    "progress_header": "📊 <b>پیشرفت شما</b>\n\n",
    "progress_percent": "📈 {percent}% تکمیل شده",
    "progress_completed": "✅ درس‌های تکمیل شده: {completed}",
    "progress_total": "📚 کل درس‌ها: {total}",
    "progress_remaining": "📋 باقی‌مانده: {remaining}",
    "progress_course_status": "🎉 تکمیل شده",
    "progress_summary": "📈 <b>مجموع:</b> {completed}/{total} درس ({percent}%)",
    "progress_all_done": "🎉 تبریک! شما تمام دوره‌ها را تکمیل کرده‌اید!",

    # درباره دوره
    "about_single": "📚 <b>درباره دوره</b>\n\nتعداد درس‌ها: {total}\n\nبرای شروع یا ادامه دوره از منوی اصلی استفاده کنید.",
    "about_multi_header": "📚 <b>دوره‌های موجود</b>\n\n",
    "about_course_lessons": "📊 تعداد درس‌ها: {count}",
    "about_footer": "برای شروع یا ادامه دوره از منوی اصلی استفاده کنید.",

    # پشتیبانی
    "support_text": (
        "📞 <b>پشتیبانی</b>\n\n"
        "در صورت وجود مشکل یا سوال، پیام خود را ارسال کنید.\n"
        "تیم پشتیبانی در اسرع وقت پاسخگو خواهد بود.\n\n"
        "همچنین می‌توانید از دستورات زیر استفاده کنید:\n"
        "/start - شروع مجدد\n"
        "/progress - مشاهده پیشرفت\n"
        "/help - راهنما"
    ),

    # راهنما
    "help_text": (
        "📖 <b>راهنمای ربات</b>\n\n"
        "🔹 /start - شروع یا ورود مجدد\n"
        "🔹 /progress - مشاهده پیشرفت\n"
        "🔹 /help - این راهنما\n\n"
        "📚 <b>ادامه دوره</b> - دریافت درس بعدی\n"
        "📊 <b>پیشرفت من</b> - مشاهده وضعیت پیشرفت\n"
        "ℹ️ <b>درباره دوره</b> - اطلاعات دوره\n"
        "📞 <b>پشتیبانی</b> - ارتباط با پشتیبانی"
    ),
}


# ╔══════════════════════════════════════════════╗
# ║            پیام‌های پنل ادمین                 ║
# ╚══════════════════════════════════════════════╝

ADMIN = {
    # ورود
    "welcome": "👋 سلام ادمین عزیز!\n\nبه پنل مدیریت خوش آمدید.",
    "panel_header": "🔧 <b>پنل مدیریت</b>\n\nاز منوی زیر گزینه مورد نظر را انتخاب کنید:",

    # داشبورد
    "dashboard_header": "📊 <b>داشبورد</b>\n\n",
    "dashboard_total_users": "👥 کل کاربران: {count}",
    "dashboard_active_users": "✅ کاربران فعال: {count}",
    "dashboard_completed": "🎓 تکمیل کننده‌ها: {count}",
    "dashboard_completion_rate": "📈 نرخ تکمیل: {rate}%",
    "dashboard_courses": "📖 دوره‌ها: {count}",
    "dashboard_lessons": "📚 درس‌ها: {count}",
    "dashboard_activity_header": "🕐 <b>فعالیت:</b>",
    "dashboard_active_24h": "🔥 ۲۴ ساعت اخیر: {count}",
    "dashboard_active_7d": "📅 ۷ روز اخیر: {count}",
    "dashboard_today_header": "📅 <b>امروز:</b>",
    "dashboard_today_new": "🆕 کاربران جدید: {count}",
    "dashboard_today_lessons": "✅ درس‌های تکمیل شده: {count}",
    "dashboard_week_header": "📅 <b>این هفته:</b>",
    "dashboard_week_new": "🆕 کاربران جدید: {count}",

    # فانل
    "funnel_no_data": "📭 داده‌ای برای تحلیل وجود ندارد.",
    "funnel_header": "📊 <b>تحلیل فانل (ریزش درس به درس)</b>\n\n",
    "funnel_start": "شروع: {start} | تکمیل: {end} ({rate}%)",
    "funnel_drop": "ریزش: {rate}%",
    "funnel_legend": "⚠️ = ریزش بالا (>30%)  ⚡ = ریزش متوسط (>15%)",

    # آمار دوره
    "courses_analytics_header": "📈 <b>آمار دوره‌ها</b>\n\n",
    "courses_analytics_lessons": "📖 {count} درس | 👥 {enrolled} ثبت‌نام",
    "courses_analytics_completed": "🎓 {count} تکمیل ({rate}%)",
    "courses_analytics_quiz": "📝 آزمون: {attempts} تلاش | قبولی: {pass_rate}% | میانگین: {avg}",

    # مدیریت دوره
    "courses_header": "📚 <b>مدیریت دوره‌ها و درس‌ها</b>\n\nیک دوره را انتخاب کنید یا دوره جدید بسازید:",
    "course_button": "{status} {title} ({count} درس)",
    "course_not_found": "❌ دوره یافت نشد.",
    "course_create_title": "📝 <b>ساخت دوره جدید</b>\n\nعنوان دوره را وارد کنید:",
    "course_create_desc": "📝 توضیحات دوره را وارد کنید (یا /skip):",
    "course_created": "✅ دوره «{title}» با موفقیت ساخته شد!\n\nحالا می‌توانید درس‌ها را به این دوره اضافه کنید.",
    "course_view_header": "📚 <b>{title}</b>",
    "course_view_desc": "📝 {description}",
    "course_view_status": "📊 وضعیت: {status}",
    "course_view_stats_header": "📈 <b>آمار:</b>",
    "course_view_lesson_count": "📖 تعداد درس: {count}",
    "course_view_enrolled": "👥 ثبت‌نام شده: {count}",
    "course_view_completed": "🎓 تکمیل کرده: {count}",
    "course_view_rate": "📊 نرخ تکمیل: {rate}%",
    "course_view_lessons_header": "<b>درس‌ها:</b>",
    "course_view_more_lessons": "... و {count} درس دیگر",
    "course_toggled": "🔄 دوره «{title}» {status} شد.",
    "course_toggled_active": "فعال ✅",
    "course_toggled_inactive": "غیرفعال ❌",
    "course_delete_confirm": "⚠️ آیا مطمئنید که می‌خواهید دوره «{title}» و تمام درس‌هایش را حذف کنید؟",
    "course_deleted": "✅ دوره حذف شد.",
    "course_edit_title": "✏️ عنوان جدید دوره را وارد کنید:",
    "course_title_updated": "✅ عنوان دوره به «{title}» تغییر یافت.",

    # مدیریت درس
    "lesson_add_title": "📝 <b>افزودن درس جدید</b>\n\nعنوان درس را وارد کنید:",
    "lesson_select_type": "نوع محتوای درس را انتخاب کنید:",
    "lesson_type_prompts": {
        "text": "📝 متن درس را ارسال کنید:",
        "video": "🎥 ویدیو درس را ارسال کنید (فایل ویدیو):",
        "audio": "🎵 فایل صوتی یا ویس درس را ارسال کنید:",
        "voice": "🎤 ویس درس را ضبط و ارسال کنید (یا فایل صوتی بفرستید):",
        "document": "📄 فایل درس را ارسال کنید:",
        "photo": "🖼 تصویر درس را ارسال کنید:",
        "default": "محتوای درس را ارسال کنید:",
    },
    "lesson_audio_error": "⚠️ لطفاً فایل صوتی یا ویس ارسال کنید.",
    "lesson_voice_error": "⚠️ لطفاً ویس ضبط کنید یا فایل صوتی ارسال کنید.",
    "lesson_type_error": "⚠️ لطفاً نوع محتوای صحیح ارسال کنید.",
    "lesson_content_added": "✅ محتوا اضافه شد!\n\n{summary}\nآیا می‌خواهید محتوای دیگری اضافه کنید؟",
    "lesson_select_next_type": "نوع محتوای بعدی را انتخاب کنید:",
    "lesson_enter_description": "📝 توضیحات درس را وارد کنید (یا /skip برای رد شدن):",
    "lesson_enter_delay": "⏱ <b>فاصله زمانی تا درس بعدی</b>\n\nبعد از تایید این درس، چند دقیقه بعد درس بعدی ارسال شود؟\nعدد را به دقیقه وارد کنید (مثلاً: 60 برای یک ساعت، 1440 برای یک روز)\nیا 0 برای ارسال فوری:",
    "lesson_delay_error": "⚠️ لطفاً یک عدد صحیح مثبت وارد کنید (مثلاً: 0، 30، 60، 1440):",
    "lesson_created": "✅ درس «{title}» با موفقیت اضافه شد!\n📋 شماره: {order}\n{content_info}\n⏱ فاصله: {delay}",
    "lesson_add_quiz_prompt": "اگر می‌خواهید آزمون هم اضافه کنید:",
    "lesson_add_quiz_btn": "📝 افزودن آزمون",
    "lesson_back_to_panel": "✅ بازگشت به پنل",
    "lesson_list_empty": "📭 دوره «{title}» هنوز درسی ندارد.",
    "lesson_list_header": "📚 <b>درس‌های دوره «{title}»</b> ({count} درس)\n\nبرای مدیریت روی هر درس کلیک کنید:",
    "lesson_not_found": "❌ درس یافت نشد.",
    "lesson_view_header": "📚 <b>درس {order}: {title}</b>",
    "lesson_view_content": "📦 محتوا: {content}",
    "lesson_view_status": "📌 وضعیت: {status}",
    "lesson_view_delay": "⏱ فاصله تا درس بعد: {delay}",
    "lesson_view_desc": "📝 توضیحات: {desc}",
    "lesson_view_no_desc": "ندارد",
    "lesson_view_stats": "📊 <b>آمار:</b>",
    "lesson_view_started": "👁 شروع شده: {count}",
    "lesson_view_completed": "✅ تکمیل شده: {count}",
    "lesson_view_rate": "📈 نرخ تکمیل: {rate}%",
    "lesson_view_cta": "🔗 CTA: {text}",
    "lesson_view_quiz": "📝 آزمون: {count} سوال (حداقل {score}%)",

    # ویرایش درس
    "lesson_edit_header": "✏️ <b>ویرایش درس</b>\n\nکدام فیلد را می‌خواهید ویرایش کنید؟",
    "lesson_edit_content_header": "🔄 <b>ویرایش محتوای درس</b>\n\nمحتوای قبلی جایگزین خواهد شد.\nنوع اولین محتوا را انتخاب کنید:",
    "lesson_edit_prompts": {
        "title": "📝 عنوان جدید درس را وارد کنید:",
        "description": "📄 توضیحات جدید را وارد کنید (یا /skip برای حذف):",
        "delay": "⏱ فاصله زمانی جدید (به دقیقه) را وارد کنید (مثلاً: 0، 30، 60، 1440):",
        "cta_text": "🔗 متن دکمه CTA جدید را وارد کنید (یا /skip برای حذف):",
        "cta_url": "🌐 لینک CTA جدید را وارد کنید (یا /skip برای حذف):",
        "default": "مقدار جدید را وارد کنید:",
    },
    "lesson_edit_delay_error": "⚠️ عدد نامعتبر. ویرایش لغو شد.",
    "lesson_edit_error": "⚠️ خطا. لطفاً دوباره تلاش کنید.",
    "lesson_edited": "✅ درس «{title}» با موفقیت ویرایش شد.",
    "lesson_edit_failed": "❌ خطا در ویرایش درس.",
    "lesson_edit_content_audio_error": "⚠️ لطفاً فایل صوتی ارسال کنید.",
    "lesson_edit_content_voice_error": "⚠️ لطفاً ویس ارسال کنید.",
    "lesson_edit_content_type_error": "⚠️ لطفاً محتوای صحیح ارسال کنید.",
    "lesson_edit_content_added": "✅ محتوا اضافه شد!\n\n{summary}\nآیا می‌خواهید محتوای دیگری اضافه کنید؟",
    "lesson_edit_no_content": "⚠️ هیچ محتوایی اضافه نشد.",
    "lesson_edit_content_saved": "✅ محتوای درس «{title}» با {count} بخش ویرایش شد.",
    "lesson_edit_content_prompts": {
        "text": "📝 متن را ارسال کنید:",
        "video": "🎥 ویدیو را ارسال کنید:",
        "audio": "🎵 فایل صوتی را ارسال کنید:",
        "voice": "🎤 ویس را ضبط و ارسال کنید:",
        "document": "📄 فایل را ارسال کنید:",
        "photo": "🖼 تصویر را ارسال کنید:",
        "default": "محتوا را ارسال کنید:",
    },

    # ترتیب درس
    "reorder_min_lessons": "⚠️ حداقل ۲ درس برای تغییر ترتیب نیاز است.",
    "reorder_header": "🔄 <b>تغییر ترتیب درس‌ها</b>\n\nبا دکمه‌های ⬆️ و ⬇️ ترتیب را تغییر دهید:",

    # تغییر وضعیت درس
    "lesson_toggled": "وضعیت درس: {status}",
    "lesson_toggle_error": "❌ خطا در تغییر وضعیت",

    # حذف درس
    "lesson_delete_confirm": "⚠️ آیا از حذف این درس اطمینان دارید؟\nاین عمل غیرقابل بازگشت است.",
    "lesson_deleted": "✅ درس با موفقیت حذف شد.",
    "lesson_delete_error": "❌ خطا در حذف درس.",
    "operation_cancelled": "لغو شد",

    # مدیریت کاربران
    "users_header": "👥 <b>مدیریت کاربران</b>\n\nیک گزینه را انتخاب کنید:",
    "users_empty": "📭 کاربری یافت نشد.",
    "users_list_header": "👥 <b>کاربران</b> ({count} نفر)\n\n",
    "users_page": "📄 {page}/{total}",
    "user_not_found": "❌ کاربر یافت نشد.",
    "user_info_header": "👤 <b>اطلاعات کاربر</b>",
    "user_info_name": "📛 نام: {name}",
    "user_info_username": "👤 یوزرنیم: @{username}",
    "user_info_id": "🆔 آیدی: {id}",
    "user_info_status": "📌 وضعیت: {status}",
    "user_info_completed": "🎓 تکمیل دوره: {status}",
    "user_info_stats_header": "📊 <b>آمار:</b>",
    "user_info_lessons": "✅ درس‌های تکمیل شده: {completed}/{total}",
    "user_info_progress": "📈 پیشرفت: {percent}%",
    "user_info_time": "⏱ زمان صرف شده: {time}",
    "user_info_tags": "🏷 تگ‌ها: {tags}",
    "user_info_registered": "📅 تاریخ ثبت‌نام: {date}",
    "user_info_reg_data": "📝 <b>اطلاعات ثبت‌نام:</b>",
    "user_completed_yes": "بله ✅",
    "user_completed_no": "خیر ❌",

    # اقدامات روی کاربر
    "user_message_prompt": "💬 پیام خود را ارسال کنید:",
    "user_message_sent": "✅ پیام با موفقیت ارسال شد.",
    "user_message_error": "❌ خطا در ارسال پیام.",
    "user_blocked": "🚫 کاربر بلاک شد.",
    "user_unblocked": "✅ کاربر آنبلاک شد.",
    "user_delete_confirm": "⚠️ آیا از حذف این کاربر اطمینان دارید؟",
    "user_deleted": "✅ کاربر حذف شد.",
    "user_delete_error": "❌ خطا در حذف کاربر.",
    "user_progress_reset": "✅ پیشرفت کاربر ریست شد.",
    "user_progress_reset_error": "❌ خطا در ریست پیشرفت.",

    # تگ‌ها
    "tags_header": "🏷 <b>مدیریت تگ‌ها</b>\n\nتگ‌های فعلی: {tags}\n\nتگ‌ها را با کاما جدا کرده و ارسال کنید:\nمثال: vip, active, campaign1\n\nبرای حذف همه تگ‌ها عبارت 'clear' را ارسال کنید.",
    "tags_updated": "✅ تگ‌ها با موفقیت ب‌روزرسانی شد.\n🏷 تگ‌ها: {tags}",

    # جستجو
    "search_prompt": "🔍 نام، یوزرنیم یا شماره کاربر را وارد کنید:",
    "search_empty": "📭 کاربری یافت نشد.",
    "search_results": "🔍 نتایج جستجو ({count} نفر):",

    # اکسپورت
    "export_preparing": "در حال آماده‌سازی فایل...",
    "export_users_caption": "📥 فایل اکسپورت کاربران",
    "export_analytics_caption": "📥 فایل اکسپورت گزارش‌ها",

    # ارسال پیام همگانی
    "broadcast_header": "📢 <b>ارسال پیام</b>\n\nمخاطبان را انتخاب کنید:",
    "broadcast_enter_msg": "📝 پیام خود را ارسال کنید:",
    "broadcast_sending": "📡 در حال ارسال پیام...",
    "broadcast_result": "📢 <b>نتیجه ارسال پیام</b>\n\n👥 کل: {total}\n✅ موفق: {sent}\n❌ ناموفق: {failed}",

    # فیلدهای ثبت‌نام
    "fields_header": "📝 <b>مدیریت فیلدهای ثبت‌نام</b>\n\nیک گزینه را انتخاب کنید:",
    "field_add_name": "📝 نام فیلد (شناسه انگلیسی) را وارد کنید:\nمثال: phone, city, age",
    "field_add_label": "📝 عنوان فیلد (فارسی) را وارد کنید:\nمثال: شماره تلفن، شهر، سن",
    "field_add_type": "نوع فیلد را انتخاب کنید:",
    "field_add_options": "گزینه‌ها را با کاما جدا کنید:\nمثال: تهران، اصفهان، شیراز",
    "field_added": "✅ فیلد «{label}» با موفقیت اضافه شد!\n📦 نوع: {type}\n📋 ترتیب: {order}",
    "field_list_empty": "📭 هنوز فیلدی اضافه نشده.",
    "field_list_header": "📝 <b>فیلدهای ثبت‌نام</b>\n\nبرای مدیریت روی هر فیلد کلیک کنید:",
    "field_not_found": "❌ فیلد یافت نشد.",
    "field_view_header": "📝 <b>جزئیات فیلد</b>",
    "field_view_name": "📛 شناسه: {name}",
    "field_view_label": "🏷 عنوان: {label}",
    "field_view_type": "📦 نوع: {type}",
    "field_view_required": "📌 اجباری: {status}",
    "field_view_active": "🔄 وضعیت: {status}",
    "field_view_order": "📋 ترتیب: {order}",
    "field_view_options": "📋 گزینه‌ها: {options}",
    "field_required_yes": "✅ بله",
    "field_required_no": "❌ خیر",
    "field_toggle_required": "وضعیت: {status}",
    "field_toggle_required_on": "اجباری ✅",
    "field_toggle_required_off": "اختیاری ❌",
    "field_toggle_active": "وضعیت: {status}",
    "field_toggle_active_on": "فعال ✅",
    "field_toggle_active_off": "غیرفعال ❌",
    "field_deleted": "✅ فیلد حذف شد.",
    "field_edit_label_prompt": "📝 عنوان جدید فیلد را وارد کنید:",
    "field_label_updated": "✅ عنوان فیلد به «{label}» تغییر کرد.",
    "reorder_fields_min": "⚠️ حداقل ۲ فیلد برای تغییر ترتیب نیاز است.",
    "reorder_fields_header": "🔄 <b>تغییر ترتیب فیلدها</b>\n\nبا دکمه‌های ⬆️ و ⬇️ ترتیب را تغییر دهید:",

    # ساخت فرم درس
    "form_builder_intro": "📋 <b>ساخت فرم</b>\n\nعنوان فیلد اول را وارد کنید:\nمثال: نام و نام خانوادگی، شهر، نظر شما",
    "form_field_type": "نوع فیلد را انتخاب کنید:",
    "form_field_type_text": "📝 متن",
    "form_field_type_number": "🔢 عدد",
    "form_field_type_select": "☑️ انتخابی",
    "form_field_options": "📋 گزینه‌ها را با کاما جدا کرده وارد کنید:\nمثال: تهران، اصفهان، شیراز",
    "form_field_added": "✅ فیلد «{label}» اضافه شد.\n\n📋 فیلدهای فرم:\n{fields}\n\nآیا فیلد دیگری اضافه می‌کنید؟",
    "form_next_field": "📝 عنوان فیلد بعدی را وارد کنید:",
    "form_enter_description": "📝 توضیحات فرم را وارد کنید (یا /skip برای رد شدن):",

    # آزمون
    "quiz_header": "📝 <b>آزمون درس «{title}»</b>\n\n✅ تعداد سوالات: {count}\n📊 حداقل نمره قبولی: {score}%",
    "quiz_correct_answer": "✅ جواب: {answer}",
    "quiz_no_quiz": "📝 درس «{title}» آزمون ندارد.\n\nآزمون باعث می‌شود کاربر بعد از مشاهده درس به سوالات پاسخ دهد.\nاگر نمره کافی بگیرد، درس تایید می‌شود.",
    "quiz_deleted": "✅ آزمون حذف شد.",
    "quiz_enter_score": "📝 <b>ساخت آزمون</b>\n\nحداقل درصد قبولی را وارد کنید (مثلاً: 70 یا 100):",
    "quiz_score_error": "⚠️ لطفاً عددی بین 1 تا 100 وارد کنید:",
    "quiz_enter_question": "📝 متن سوال {n} را وارد کنید:",
    "quiz_enter_first_question": "📝 متن سوال اول را وارد کنید:",
    "quiz_enter_options": "📋 گزینه‌ها را هر کدام در یک خط بنویسید (حداقل ۲ گزینه):\n\nمثال:\nتهران\nاصفهان\nشیراز",
    "quiz_options_error": "⚠️ حداقل ۲ گزینه وارد کنید (هر کدام در یک خط):",
    "quiz_select_correct": "✅ <b>گزینه صحیح را انتخاب کنید:</b>",
    "quiz_answer_saved": "✅ ثبت شد",
    "quiz_question_added": "✅ سوال {n} اضافه شد.\n📊 تعداد سوالات: {n}\n\nآیا سوال دیگری اضافه می‌کنید؟",
    "quiz_empty": "❌ آزمون بدون سوال ذخیره نشد.",
    "quiz_saved": "✅ آزمون با {count} سوال و حداقل نمره {score}% ذخیره شد.",

    # گزارش‌ها
    "reports_header": "📈 <b>گزارش‌ها و آمار</b>\n\nدوره زمانی را انتخاب کنید:",
    "report_period_labels": {
        "today": "امروز",
        "week": "هفته",
        "month": "ماه",
        "all": "کل",
    },
    "report_header": "📈 <b>گزارش {period}</b>",
    "report_new_users": "🆕 کاربران جدید: {count}",
    "report_completed_lessons": "✅ درس‌های تکمیل شده: {count}",
    "report_active_users": "👥 کاربران فعال: {count}",
    "report_lesson_stats_header": "📚 <b>آمار درس‌ها:</b>",
    "report_lesson_stat": "{order}. {title}: {completed} تکمیل ({rate}%)",

    # وبهوک
    "webhook_header": "🔗 <b>مدیریت وبهوک‌ها</b>",
    "webhook_empty": "📭 هنوز وبهوکی تعریف نشده.",
    "webhook_structure_header": "📋 <b>ساختار استاندارد وبهوک:</b>",
    "webhook_events_header": "<b>رویدادها:</b>",
    "webhook_add_name": "🔗 <b>افزودن وبهوک جدید</b>\n\nنام وبهوک را وارد کنید (مثل: n8n, crm, zapier):",
    "webhook_add_url": "🌐 URL وبهوک را وارد کنید:",
    "webhook_added": "✅ وبهوک «{name}» با موفقیت اضافه شد!\n🌐 URL: {url}",
    "webhook_list_empty": "📭 هنوز وبهوکی اضافه نشده.",
    "webhook_list_header": "🔗 <b>لیست وبهوک‌ها</b>",
    "webhook_toggled": "🔄 وبهوک «{name}» {status} شد.",
    "webhook_deleted": "🗑 وبهوک حذف شد.",
    "webhook_testing": "در حال تست...",
    "webhook_test_header": "🧪 <b>نتایج تست وبهوک‌ها</b>",

    # تنظیمات
    "settings_header": "⚙️ <b>تنظیمات</b>",
    "settings_token": "🤖 توکن: {token}",
    "settings_token_not_set": "تنظیم نشده",
    "settings_admins": "👥 ادمین‌ها: {count} نفر",
    "settings_db": "🗄 دیتابیس: {host}",
    "settings_reminder_days": "💤 روز یادآوری: {days} روز",
    "settings_broadcast_rate": "📢 سرعت ارسال: {rate} پیام/ثانیه",
    "settings_log_level": "📝 لاگ: {level}",
}


# ╔══════════════════════════════════════════════╗
# ║     قالب‌های فاصله زمانی                       ║
# ╚══════════════════════════════════════════════╝

DELAY = {
    "instant": "فوری",
    "minutes": "{minutes} دقیقه",
    "hours": "{hours} ساعت",
    "hours_minutes": "{hours} ساعت و {minutes} دقیقه",
    "days": "{days} روز",
}


# ╔══════════════════════════════════════════════╗
# ║     قالب‌های انواع محتوا                       ║
# ╚══════════════════════════════════════════════╝

CONTENT_TYPES = {
    "text": "متن",
    "video": "ویدیو",
    "audio": "صوت",
    "voice": "ویس",
    "document": "فایل",
    "photo": "تصویر",
    "form": "فرم",
}


# ╔══════════════════════════════════════════════╗
# ║       قالب‌های یادآوری هوشمند                  ║
# ╚══════════════════════════════════════════════╝

REMINDERS = {
    "default_name": "دوست",
    "templates": [
        (
            "👋 سلام {name}!\n\n"
            "مدتیه که سری به دوره نزدید.\n"
            "درس‌های جالبی منتظر شماست! 📚\n\n"
            "📚 ادامه دوره"
        ),
        (
            "🌟 {name} عزیز!\n\n"
            "پیشرفتت عالی بوده ولی کمی متوقف شدی.\n"
            "فقط {remaining} درس تا تکمیل دوره مونده! 💪\n\n"
            "📚 ادامه دوره"
        ),
        (
            "📖 سلام {name}!\n\n"
            "یادت نره که {progress}% دوره رو تکمیل کردی.\n"
            "بیا ادامه بدیم! 🚀\n\n"
            "📚 ادامه دوره"
        ),
        (
            "💡 {name} جان!\n\n"
            "آخرین فعالیتت {days_ago} روز پیش بود.\n"
            "درس بعدی منتظرته، فقط یه کلیک فاصله داری! ✨\n\n"
            "📚 ادامه دوره"
        ),
        (
            "🎯 {name} عزیز!\n\n"
            "هم‌کلاسی‌هات دارن پیشرفت می‌کنن.\n"
            "بیا عقب نمونی! 😊\n\n"
            "📚 ادامه دوره"
        ),
    ],
    "form_lesson": (
        "📋 <b>درس {order}: {title}</b>\n\n"
        "{description}\n\n"
        "📝 این درس شامل یک فرم است.\n"
        "برای پر کردن فرم روی دکمه «📚 ادامه دوره» کلیک کنید."
    ),
}


# ╔══════════════════════════════════════════════╗
# ║       متن‌های اکسپورت اکسل                    ║
# ╚══════════════════════════════════════════════╝

EXPORT = {
    # ستون‌های کاربران
    "col_id": "شناسه",
    "col_telegram_id": "آیدی تلگرام",
    "col_username": "یوزرنیم",
    "col_first_name": "نام",
    "col_last_name": "نام خانوادگی",
    "col_status": "وضعیت",
    "col_completed": "تکمیل دوره",
    "col_tags": "تگ‌ها",
    "col_campaign": "کمپین",
    "col_reg_date": "تاریخ ثبت‌نام",
    "col_last_activity": "آخرین فعالیت",
    "val_active": "فعال",
    "val_inactive": "غیرفعال",
    "val_yes": "بله",
    "val_no": "خیر",
    "sheet_users": "کاربران",

    # ستون‌های پیشرفت
    "col_name": "نام",
    "val_completed": "✅ تکمیل",
    "val_in_progress": "🔄 در حال مشاهده",
    "val_not_started": "❌ مشاهده نشده",
    "sheet_progress": "پیشرفت",

    # ستون‌های آنالیتیکس
    "col_indicator": "شاخص",
    "col_value": "مقدار",
    "ind_total_users": "کل کاربران",
    "ind_active_users": "کاربران فعال",
    "ind_completed_users": "تکمیل کننده‌ها",
    "ind_completion_rate": "نرخ تکمیل (%)",
    "ind_today_new": "کاربران جدید امروز",
    "ind_week_new": "کاربران جدید این هفته",
    "col_lesson": "درس",
    "col_started": "شروع شده",
    "col_lesson_completed": "تکمیل شده",
    "col_completion_rate": "نرخ تکمیل (%)",
    "sheet_dashboard": "داشبورد",
    "sheet_lessons": "درس‌ها",
}
