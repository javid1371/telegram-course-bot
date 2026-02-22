import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { users } from '../api';

export default function LessonProgress() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [courseFilter, setCourseFilter] = useState('');
  const [expandedLesson, setExpandedLesson] = useState(null);
  const [lessonUsers, setLessonUsers] = useState(null);
  const [loadingUsers, setLoadingUsers] = useState(false);

  const load = (cid) => {
    setLoading(true);
    const params = cid ? { course_id: cid } : {};
    users.byLesson(params)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleCourseChange = (cid) => {
    setCourseFilter(cid);
    setExpandedLesson(null);
    setLessonUsers(null);
    load(cid || undefined);
  };

  const toggleLesson = async (lessonId) => {
    if (expandedLesson === lessonId) {
      setExpandedLesson(null);
      setLessonUsers(null);
      return;
    }
    setExpandedLesson(lessonId);
    setLoadingUsers(true);
    try {
      const result = await users.byLessonDetail(lessonId);
      setLessonUsers(result);
    } catch {
      setLessonUsers(null);
    } finally {
      setLoadingUsers(false);
    }
  };

  if (loading) {
    return <div className="text-center py-20 text-gray-500">در حال بارگذاری...</div>;
  }

  if (!data) {
    return <div className="text-center py-20 text-gray-400">خطا در بارگذاری</div>;
  }

  // Calculate totals
  const totalStarted = data.lessons.reduce((s, l) => s + l.started_users, 0);
  const totalCompleted = data.lessons.reduce((s, l) => s + l.completed_users, 0);
  const totalCurrent = data.lessons.reduce((s, l) => s + l.current_users, 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">📊 روند پیشرفت دروس</h1>
        <div className="flex items-center gap-3">
          <select
            value={courseFilter}
            onChange={(e) => handleCourseChange(e.target.value)}
            className="px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
          >
            <option value="">همه دوره‌ها</option>
            {data.courses?.map((c) => (
              <option key={c.id} value={c.id}>{c.title}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-blue-50 rounded-xl p-4">
          <div className="text-2xl font-bold text-blue-700">{totalCurrent}</div>
          <div className="text-xs text-blue-600">هم‌اکنون در دروس</div>
        </div>
        <div className="bg-amber-50 rounded-xl p-4">
          <div className="text-2xl font-bold text-amber-700">{totalStarted}</div>
          <div className="text-xs text-amber-600">شروع شده (جمع)</div>
        </div>
        <div className="bg-green-50 rounded-xl p-4">
          <div className="text-2xl font-bold text-green-700">{totalCompleted}</div>
          <div className="text-xs text-green-600">تکمیل شده (جمع)</div>
        </div>
      </div>

      {/* Funnel View */}
      <div className="space-y-2">
        {data.lessons.map((lesson) => {
          const maxUsers = Math.max(...data.lessons.map(l => l.started_users), 1);
          const barWidth = Math.max((lesson.started_users / maxUsers) * 100, 3);
          const completionRate = lesson.started_users > 0
            ? Math.round((lesson.completed_users / lesson.started_users) * 100)
            : 0;

          return (
            <div key={lesson.id}>
              <div
                className={`bg-white rounded-xl border p-4 cursor-pointer hover:shadow-sm transition ${
                  expandedLesson === lesson.id ? 'border-blue-400 shadow-sm' : ''
                }`}
                onClick={() => toggleLesson(lesson.id)}
              >
                <div className="flex items-center gap-4">
                  {/* Lesson Number */}
                  <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-bold flex-shrink-0">
                    {lesson.lesson_number ?? '—'}
                  </div>

                  {/* Info + Bar */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-800 text-sm truncate">{lesson.title}</span>
                        {lesson.course_title && (
                          <span className="text-xs text-gray-400 hidden md:inline">({lesson.course_title})</span>
                        )}
                        {lesson.has_quiz && <span className="text-xs px-1.5 py-0.5 rounded bg-purple-50 text-purple-600">کوئیز</span>}
                        {lesson.has_form && <span className="text-xs px-1.5 py-0.5 rounded bg-amber-50 text-amber-600">فرم</span>}
                      </div>
                      <div className="flex items-center gap-4 text-xs text-gray-500 flex-shrink-0">
                        <span title="هم‌اکنون در این درس">🔵 {lesson.current_users}</span>
                        <span title="شروع کرده">📥 {lesson.started_users}</span>
                        <span title="تکمیل کرده">✅ {lesson.completed_users}</span>
                        <span title="نرخ تکمیل" className="font-medium">{completionRate}%</span>
                      </div>
                    </div>

                    {/* Progress Bars */}
                    <div className="relative h-4 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="absolute top-0 right-0 h-full bg-blue-200 rounded-full transition-all"
                        style={{ width: `${barWidth}%` }}
                      />
                      <div
                        className="absolute top-0 right-0 h-full bg-green-500 rounded-full transition-all"
                        style={{ width: `${lesson.started_users > 0 ? (lesson.completed_users / maxUsers) * 100 : 0}%` }}
                      />
                    </div>

                    {/* Quiz stats */}
                    {lesson.quiz_stats && (
                      <div className="flex gap-3 mt-1 text-xs text-gray-400">
                        <span>کوئیز: {lesson.quiz_stats.attempts} تلاش</span>
                        <span>قبول: {lesson.quiz_stats.passed}</span>
                        <span>رد: {lesson.quiz_stats.attempts - lesson.quiz_stats.passed}</span>
                      </div>
                    )}
                  </div>

                  <span className="text-gray-400 text-sm flex-shrink-0">
                    {expandedLesson === lesson.id ? '▲' : '▼'}
                  </span>
                </div>
              </div>

              {/* Expanded: users at this lesson */}
              {expandedLesson === lesson.id && (
                <div className="bg-gray-50 rounded-b-xl border border-t-0 p-4 -mt-1">
                  {loadingUsers ? (
                    <div className="text-center py-4 text-gray-500 text-sm">در حال بارگذاری...</div>
                  ) : lessonUsers?.users?.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-gray-500 border-b">
                            <th className="px-3 py-2 text-right font-medium">کاربر</th>
                            <th className="px-3 py-2 text-right font-medium">پلتفرم</th>
                            <th className="px-3 py-2 text-right font-medium">شروع</th>
                            <th className="px-3 py-2 text-right font-medium">تکمیل</th>
                            {lessonUsers.lesson?.has_quiz && (
                              <th className="px-3 py-2 text-right font-medium">کوئیز</th>
                            )}
                            {lessonUsers.lesson?.has_form && (
                              <th className="px-3 py-2 text-right font-medium">فرم</th>
                            )}
                            <th className="px-3 py-2 text-right font-medium">عملیات</th>
                          </tr>
                        </thead>
                        <tbody>
                          {lessonUsers.users.map((u) => (
                            <tr key={u.id} className="border-b border-gray-200 hover:bg-white">
                              <td className="px-3 py-2">
                                <span className="font-medium">{u.first_name || '—'}</span>
                                {u.last_name && <span className="text-gray-500 mr-1">{u.last_name}</span>}
                                {u.username && <span className="text-gray-400 text-xs mr-2" dir="ltr">@{u.username}</span>}
                              </td>
                              <td className="px-3 py-2">
                                <span className={`text-xs px-1.5 py-0.5 rounded-full ${u.platform === 'telegram' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                                  {u.platform}
                                </span>
                              </td>
                              <td className="px-3 py-2 text-xs text-gray-500">
                                {u.started_at ? new Date(u.started_at).toLocaleString('fa-IR') : '—'}
                              </td>
                              <td className="px-3 py-2 text-xs">
                                {u.completed_at ? (
                                  <span className="text-green-600">✅ {new Date(u.completed_at).toLocaleString('fa-IR')}</span>
                                ) : u.is_current ? (
                                  <span className="text-amber-600">⏳ هم‌اکنون اینجا</span>
                                ) : (
                                  <span className="text-gray-400">—</span>
                                )}
                              </td>
                              {lessonUsers.lesson?.has_quiz && (
                                <td className="px-3 py-2 text-xs">
                                  {u.quiz ? (
                                    <span className={u.quiz.passed ? 'text-green-600' : 'text-red-600'}>
                                      {u.quiz.passed ? '✅' : '❌'} {Math.round(u.quiz.score)}%
                                    </span>
                                  ) : (
                                    <span className="text-gray-400">—</span>
                                  )}
                                </td>
                              )}
                              {lessonUsers.lesson?.has_form && (
                                <td className="px-3 py-2 text-xs">
                                  {u.form ? (
                                    <span className="text-green-600">✅ پر شده</span>
                                  ) : (
                                    <span className="text-gray-400">—</span>
                                  )}
                                </td>
                              )}
                              <td className="px-3 py-2">
                                <Link
                                  to={`/users/${u.id}`}
                                  className="text-xs text-blue-600 hover:underline"
                                >
                                  مشاهده پروفایل
                                </Link>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-4 text-gray-400 text-sm">هیچ کاربری در این درس وجود ندارد</div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {data.lessons.length === 0 && (
        <div className="text-center py-16 bg-white rounded-xl border">
          <div className="text-4xl mb-3">📭</div>
          <p className="text-gray-400">هیچ درسی یافت نشد</p>
        </div>
      )}
    </div>
  );
}
