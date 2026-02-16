import { useState, useEffect } from 'react';
import { users } from '../api';

export default function Users() {
  const [data, setData] = useState({ items: [], total: 0, page: 1, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState(null);
  const [expandedUser, setExpandedUser] = useState(null);

  const load = (p = page, s = search) => {
    setLoading(true);
    const params = { page: p, per_page: 50 };
    if (s) params.search = s;
    users.list(params)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    load(1, search);
  };

  const handlePage = (p) => {
    setPage(p);
    load(p, search);
  };

  const toggleExpand = async (userId) => {
    if (expandedId === userId) {
      setExpandedId(null);
      setExpandedUser(null);
      return;
    }
    try {
      const u = await users.get(userId);
      setExpandedId(userId);
      setExpandedUser(u);
    } catch {
      // ignore
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">👥 مدیریت کاربران</h1>
        <span className="text-sm text-gray-500">{data.total} کاربر</span>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="mb-4 flex gap-2">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          placeholder="جستجو بر اساس نام یا یوزرنیم..."
        />
        <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
          🔍 جستجو
        </button>
      </form>

      {/* User list */}
      {loading ? (
        <div className="text-center py-10 text-gray-500">در حال بارگذاری...</div>
      ) : data.items.length === 0 ? (
        <div className="text-center py-10 text-gray-400">کاربری یافت نشد</div>
      ) : (
        <div className="bg-white rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-right font-medium text-gray-600">نام</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">یوزرنیم</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">پلتفرم</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">وضعیت</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">امتیاز</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">تاریخ ثبت‌نام</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">عملیات</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((u) => (
                <>
                  <tr key={u.id} className="border-b hover:bg-gray-50 transition">
                    <td className="px-4 py-3">
                      <span className="font-medium">{u.first_name || '—'}</span>
                      {u.last_name && <span className="text-gray-500 mr-1">{u.last_name}</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-500" dir="ltr">{u.username ? `@${u.username}` : '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${u.platform === 'telegram' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                        {u.platform}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {u.is_completed ? (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">تکمیل</span>
                      ) : u.is_active ? (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">فعال</span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">غیرفعال</span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono">{u.lead_score}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString('fa-IR') : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleExpand(u.id)}
                        className="px-2 py-1 bg-gray-100 rounded text-xs hover:bg-gray-200 transition"
                      >
                        {expandedId === u.id ? '▲ بستن' : '▼ جزئیات'}
                      </button>
                    </td>
                  </tr>
                  {expandedId === u.id && expandedUser && (
                    <tr key={`${u.id}-details`}>
                      <td colSpan={7} className="px-6 py-4 bg-gray-50">
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                          <div>
                            <span className="text-gray-500">شناسه تلگرام:</span>
                            <span className="mr-2 font-mono" dir="ltr">{expandedUser.telegram_user_id}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">دوره فعلی:</span>
                            <span className="mr-2">{expandedUser.current_course_id || '—'}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">درس فعلی:</span>
                            <span className="mr-2">{expandedUser.current_lesson_id || '—'}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">مسئول فروش:</span>
                            <span className="mr-2">{expandedUser.assigned_owner_name || '—'}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">تگ‌ها:</span>
                            <span className="mr-2">{expandedUser.tags?.join(', ') || '—'}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">آخرین فعالیت:</span>
                            <span className="mr-2 text-xs">
                              {expandedUser.last_activity_at ? new Date(expandedUser.last_activity_at).toLocaleString('fa-IR') : '—'}
                            </span>
                          </div>
                          {expandedUser.registration_data && (
                            <div className="col-span-full">
                              <span className="text-gray-500">اطلاعات ثبت‌نام:</span>
                              <div className="mt-1 bg-white p-3 rounded border text-xs font-mono" dir="ltr">
                                {JSON.stringify(expandedUser.registration_data, null, 2)}
                              </div>
                            </div>
                          )}
                          {expandedUser.progress?.length > 0 && (
                            <div className="col-span-full">
                              <span className="text-gray-500">پیشرفت ({expandedUser.progress.length} درس):</span>
                              <div className="mt-1 flex flex-wrap gap-1">
                                {expandedUser.progress.map((p, i) => (
                                  <span
                                    key={i}
                                    className={`text-xs px-2 py-0.5 rounded ${p.completed_at ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}
                                  >
                                    درس {p.lesson_id} {p.completed_at ? '✅' : '⏳'}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          {data.pages > 1 && (
            <div className="flex items-center justify-center gap-2 p-4 border-t">
              <button
                onClick={() => handlePage(page - 1)}
                disabled={page <= 1}
                className="px-3 py-1 rounded border text-sm disabled:opacity-50 hover:bg-gray-50"
              >
                قبلی
              </button>
              <span className="text-sm text-gray-500">
                صفحه {page} از {data.pages}
              </span>
              <button
                onClick={() => handlePage(page + 1)}
                disabled={page >= data.pages}
                className="px-3 py-1 rounded border text-sm disabled:opacity-50 hover:bg-gray-50"
              >
                بعدی
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
