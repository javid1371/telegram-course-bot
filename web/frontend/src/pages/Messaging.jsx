import { useState, useEffect, useCallback } from 'react';
import { messaging, exports } from '../api';

const TARGET_OPTIONS = [
  { value: 'all', label: 'همه کاربران', icon: '👥' },
  { value: 'active', label: 'فعال‌ها', icon: '🟢' },
  { value: 'inactive', label: 'غیرفعال‌ها', icon: '🔴' },
  { value: 'completed', label: 'تمام‌کرده‌ها', icon: '✅' },
];

export default function Messaging() {
  // Broadcast form
  const [message, setMessage] = useState('');
  const [target, setTarget] = useState('all');
  const [tags, setTags] = useState('');
  const [previewCount, setPreviewCount] = useState(null);
  const [sending, setSending] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  // History
  const [history, setHistory] = useState([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Direct message
  const [dmUserId, setDmUserId] = useState('');
  const [dmMessage, setDmMessage] = useState('');
  const [dmSending, setDmSending] = useState(false);
  const [dmResult, setDmResult] = useState(null);

  // Active tab
  const [tab, setTab] = useState('broadcast');

  // Preview
  useEffect(() => {
    const timer = setTimeout(() => {
      messaging.broadcastPreview(target, tags)
        .then(r => setPreviewCount(r.count))
        .catch(() => setPreviewCount(null));
    }, 300);
    return () => clearTimeout(timer);
  }, [target, tags]);

  // Load history
  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const res = await messaging.broadcastHistory(historyPage, 10);
      setHistory(res.items);
      setHistoryTotal(res.total);
    } catch (e) {
      console.error(e);
    }
    setLoadingHistory(false);
  }, [historyPage]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // Send broadcast
  const handleBroadcast = async (e) => {
    e.preventDefault();
    if (!message.trim()) return;
    if (!confirm(`آیا از ارسال پیام گروهی به ${previewCount ?? '?'} کاربر اطمینان دارید؟`)) return;

    setSending(true);
    setLastResult(null);
    try {
      const tagList = tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : undefined;
      const res = await messaging.broadcast({ message, target, tags: tagList });
      setLastResult(res);
      setMessage('');
      setTimeout(loadHistory, 2000);
    } catch (err) {
      setLastResult({ error: err.message || 'خطا' });
    }
    setSending(false);
  };

  // Send DM
  const handleDM = async (e) => {
    e.preventDefault();
    if (!dmUserId || !dmMessage.trim()) return;
    setDmSending(true);
    setDmResult(null);
    try {
      const res = await messaging.sendDirect(dmUserId, dmMessage);
      setDmResult(res);
      setDmMessage('');
    } catch (err) {
      setDmResult({ error: err.message || 'خطا' });
    }
    setDmSending(false);
  };

  // Download export
  const handleExport = (type) => {
    let url;
    if (type === 'users') url = exports.users();
    else if (type === 'progress') url = exports.progress();
    else url = exports.analytics();

    const token = localStorage.getItem('token');
    // Open in new tab with auth
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    // We need to use fetch for auth
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob())
      .then(blob => {
        const blobUrl = URL.createObjectURL(blob);
        a.href = blobUrl;
        a.download = `${type}_export.xlsx`;
        a.click();
        URL.revokeObjectURL(blobUrl);
      })
      .catch(() => alert('خطا در دانلود فایل'));
  };

  const tabClass = (t) =>
    `px-4 py-2 rounded-t-lg font-medium text-sm transition-colors ${
      tab === t
        ? 'bg-white dark:bg-gray-800 text-blue-600 border-b-2 border-blue-600'
        : 'text-gray-500 hover:text-gray-700 dark:text-gray-400'
    }`;

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">📨 پیام‌رسانی و خروجی</h1>

      {/* Tabs */}
      <div className="flex gap-1 border-b dark:border-gray-700">
        <button className={tabClass('broadcast')} onClick={() => setTab('broadcast')}>
          📢 ارسال گروهی
        </button>
        <button className={tabClass('direct')} onClick={() => setTab('direct')}>
          ✉️ پیام شخصی
        </button>
        <button className={tabClass('history')} onClick={() => setTab('history')}>
          📋 تاریخچه ارسال
        </button>
        <button className={tabClass('export')} onClick={() => setTab('export')}>
          📥 خروجی اکسل
        </button>
      </div>

      {/* ── Broadcast Tab ── */}
      {tab === 'broadcast' && (
        <form onSubmit={handleBroadcast} className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 space-y-4">
          <h2 className="text-lg font-semibold">📢 ارسال پیام گروهی</h2>

          {/* Target */}
          <div>
            <label className="block text-sm font-medium mb-2">مخاطبان</label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {TARGET_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setTarget(opt.value)}
                  className={`p-3 rounded-lg border text-center transition-colors ${
                    target === opt.value
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                  }`}
                >
                  <div className="text-xl">{opt.icon}</div>
                  <div className="text-sm mt-1">{opt.label}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Tags filter */}
          <div>
            <label className="block text-sm font-medium mb-1">فیلتر تگ (اختیاری، جدا با کاما)</label>
            <input
              type="text"
              value={tags}
              onChange={e => setTags(e.target.value)}
              placeholder="مثال: vip, premium"
              className="w-full border rounded-lg px-3 py-2 dark:bg-gray-700 dark:border-gray-600"
            />
          </div>

          {/* Preview count */}
          {previewCount !== null && (
            <div className="bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 rounded-lg p-3 text-sm">
              👥 این پیام به <strong>{previewCount.toLocaleString('fa-IR')}</strong> کاربر ارسال خواهد شد
            </div>
          )}

          {/* Message */}
          <div>
            <label className="block text-sm font-medium mb-1">متن پیام</label>
            <textarea
              value={message}
              onChange={e => setMessage(e.target.value)}
              rows={5}
              placeholder="متن پیام را وارد کنید..."
              className="w-full border rounded-lg px-3 py-2 dark:bg-gray-700 dark:border-gray-600 resize-y"
              required
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={sending || !message.trim()}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {sending ? '⏳ در حال ارسال...' : '🚀 ارسال پیام'}
          </button>

          {/* Result */}
          {lastResult && (
            <div className={`rounded-lg p-3 text-sm ${
              lastResult.error
                ? 'bg-red-50 dark:bg-red-900/20 text-red-700'
                : 'bg-green-50 dark:bg-green-900/20 text-green-700'
            }`}>
              {lastResult.error
                ? `❌ ${lastResult.error}`
                : `✅ پیام در حال ارسال به ${lastResult.total_users} کاربر`}
            </div>
          )}
        </form>
      )}

      {/* ── Direct Message Tab ── */}
      {tab === 'direct' && (
        <form onSubmit={handleDM} className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 space-y-4">
          <h2 className="text-lg font-semibold">✉️ ارسال پیام شخصی</h2>

          <div>
            <label className="block text-sm font-medium mb-1">شناسه کاربر (ID عددی در سیستم)</label>
            <input
              type="number"
              value={dmUserId}
              onChange={e => setDmUserId(e.target.value)}
              placeholder="مثال: 42"
              className="w-full border rounded-lg px-3 py-2 dark:bg-gray-700 dark:border-gray-600"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              ID کاربر را از صفحه «کاربران» پیدا کنید یا مستقیماً از صفحه جزئیات کاربر پیام بفرستید.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">متن پیام</label>
            <textarea
              value={dmMessage}
              onChange={e => setDmMessage(e.target.value)}
              rows={4}
              placeholder="متن پیام شخصی..."
              className="w-full border rounded-lg px-3 py-2 dark:bg-gray-700 dark:border-gray-600 resize-y"
              required
            />
          </div>

          <button
            type="submit"
            disabled={dmSending || !dmUserId || !dmMessage.trim()}
            className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {dmSending ? '⏳ در حال ارسال...' : '📤 ارسال'}
          </button>

          {dmResult && (
            <div className={`rounded-lg p-3 text-sm ${
              dmResult.error
                ? 'bg-red-50 dark:bg-red-900/20 text-red-700'
                : 'bg-green-50 dark:bg-green-900/20 text-green-700'
            }`}>
              {dmResult.error ? `❌ ${dmResult.error}` : `✅ ${dmResult.detail}`}
            </div>
          )}
        </form>
      )}

      {/* ── History Tab ── */}
      {tab === 'history' && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold">📋 تاریخچه ارسال گروهی</h2>
            <button onClick={loadHistory} className="text-blue-600 text-sm hover:underline">
              🔄 بروزرسانی
            </button>
          </div>

          {loadingHistory ? (
            <div className="text-center py-8 text-gray-500">در حال بارگذاری...</div>
          ) : history.length === 0 ? (
            <div className="text-center py-8 text-gray-500">هنوز پیام گروهی ارسال نشده</div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-700">
                    <tr>
                      <th className="px-3 py-2 text-right">#</th>
                      <th className="px-3 py-2 text-right">متن</th>
                      <th className="px-3 py-2 text-center">مخاطبان</th>
                      <th className="px-3 py-2 text-center">کل</th>
                      <th className="px-3 py-2 text-center">موفق</th>
                      <th className="px-3 py-2 text-center">ناموفق</th>
                      <th className="px-3 py-2 text-center">وضعیت</th>
                      <th className="px-3 py-2 text-right">تاریخ</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y dark:divide-gray-700">
                    {history.map(log => (
                      <tr key={log.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                        <td className="px-3 py-2">{log.id}</td>
                        <td className="px-3 py-2 max-w-[200px] truncate" title={log.full_message}>
                          {log.message}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-xs">
                            {TARGET_OPTIONS.find(o => o.value === log.target)?.label || log.target}
                          </span>
                          {log.tags && log.tags.length > 0 && (
                            <span className="bg-purple-100 text-purple-800 px-2 py-0.5 rounded text-xs mr-1">
                              {log.tags.join(', ')}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-center">{log.total_users}</td>
                        <td className="px-3 py-2 text-center text-green-600">{log.success_count ?? '—'}</td>
                        <td className="px-3 py-2 text-center text-red-600">{log.failed_count ?? '—'}</td>
                        <td className="px-3 py-2 text-center">
                          {log.is_done ? (
                            <span className="text-green-600">✅ تمام</span>
                          ) : (
                            <span className="text-yellow-600">⏳ در حال ارسال</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-500">
                          {log.started_at ? new Date(log.started_at).toLocaleString('fa-IR') : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {historyTotal > 10 && (
                <div className="flex justify-center gap-2 mt-4">
                  <button
                    onClick={() => setHistoryPage(p => Math.max(1, p - 1))}
                    disabled={historyPage === 1}
                    className="px-3 py-1 border rounded disabled:opacity-50"
                  >
                    قبلی
                  </button>
                  <span className="px-3 py-1 text-sm text-gray-500">
                    صفحه {historyPage} از {Math.ceil(historyTotal / 10)}
                  </span>
                  <button
                    onClick={() => setHistoryPage(p => p + 1)}
                    disabled={historyPage >= Math.ceil(historyTotal / 10)}
                    className="px-3 py-1 border rounded disabled:opacity-50"
                  >
                    بعدی
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Export Tab ── */}
      {tab === 'export' && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 space-y-4">
          <h2 className="text-lg font-semibold">📥 خروجی اکسل</h2>
          <p className="text-sm text-gray-500">فایل‌های اکسل برای گزارش‌گیری و تحلیل دقیق‌تر دانلود کنید.</p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <button
              onClick={() => handleExport('users')}
              className="flex flex-col items-center gap-2 p-6 border rounded-xl hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
            >
              <span className="text-3xl">👥</span>
              <span className="font-medium">لیست کاربران</span>
              <span className="text-xs text-gray-500">اطلاعات + ثبت‌نام + تگ‌ها</span>
            </button>

            <button
              onClick={() => handleExport('progress')}
              className="flex flex-col items-center gap-2 p-6 border rounded-xl hover:border-green-400 hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors"
            >
              <span className="text-3xl">📊</span>
              <span className="font-medium">پیشرفت دروس</span>
              <span className="text-xs text-gray-500">ماتریس پیشرفت هر کاربر</span>
            </button>

            <button
              onClick={() => handleExport('analytics')}
              className="flex flex-col items-center gap-2 p-6 border rounded-xl hover:border-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/20 transition-colors"
            >
              <span className="text-3xl">📈</span>
              <span className="font-medium">آمار تحلیلی</span>
              <span className="text-xs text-gray-500">آمار کلی + آمار هر درس</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
