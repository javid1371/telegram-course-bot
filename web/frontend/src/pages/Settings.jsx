import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { settings } from '../api';

const TABS = [
  { id: 'company', label: '🏢 اطلاعات شرکت' },
  { id: 'webhooks', label: '🔗 وب‌هوک‌ها' },
  { id: 'texts', label: '💬 متون ربات' },
  { id: 'scoring', label: '📊 امتیازدهی' },
];

/* ── Company Info Tab ────────────────────── */

function CompanyTab() {
  const [data, setData] = useState({});
  const [labels, setLabels] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    settings.getCompany()
      .then((res) => {
        setData(res.settings || {});
        setLabels(res.labels || {});
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const items = Object.entries(data).map(([key, value]) => ({ key, value: value || '' }));
      await settings.updateCompany(items);
      toast.success('اطلاعات شرکت ذخیره شد');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-center py-10 text-gray-400">در حال بارگذاری...</div>;

  const keys = Object.keys(labels);

  return (
    <div className="space-y-4">
      {keys.map((key) => (
        <div key={key}>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {labels[key]}
          </label>
          {key === 'extra_info' || key === 'address' ? (
            <textarea
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              rows={3}
              value={data[key] || ''}
              onChange={(e) => setData({ ...data, [key]: e.target.value })}
            />
          ) : (
            <input
              type={key === 'sales_trigger_lesson' ? 'number' : 'text'}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              value={data[key] || ''}
              onChange={(e) => setData({ ...data, [key]: e.target.value })}
              placeholder={key === 'sales_trigger_lesson' ? 'مثلاً: 3' : ''}
            />
          )}
        </div>
      ))}

      <button
        onClick={handleSave}
        disabled={saving}
        className="mt-4 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
      >
        {saving ? 'ذخیره...' : '💾 ذخیره تغییرات'}
      </button>
    </div>
  );
}


/* ── Webhooks Tab ────────────────────────── */

function WebhooksTab() {
  const [webhooks, setWebhooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState({ name: '', url: '', is_active: true, timeout: 10, retry_count: 3, events: '', headers: '' });
  const [showNew, setShowNew] = useState(false);

  const load = () => {
    setLoading(true);
    settings.getWebhooks()
      .then(setWebhooks)
      .catch((e) => toast.error(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const resetForm = () => {
    setForm({ name: '', url: '', is_active: true, timeout: 10, retry_count: 3, events: '', headers: '' });
    setEditId(null);
    setShowNew(false);
  };

  const handleEdit = (w) => {
    setEditId(w.id);
    setShowNew(true);
    setForm({
      name: w.name || '',
      url: w.url || '',
      is_active: w.is_active !== false,
      timeout: w.timeout || 10,
      retry_count: w.retry_count || 3,
      events: w.events ? JSON.stringify(w.events) : '',
      headers: w.headers ? JSON.stringify(w.headers) : '',
    });
  };

  const handleSave = async () => {
    try {
      const payload = {
        name: form.name,
        url: form.url,
        is_active: form.is_active,
        timeout: parseInt(form.timeout) || 10,
        retry_count: parseInt(form.retry_count) || 3,
        events: form.events ? JSON.parse(form.events) : null,
        headers: form.headers ? JSON.parse(form.headers) : null,
      };
      if (editId) {
        await settings.updateWebhook(editId, payload);
        toast.success('وب‌هوک بروزرسانی شد');
      } else {
        await settings.createWebhook(payload);
        toast.success('وب‌هوک جدید ایجاد شد');
      }
      resetForm();
      load();
    } catch (e) {
      toast.error(e.message || 'خطا در ذخیره');
    }
  };

  const handleDelete = async (id, name) => {
    if (!confirm(`آیا وب‌هوک «${name}» حذف شود؟`)) return;
    try {
      await settings.deleteWebhook(id);
      toast.success('وب‌هوک حذف شد');
      load();
    } catch (e) {
      toast.error(e.message);
    }
  };

  if (loading) return <div className="text-center py-10 text-gray-400">در حال بارگذاری...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-gray-500">{webhooks.length} وب‌هوک</span>
        <button
          onClick={() => { resetForm(); setShowNew(true); }}
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700"
        >
          ➕ وب‌هوک جدید
        </button>
      </div>

      {showNew && (
        <div className="bg-gray-50 rounded-lg p-4 mb-4 border space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="نام" className="border rounded px-3 py-2 text-sm" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input placeholder="URL" dir="ltr" className="border rounded px-3 py-2 text-sm" value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-gray-500">Timeout (s)</label>
              <input type="number" className="w-full border rounded px-3 py-2 text-sm" value={form.timeout}
                onChange={(e) => setForm({ ...form, timeout: e.target.value })} />
            </div>
            <div>
              <label className="text-xs text-gray-500">Retry</label>
              <input type="number" className="w-full border rounded px-3 py-2 text-sm" value={form.retry_count}
                onChange={(e) => setForm({ ...form, retry_count: e.target.value })} />
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
                فعال
              </label>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500">Events (JSON array)</label>
              <input dir="ltr" className="w-full border rounded px-3 py-2 text-sm font-mono" value={form.events}
                onChange={(e) => setForm({ ...form, events: e.target.value })} placeholder='["lesson_completed"]' />
            </div>
            <div>
              <label className="text-xs text-gray-500">Headers (JSON)</label>
              <input dir="ltr" className="w-full border rounded px-3 py-2 text-sm font-mono" value={form.headers}
                onChange={(e) => setForm({ ...form, headers: e.target.value })} placeholder='{"X-Token": "..."}' />
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <button onClick={handleSave} className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700">
              {editId ? '💾 بروزرسانی' : '✅ ایجاد'}
            </button>
            <button onClick={resetForm} className="px-4 py-2 bg-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-400">
              انصراف
            </button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {webhooks.map((w) => (
          <div key={w.id} className="flex items-center justify-between bg-white border rounded-lg px-4 py-3">
            <div className="flex items-center gap-3 min-w-0">
              <span className={`text-xs px-2 py-1 rounded-full font-bold ${w.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                {w.is_active ? '✅ فعال' : '⛔ غیرفعال'}
              </span>
              <div className="min-w-0">
                <div className="font-medium text-sm">{w.name}</div>
                <div dir="ltr" className="text-xs text-gray-400 truncate max-w-xs">{w.url}</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => handleEdit(w)} className="text-indigo-600 hover:text-indigo-800 text-sm">✏️</button>
              <button onClick={() => handleDelete(w.id, w.name)} className="text-red-500 hover:text-red-700 text-sm">🗑️</button>
            </div>
          </div>
        ))}
        {webhooks.length === 0 && <p className="text-center text-gray-400 py-6">وب‌هوکی تعریف نشده است</p>}
      </div>
    </div>
  );
}


/* ── Bot Texts Tab ───────────────────────── */

function BotTextsTab() {
  const [texts, setTexts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editId, setEditId] = useState(null);
  const [editValue, setEditValue] = useState('');

  useEffect(() => {
    settings.getBotTexts()
      .then(setTexts)
      .catch((e) => toast.error(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (id) => {
    try {
      await settings.updateBotText(id, editValue);
      toast.success('متن بروزرسانی شد');
      setTexts(texts.map((t) => (t.id === id ? { ...t, value: editValue } : t)));
      setEditId(null);
    } catch (e) {
      toast.error(e.message);
    }
  };

  if (loading) return <div className="text-center py-10 text-gray-400">در حال بارگذاری...</div>;

  if (texts.length === 0) {
    return <p className="text-center text-gray-400 py-10">هیچ متن سفارشی‌ تعریف نشده (از پنل ادمین ربات اضافه کنید)</p>;
  }

  // Group by category
  const groups = {};
  texts.forEach((t) => {
    if (!groups[t.category]) groups[t.category] = [];
    groups[t.category].push(t);
  });

  return (
    <div className="space-y-6">
      {Object.entries(groups).map(([cat, items]) => (
        <div key={cat}>
          <h3 className="text-sm font-bold text-gray-600 mb-2 border-b pb-1">📂 {cat}</h3>
          <div className="space-y-2">
            {items.map((t) => (
              <div key={t.id} className="bg-white border rounded-lg px-4 py-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-mono text-indigo-600">{t.key}</span>
                  <button
                    onClick={() => { setEditId(t.id); setEditValue(t.value); }}
                    className="text-indigo-500 hover:text-indigo-700 text-xs"
                  >
                    ✏️ ویرایش
                  </button>
                </div>
                {editId === t.id ? (
                  <div className="space-y-2">
                    <textarea
                      className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                      rows={4}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <button onClick={() => handleSave(t.id)} className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700">
                        💾 ذخیره
                      </button>
                      <button onClick={() => setEditId(null)} className="px-3 py-1 bg-gray-200 text-gray-600 text-xs rounded hover:bg-gray-300">
                        انصراف
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{t.value}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}


/* ── Scoring Rules Tab ───────────────────── */

function ScoringTab() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    settings.getScoringRules()
      .then(setRules)
      .catch((e) => toast.error(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleUpdate = async (id, field, value) => {
    try {
      await settings.updateScoringRule(id, { [field]: value });
      setRules(rules.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
      toast.success('قانون بروزرسانی شد');
    } catch (e) {
      toast.error(e.message);
    }
  };

  if (loading) return <div className="text-center py-10 text-gray-400">در حال بارگذاری...</div>;

  if (rules.length === 0) {
    return <p className="text-center text-gray-400 py-10">هیچ قانون امتیازدهی تعریف نشده</p>;
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-12 gap-2 text-xs text-gray-500 font-bold px-4 pb-1">
        <div className="col-span-4">رویداد</div>
        <div className="col-span-3">عنوان</div>
        <div className="col-span-2 text-center">امتیاز</div>
        <div className="col-span-2 text-center">وضعیت</div>
        <div className="col-span-1"></div>
      </div>
      {rules.map((r) => (
        <div key={r.id} className="grid grid-cols-12 gap-2 items-center bg-white border rounded-lg px-4 py-3">
          <div className="col-span-4 text-sm font-mono text-indigo-600 truncate">{r.event_type}</div>
          <div className="col-span-3 text-sm text-gray-700">{r.label || '—'}</div>
          <div className="col-span-2 text-center">
            <input
              type="number"
              className="w-16 border rounded px-2 py-1 text-sm text-center"
              value={r.points}
              onChange={(e) => {
                const pts = parseInt(e.target.value) || 0;
                setRules(rules.map((x) => (x.id === r.id ? { ...x, points: pts } : x)));
              }}
              onBlur={(e) => handleUpdate(r.id, 'points', parseInt(e.target.value) || 0)}
            />
          </div>
          <div className="col-span-2 text-center">
            <button
              onClick={() => handleUpdate(r.id, 'is_active', !r.is_active)}
              className={`text-xs px-3 py-1 rounded-full font-bold ${r.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}
            >
              {r.is_active ? '✅ فعال' : '⛔ غیرفعال'}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}


/* ── Main Settings Page ──────────────────── */

export default function Settings() {
  const [tab, setTab] = useState('company');

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">⚙️ تنظیمات</h1>

      {/* Tab Buttons */}
      <div className="flex gap-2 mb-6 border-b pb-3 flex-wrap">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm rounded-lg transition-colors ${
              tab === t.id
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        {tab === 'company' && <CompanyTab />}
        {tab === 'webhooks' && <WebhooksTab />}
        {tab === 'texts' && <BotTextsTab />}
        {tab === 'scoring' && <ScoringTab />}
      </div>
    </div>
  );
}
