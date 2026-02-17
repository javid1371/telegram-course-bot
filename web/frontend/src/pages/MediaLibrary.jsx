import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { media } from '../api';

const TYPE_ICONS = {
  video: '🎬',
  audio: '🎵',
  voice: '🎙',
  photo: '🖼',
  document: '📎',
};

const TYPE_LABELS = {
  video: 'ویدیو',
  audio: 'صدا',
  voice: 'ویس',
  photo: 'عکس',
  document: 'فایل',
};

function formatSize(bytes) {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatDuration(secs) {
  if (!secs) return null;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return new Intl.DateTimeFormat('fa-IR', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  }).format(d);
}

export default function MediaLibrary() {
  const [files, setFiles] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [search, setSearch] = useState('');
  const [platform, setPlatform] = useState({ platform: '', label: '' });

  const load = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filter) params.file_type = filter;
      if (search) params.search = search;
      const data = await media.list(params);
      setFiles(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    media.platform().then(setPlatform).catch(() => {});
    load();
  }, [filter]);

  const handleSearch = (e) => {
    e.preventDefault();
    load();
  };

  const handleDelete = async (id, name) => {
    if (!confirm(`آیا فایل «${name}» حذف شود؟`)) return;
    try {
      await media.delete(id);
      toast.success(`فایل «${name}» حذف شد`);
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">📁 کتابخانه فایل‌ها</h1>
        <div className="flex items-center gap-3">
          {platform.label && (
            <span className={`px-3 py-1 rounded-full text-xs font-bold ${
              platform.platform === 'telegram' ? 'bg-blue-100 text-blue-700' : 'bg-orange-100 text-orange-700'
            }`}>
              {platform.platform === 'telegram' ? '📱' : '💬'} {platform.label}
            </span>
          )}
          <span className="text-sm text-gray-500">{total} فایل</span>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
        <p className="text-sm text-blue-800">
          <strong>📌 نحوه افزودن فایل:</strong> فایل‌های خود را مستقیماً در چت بات {platform.label || 'تلگرام/بله'} ارسال کنید.
          ابتدا دکمه «📁 کتابخانه فایل‌ها» را بزنید، سپس فایل بفرستید.
        </p>
        <p className="text-xs text-blue-600 mt-1">
          ⚠️ فایل‌های هر پلتفرم جداگانه هستند — فایل آپلود شده در تلگرام فقط در پنل تلگرام نمایش داده می‌شود و بالعکس.
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap items-center">
        <form onSubmit={handleSearch} className="flex gap-2 flex-1 min-w-[200px]">
          <input
            type="text"
            className="flex-1 border rounded-lg px-3 py-2 text-sm"
            placeholder="جستجو نام فایل..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit" className="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600">
            🔍
          </button>
        </form>
        <div className="flex gap-1 flex-wrap">
          <button
            onClick={() => setFilter('')}
            className={`px-3 py-1.5 rounded-full text-xs transition ${!filter ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
          >
            همه
          </button>
          {Object.entries(TYPE_LABELS).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`px-3 py-1.5 rounded-full text-xs transition ${filter === key ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {TYPE_ICONS[key]} {label}
            </button>
          ))}
        </div>
      </div>

      {/* File List */}
      {loading ? (
        <div className="text-center py-12 text-gray-400">در حال بارگذاری...</div>
      ) : files.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg border">
          <p className="text-4xl mb-3">📭</p>
          <p className="text-gray-500">هنوز فایلی آپلود نشده</p>
          <p className="text-sm text-gray-400 mt-1">
            فایل‌ها رو از چت بات تلگرام/بله بفرستید (دکمه «📁 کتابخانه فایل‌ها»)
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-gray-600 text-xs">
                <th className="text-right p-3">نوع</th>
                <th className="text-right p-3">نام فایل</th>
                <th className="text-right p-3">حجم</th>
                <th className="text-right p-3">مدت</th>
                <th className="text-right p-3">تاریخ</th>
                <th className="text-right p-3">عملیات</th>
              </tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.id} className="border-t hover:bg-gray-50 transition">
                  <td className="p-3 text-lg">{TYPE_ICONS[f.file_type] || '📎'}</td>
                  <td className="p-3">
                    <p className="font-medium text-gray-800 truncate max-w-[250px]">{f.name}</p>
                    <p className="text-xs text-gray-400 font-mono truncate max-w-[250px]" dir="ltr">
                      {f.file_id?.slice(0, 30)}...
                    </p>
                  </td>
                  <td className="p-3 text-gray-600">{formatSize(f.file_size)}</td>
                  <td className="p-3 text-gray-600">{formatDuration(f.duration) || '—'}</td>
                  <td className="p-3 text-gray-500 text-xs">{formatDate(f.created_at)}</td>
                  <td className="p-3">
                    <div className="flex gap-1">
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(f.file_id);
                          toast.success('file_id کپی شد');
                        }}
                        className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs hover:bg-gray-200"
                        title="کپی file_id"
                      >
                        📋
                      </button>
                      <button
                        onClick={() => handleDelete(f.id, f.name)}
                        className="px-2 py-1 bg-red-50 text-red-700 rounded text-xs hover:bg-red-100"
                        title="حذف"
                      >
                        🗑️
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
