import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { users } from '../api';

const TABS = [
  { key: 'overview', label: 'نمای کلی', icon: '📋' },
  { key: 'engagement', label: 'تعامل', icon: '🔥' },
  { key: 'progress', label: 'پیشرفت دروس', icon: '📚' },
  { key: 'quizzes', label: 'کوئیزها', icon: '❓' },
  { key: 'forms', label: 'فرم‌ها', icon: '📝' },
  { key: 'messages', label: 'پیام‌ها', icon: '💬' },
];

const BADGE_INFO = {
  starter: { emoji: '🌱', label: 'شروع‌کننده' },
  motivated: { emoji: '💪', label: 'با‌انگیزه' },
  streak_5: { emoji: '🔥', label: '۵ روز متوالی' },
  streak_10: { emoji: '⚡', label: '۱۰ روز متوالی' },
  halfway: { emoji: '🏔️', label: 'نیمه راه' },
  almost: { emoji: '🎯', label: 'نزدیک خط پایان' },
  fast_learner: { emoji: '🚀', label: 'یادگیرنده سریع' },
  graduate: { emoji: '🎓', label: 'فارغ‌التحصیل' },
};

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('fa-IR', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

function formatShortDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('fa-IR');
}

function timeDiff(start, end) {
  if (!start || !end) return null;
  const ms = new Date(end) - new Date(start);
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `${mins} دقیقه`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} ساعت`;
  const days = Math.round(hours / 24);
  return `${days} روز`;
}

export default function UserDetail() {
  const { id } = useParams();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('overview');

  useEffect(() => {
    setLoading(true);
    users.get(id)
      .then(setUser)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="text-center py-20 text-gray-500">در حال بارگذاری...</div>;
  }

  if (!user) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-400 text-lg">کاربر یافت نشد</p>
        <Link to="/users" className="text-blue-600 hover:underline mt-2 inline-block">بازگشت به لیست</Link>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Link to="/users" className="text-gray-400 hover:text-gray-600 text-xl">→</Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-800">
              {user.first_name || 'کاربر'} {user.last_name || ''}
            </h1>
            <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
              {user.username && <span dir="ltr">@{user.username}</span>}
              <span className={`px-2 py-0.5 rounded-full text-xs ${user.platform === 'telegram' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                {user.platform}
              </span>
              {user.is_completed ? (
                <span className="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700">تکمیل شده</span>
              ) : user.is_active ? (
                <span className="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-700">فعال</span>
              ) : (
                <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600">غیرفعال</span>
              )}
            </div>
          </div>
        </div>
        <div className="text-left">
          <div className="text-3xl font-bold text-blue-600">{user.lead_score}</div>
          <div className="text-xs text-gray-400">امتیاز</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-white rounded-xl border p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              tab === t.key
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <span className="ml-1">{t.icon}</span> {t.label}
            {t.key === 'quizzes' && user.quizzes?.length > 0 && (
              <span className="mr-1 px-1.5 py-0.5 rounded-full bg-white/20 text-xs">{user.quizzes.length}</span>
            )}
            {t.key === 'forms' && user.forms?.length > 0 && (
              <span className="mr-1 px-1.5 py-0.5 rounded-full bg-white/20 text-xs">{user.forms.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'overview' && <OverviewTab user={user} />}
      {tab === 'engagement' && <EngagementTab user={user} />}
      {tab === 'progress' && <ProgressTab user={user} />}
      {tab === 'quizzes' && <QuizzesTab user={user} />}
      {tab === 'forms' && <FormsTab user={user} />}
      {tab === 'messages' && <MessagesTab user={user} />}
    </div>
  );
}

/* ── Overview Tab ── */
function OverviewTab({ user }) {
  const totalLessons = user.progress?.length || 0;
  const completedLessons = user.progress?.filter(p => p.completed_at).length || 0;
  const progressPct = totalLessons > 0 ? Math.round((completedLessons / totalLessons) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard title="دروس دیده" value={totalLessons} icon="📖" />
        <StatCard title="دروس تکمیل" value={completedLessons} icon="✅" color="green" />
        <StatCard title="کوئیزها" value={user.quizzes?.length || 0} icon="❓" color="purple" />
        <StatCard title="🔥 استریک" value={user.streak_days || 0} icon="🔥" color="amber" />
        <StatCard title="🏅 نشان‌ها" value={(user.badges || []).length} icon="🏅" color="amber" />
      </div>

      {/* Progress Bar */}
      <div className="bg-white rounded-xl border p-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">پیشرفت کلی</span>
          <span className="text-sm text-gray-500">{progressPct}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className="bg-blue-600 h-3 rounded-full transition-all"
            style={{ width: `${progressPct}%` }}
          ></div>
        </div>
      </div>

      {/* Info Grid */}
      <div className="bg-white rounded-xl border p-6">
        <h3 className="font-bold text-gray-700 mb-4">اطلاعات کاربر</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <InfoRow label="شناسه تلگرام" value={user.telegram_user_id} dir="ltr" />
          <InfoRow label="دوره فعلی" value={user.current_course_title || '—'} />
          <InfoRow label="درس فعلی" value={user.current_lesson_id ? `درس #${user.current_lesson_id}` : '—'} />
          <InfoRow label="مسئول فروش" value={user.assigned_owner_name || '—'} />
          <InfoRow label="تاریخ ثبت‌نام" value={formatDate(user.created_at)} />
          <InfoRow label="آخرین فعالیت" value={formatDate(user.last_activity_at)} />
          <InfoRow label="تگ‌ها" value={user.tags?.length > 0 ? user.tags.join('، ') : '—'} />
        </div>
      </div>

      {/* Registration Data */}
      {user.registration_data && Object.keys(user.registration_data).length > 0 && (
        <div className="bg-white rounded-xl border p-6">
          <h3 className="font-bold text-gray-700 mb-4">📋 اطلاعات ثبت‌نام</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.entries(user.registration_data).map(([key, value]) => (
              <div key={key} className="flex items-start gap-2 bg-gray-50 rounded-lg p-3">
                <span className="text-gray-500 text-sm min-w-[100px]">{key}:</span>
                <span className="text-gray-800 text-sm font-medium">{String(value)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Engagement Tab ── */
function EngagementTab({ user }) {
  const badges = user.badges || [];

  return (
    <div className="space-y-6">
      {/* Streak Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="bg-orange-50 rounded-xl border border-orange-200 p-5 text-center">
          <div className="text-4xl mb-2">🔥</div>
          <div className="text-3xl font-bold text-orange-700">{user.streak_days || 0}</div>
          <div className="text-sm text-orange-600 mt-1">روز متوالی فعلی</div>
        </div>
        <div className="bg-purple-50 rounded-xl border border-purple-200 p-5 text-center">
          <div className="text-4xl mb-2">⚡</div>
          <div className="text-3xl font-bold text-purple-700">{user.best_streak || 0}</div>
          <div className="text-sm text-purple-600 mt-1">بهترین رکورد</div>
        </div>
        <div className="bg-blue-50 rounded-xl border border-blue-200 p-5 text-center">
          <div className="text-4xl mb-2">📅</div>
          <div className="text-xl font-bold text-blue-700">
            {user.last_streak_date
              ? new Date(user.last_streak_date).toLocaleDateString('fa-IR')
              : '—'}
          </div>
          <div className="text-sm text-blue-600 mt-1">آخرین فعالیت streak</div>
        </div>
      </div>

      {/* Badges */}
      <div className="bg-white rounded-xl border p-6">
        <h3 className="font-bold text-gray-700 mb-4">🏅 نشان‌های کسب شده ({badges.length})</h3>
        {badges.length > 0 ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {badges.map((badge) => {
              const info = BADGE_INFO[badge] || { emoji: '🏷️', label: badge };
              return (
                <div key={badge} className="bg-gradient-to-br from-amber-50 to-yellow-50 border border-amber-200 rounded-xl p-4 text-center">
                  <div className="text-3xl mb-2">{info.emoji}</div>
                  <div className="text-sm font-bold text-amber-800">{info.label}</div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-400">
            <div className="text-4xl mb-2">🏷️</div>
            <p>هنوز نشانی کسب نشده</p>
          </div>
        )}
      </div>

      {/* All Available Badges */}
      <div className="bg-white rounded-xl border p-6">
        <h3 className="font-bold text-gray-700 mb-4">🎯 همه نشان‌ها</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(BADGE_INFO).map(([key, info]) => {
            const earned = badges.includes(key);
            return (
              <div
                key={key}
                className={`rounded-xl p-4 text-center border transition ${
                  earned
                    ? 'bg-gradient-to-br from-amber-50 to-yellow-50 border-amber-200'
                    : 'bg-gray-50 border-gray-200 opacity-40'
                }`}
              >
                <div className="text-3xl mb-2">{earned ? info.emoji : '🔒'}</div>
                <div className={`text-sm font-bold ${earned ? 'text-amber-800' : 'text-gray-400'}`}>
                  {info.label}
                </div>
                {earned && <div className="text-xs text-green-600 mt-1">✅ کسب شده</div>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ── Progress Tab ── */
function ProgressTab({ user }) {
  if (!user.progress?.length) {
    return <EmptyState text="هنوز هیچ درسی شروع نشده" />;
  }

  return (
    <div className="space-y-3">
      {user.progress.map((p, i) => (
        <div
          key={i}
          className={`bg-white rounded-xl border p-4 flex items-center gap-4 transition ${
            p.completed_at ? 'border-green-200' : 'border-amber-200'
          }`}
        >
          {/* Lesson Number */}
          <div className={`w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold ${
            p.completed_at ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
          }`}>
            {p.lesson_number ?? i}
          </div>

          {/* Info */}
          <div className="flex-1">
            <div className="font-medium text-gray-800">{p.lesson_title}</div>
            <div className="flex flex-wrap gap-3 mt-1 text-xs text-gray-500">
              {p.course_title && <span>📚 {p.course_title}</span>}
              <span>📥 {formatDate(p.started_at)}</span>
              {p.completed_at && <span>✅ {formatDate(p.completed_at)}</span>}
              {p.started_at && p.completed_at && (
                <span>⏱ {timeDiff(p.started_at, p.completed_at)}</span>
              )}
            </div>
          </div>

          {/* Badges */}
          <div className="flex gap-2">
            {p.has_quiz && (
              <span className="px-2 py-1 rounded-lg bg-purple-50 text-purple-600 text-xs">کوئیز</span>
            )}
            {p.has_form && (
              <span className="px-2 py-1 rounded-lg bg-amber-50 text-amber-600 text-xs">فرم</span>
            )}
            {p.completed_at ? (
              <span className="px-2 py-1 rounded-lg bg-green-50 text-green-600 text-xs">✅ تکمیل</span>
            ) : (
              <span className="px-2 py-1 rounded-lg bg-amber-50 text-amber-600 text-xs">⏳ در انتظار</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Quizzes Tab ── */
function QuizzesTab({ user }) {
  if (!user.quizzes?.length) {
    return <EmptyState text="هنوز هیچ کوئیزی پاسخ داده نشده" />;
  }

  return (
    <div className="space-y-4">
      {user.quizzes.map((q, i) => (
        <QuizCard key={i} quiz={q} />
      ))}
    </div>
  );
}

function QuizCard({ quiz }) {
  const [expanded, setExpanded] = useState(false);

  // Parse quiz questions from quiz_data
  const questions = quiz.quiz_data?.questions || [];
  const userAnswers = quiz.answers || {};

  return (
    <div className="bg-white rounded-xl border overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 transition"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg ${
            quiz.passed ? 'bg-green-100' : 'bg-red-100'
          }`}>
            {quiz.passed ? '✅' : '❌'}
          </div>
          <div>
            <div className="font-medium text-gray-800">
              {quiz.lesson_title}
              {quiz.lesson_number != null && <span className="text-gray-400 text-sm mr-2">(درس {quiz.lesson_number})</span>}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">
              {formatDate(quiz.created_at)}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className={`text-lg font-bold ${quiz.passed ? 'text-green-600' : 'text-red-600'}`}>
            {Math.round(quiz.score)}%
          </div>
          <span className="text-gray-400 text-sm">{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* Detailed Answers */}
      {expanded && questions.length > 0 && (
        <div className="border-t p-4 space-y-4 bg-gray-50">
          {questions.map((question, qi) => {
            const userAnswer = userAnswers[String(qi)] ?? userAnswers[question.id] ?? null;
            const isCorrect = userAnswer !== null && String(userAnswer) === String(question.correct);
            const options = question.options || [];

            return (
              <div key={qi} className="bg-white rounded-lg border p-4">
                <div className="flex items-start gap-2 mb-3">
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                    isCorrect ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {qi + 1}
                  </span>
                  <span className="font-medium text-gray-800">{question.question || question.text}</span>
                </div>

                {options.length > 0 && (
                  <div className="space-y-1.5 mr-8">
                    {options.map((opt, oi) => {
                      const optText = typeof opt === 'string' ? opt : opt.text || opt.label || String(opt);
                      const optIndex = String(oi);
                      const isUserChoice = String(userAnswer) === optIndex;
                      const isCorrectOpt = String(question.correct) === optIndex;

                      let cls = 'bg-gray-50 text-gray-600';
                      if (isCorrectOpt) cls = 'bg-green-50 text-green-700 border-green-200';
                      if (isUserChoice && !isCorrectOpt) cls = 'bg-red-50 text-red-700 border-red-200';

                      return (
                        <div key={oi} className={`px-3 py-1.5 rounded-lg border text-sm flex items-center gap-2 ${cls}`}>
                          {isUserChoice && <span>{isCorrectOpt ? '✅' : '❌'}</span>}
                          {!isUserChoice && isCorrectOpt && <span>✅</span>}
                          <span>{optText}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Forms Tab ── */
function FormsTab({ user }) {
  if (!user.forms?.length) {
    return <EmptyState text="هنوز هیچ فرمی پر نشده" />;
  }

  return (
    <div className="space-y-4">
      {user.forms.map((f, i) => (
        <FormCard key={i} form={f} />
      ))}
    </div>
  );
}

function FormCard({ form }) {
  // Parse form fields from form_data
  const fields = form.form_data?.fields || [];
  const responses = form.response_data || {};

  return (
    <div className="bg-white rounded-xl border p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-medium text-gray-800">
            📝 {form.lesson_title}
            {form.lesson_number != null && <span className="text-gray-400 text-sm mr-2">(درس {form.lesson_number})</span>}
          </h3>
          <div className="text-xs text-gray-500 mt-0.5">{formatDate(form.created_at)}</div>
        </div>
      </div>

      <div className="space-y-3">
        {fields.length > 0 ? (
          fields.map((field, fi) => {
            const answer = responses[field.name || field.id || String(fi)] || responses[String(fi)] || '—';
            return (
              <div key={fi} className="flex items-start gap-2 bg-gray-50 rounded-lg p-3">
                <span className="text-gray-500 text-sm min-w-[120px]">
                  {field.label || field.name || `سؤال ${fi + 1}`}:
                </span>
                <span className="text-gray-800 text-sm font-medium">{String(answer)}</span>
              </div>
            );
          })
        ) : (
          /* If no form_data structure, show raw response */
          Object.entries(responses).map(([key, value]) => (
            <div key={key} className="flex items-start gap-2 bg-gray-50 rounded-lg p-3">
              <span className="text-gray-500 text-sm min-w-[120px]">{key}:</span>
              <span className="text-gray-800 text-sm font-medium">{String(value)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ── Messages Tab ── */
function MessagesTab({ user }) {
  if (!user.messages?.length) {
    return <EmptyState text="هیچ پیام زمان‌بندی‌شده‌ای یافت نشد" />;
  }

  const statusMap = {
    pending: { label: 'در انتظار', cls: 'bg-amber-100 text-amber-700' },
    sent: { label: 'ارسال شده', cls: 'bg-green-100 text-green-700' },
    failed: { label: 'خطا', cls: 'bg-red-100 text-red-700' },
    cancelled: { label: 'لغو شده', cls: 'bg-gray-100 text-gray-600' },
  };

  const typeMap = {
    next_lesson: '📖 درس بعدی',
    reminder: '🔔 یادآور',
    lesson_nudge: '👋 پیگیری درس',
    start_nudge: '🚀 پیگیری شروع',
    lesson_teaser: '🌅 تیزر درس',
    promotional: '📢 تبلیغاتی',
  };

  return (
    <div className="bg-white rounded-xl border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="px-4 py-3 text-right font-medium text-gray-600">نوع</th>
            <th className="px-4 py-3 text-right font-medium text-gray-600">پیام</th>
            <th className="px-4 py-3 text-right font-medium text-gray-600">وضعیت</th>
            <th className="px-4 py-3 text-right font-medium text-gray-600">زمان ارسال</th>
          </tr>
        </thead>
        <tbody>
          {user.messages.map((m) => {
            const st = statusMap[m.status] || statusMap.pending;
            return (
              <tr key={m.id} className="border-b hover:bg-gray-50">
                <td className="px-4 py-3 whitespace-nowrap">
                  <span className="text-xs">{typeMap[m.message_type] || m.message_type}</span>
                </td>
                <td className="px-4 py-3 text-gray-600 text-xs max-w-xs truncate" title={m.message}>
                  {m.message}
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${st.cls}`}>{st.label}</span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {formatDate(m.sent_at || m.send_at)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ── Helper Components ── */
function StatCard({ title, value, icon, color = 'blue' }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-700',
    green: 'bg-green-50 text-green-700',
    purple: 'bg-purple-50 text-purple-700',
    amber: 'bg-amber-50 text-amber-700',
  };

  return (
    <div className={`rounded-xl p-4 ${colors[color]}`}>
      <div className="text-2xl mb-1">{icon}</div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs opacity-75">{title}</div>
    </div>
  );
}

function InfoRow({ label, value, dir }) {
  return (
    <div className="flex items-center gap-2 py-2 border-b border-gray-100">
      <span className="text-gray-500 text-sm min-w-[120px]">{label}:</span>
      <span className="text-gray-800 text-sm font-medium" dir={dir}>{value}</span>
    </div>
  );
}

function EmptyState({ text }) {
  return (
    <div className="text-center py-16 bg-white rounded-xl border">
      <div className="text-4xl mb-3">📭</div>
      <p className="text-gray-400">{text}</p>
    </div>
  );
}
