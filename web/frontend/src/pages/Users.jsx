import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { users } from '../api';

export default function Users() {
  const [data, setData] = useState({ items: [], total: 0, page: 1, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [platformFilter, setPlatformFilter] = useState('');

  const load = (p = page, s = search, st = statusFilter, pl = platformFilter) => {
    setLoading(true);
    const params = { page: p, per_page: 50 };
    if (s) params.search = s;
    if (st) params.status = st;
    if (pl) params.platform = pl;
    users.list(params)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    load(1, search, statusFilter, platformFilter);
  };

  const handlePage = (p) => {
    setPage(p);
    load(p, search, statusFilter, platformFilter);
  };

  const handleStatusFilter = (st) => {
    setStatusFilter(st);
    setPage(1);
    load(1, search, st, platformFilter);
  };

  const handlePlatformFilter = (pl) => {
    setPlatformFilter(pl);
    setPage(1);
    load(1, search, statusFilter, pl);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">👥 مدیریت کاربران</h1>
        <span className="text-sm text-gray-500">{data.total} کاربر</span>
      </div>

      {/* Search + Filters */}
      <div className="mb-4 flex flex-wrap gap-2">
        <form onSubmit={handleSearch} className="flex gap-2 flex-1 min-w-[250px]">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="جستجو بر اساس نام، یوزرنیم یا شناسه..."
          />
          <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            🔍 جستجو
          </button>
        </form>
        <select
          value={statusFilter}
          onChange={(e) => handleStatusFilter(e.target.value)}
          className="px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
        >
          <option value="">همه وضعیت‌ها</option>
          <option value="active">فعال</option>
          <option value="completed">تکمیل شده</option>
          <option value="inactive">غیرفعال</option>
        </select>
        <select
          value={platformFilter}
          onChange={(e) => handlePlatformFilter(e.target.value)}
          className="px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
        >
          <option value="">همه پلتفرم‌ها</option>
          <option value="telegram">تلگرام</option>
          <option value="bale">بله</option>
        </select>
      </div>

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
                <th className="px-4 py-3 text-right font-medium text-gray-600">پیشرفت</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">مسئول</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">امتیاز</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">تاریخ ثبت‌نام</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">عملیات</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((u) => (
                <tr key={u.id} className="border-b hover:bg-gray-50 transition">
                  <td className="px-4 py-3">
                    <Link to={`/users/${u.id}`} className="hover:text-blue-600 transition">
                      <span className="font-medium">{u.first_name || '—'}</span>
                      {u.last_name && <span className="text-gray-500 mr-1">{u.last_name}</span>}
                    </Link>
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
                  <td className="px-4 py-3">
                    {u.progress_summary ? (
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-green-500 h-2 rounded-full"
                            style={{ width: `${u.progress_summary.total > 0 ? (u.progress_summary.completed / u.progress_summary.total) * 100 : 0}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-500">
                          {u.progress_summary.completed}/{u.progress_summary.total}
                        </span>
                      </div>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">{u.assigned_owner_name || '—'}</td>
                  <td className="px-4 py-3 font-mono">{u.lead_score}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString('fa-IR') : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/users/${u.id}`}
                      className="px-3 py-1.5 bg-blue-50 text-blue-600 rounded-lg text-xs hover:bg-blue-100 transition inline-block"
                    >
                      📋 جزئیات
                    </Link>
                  </td>
                </tr>
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
