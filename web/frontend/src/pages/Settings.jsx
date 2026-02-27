import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { settings } from '../api';

const TABS = [
  { id: 'company', label: '🏢 اطلاعات شرکت' },
  { id: 'webhooks', label: '🔗 وب‌هوک‌ها' },
  { id: 'texts', label: '💬 متون ربات' },
  { id: 'scoring', label: '📊 امتیازدهی' },
  { id: 'engagement', label: '🔥 تعامل و SMS' },
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


/* ── Available Bot Events ────────────────── */

const EVENT_GROUPS = [
  {
    label: '👤 کاربر / لید',
    events: [
      { key: 'lead.register',      label: 'ثبت‌نام کاربر جدید',         icon: '📝' },
    ],
  },
  {
    label: '📚 درس',
    events: [
      { key: 'lesson.open',        label: 'ارسال درس به کاربر',         icon: '📤' },
      { key: 'lesson.confirm',     label: 'تأیید دریافت درس',           icon: '✅' },
      { key: 'lesson.complete',    label: 'تکمیل درس',                 icon: '🏁' },
    ],
  },
  {
    label: '🎓 دوره',
    events: [
      { key: 'course.select',     label: 'انتخاب دوره',                icon: '📌' },
      { key: 'course.complete',   label: 'اتمام دوره',                 icon: '🎉' },
    ],
  },
  {
    label: '📋 فرم و کوییز',
    events: [
      { key: 'form.submit',       label: 'ارسال فرم',                  icon: '📋' },
      { key: 'quiz.start',        label: 'شروع کوییز',                 icon: '❓' },
      { key: 'quiz.pass',         label: 'قبولی در کوییز',             icon: '🟢' },
      { key: 'quiz.fail',         label: 'عدم قبولی در کوییز',         icon: '🔴' },
    ],
  },
  {
    label: '⚙️ سیستم',
    events: [
      { key: 'speed.change',      label: 'تغییر سرعت (2x / فَست‌ترک)', icon: '⚡' },
      { key: 'reminder.sent',     label: 'ارسال یادآوری',              icon: '🔔' },
      { key: 'inactivity.timeout', label: 'عدم فعالیت (48 ساعت+)',     icon: '⏰' },
    ],
  },
];

const ALL_EVENT_KEYS = EVENT_GROUPS.flatMap((g) => g.events.map((e) => e.key));

/* ── Event Picker Component ─────────────── */

function EventPicker({ selected, onChange }) {
  const isAllSelected = !selected || selected.length === 0;

  const toggleAll = () => {
    onChange(isAllSelected ? [...ALL_EVENT_KEYS] : []);
  };

  const toggleEvent = (key) => {
    if (isAllSelected) {
      // switching from "all" to specific: select all except this one
      onChange(ALL_EVENT_KEYS.filter((k) => k !== key));
    } else if (selected.includes(key)) {
      const next = selected.filter((k) => k !== key);
      onChange(next.length === 0 ? [] : next); // empty = all
      return;
    } else {
      const next = [...selected, key];
      // if all selected, switch back to "all" mode
      onChange(next.length >= ALL_EVENT_KEYS.length ? [] : next);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-xs text-gray-500 font-medium">رویدادهای ارسالی</label>
        <button
          type="button"
          onClick={toggleAll}
          className={`text-xs px-3 py-1 rounded-full font-bold transition-colors ${
            isAllSelected
              ? 'bg-indigo-100 text-indigo-700'
              : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
          }`}
        >
          {isAllSelected ? '📡 همه رویدادها' : `${selected.length} از ${ALL_EVENT_KEYS.length} رویداد`}
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {EVENT_GROUPS.map((group) => (
          <div key={group.label} className="bg-white border rounded-lg p-2">
            <div className="text-xs font-bold text-gray-500 mb-1.5 px-1">{group.label}</div>
            <div className="space-y-1">
              {group.events.map((ev) => {
                const checked = isAllSelected || (selected && selected.includes(ev.key));
                return (
                  <label
                    key={ev.key}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-sm transition-colors ${
                      checked ? 'bg-indigo-50 text-indigo-800' : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleEvent(ev.key)}
                      className="accent-indigo-600"
                    />
                    <span>{ev.icon}</span>
                    <span className="flex-1">{ev.label}</span>
                    <span dir="ltr" className="text-[10px] font-mono text-gray-400">{ev.key}</span>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}


/* ── Webhooks Tab ────────────────────────── */

function WebhooksTab() {
  const [webhooks, setWebhooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState({
    name: '', url: '', is_active: true, timeout: 10, retry_count: 3,
    events: [],  // [] = all events
    headers: '',
  });
  const [showNew, setShowNew] = useState(false);
  const [testing, setTesting] = useState(null); // webhook id being tested

  const load = () => {
    setLoading(true);
    settings.getWebhooks()
      .then(setWebhooks)
      .catch((e) => toast.error(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const resetForm = () => {
    setForm({ name: '', url: '', is_active: true, timeout: 10, retry_count: 3, events: [], headers: '' });
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
      events: Array.isArray(w.events) ? w.events : [],
      headers: w.headers ? JSON.stringify(w.headers) : '',
    });
  };

  const handleSave = async () => {
    if (!form.name || !form.url) {
      toast.error('نام و URL الزامی است');
      return;
    }
    try {
      const payload = {
        name: form.name,
        url: form.url,
        is_active: form.is_active,
        timeout: parseInt(form.timeout) || 10,
        retry_count: parseInt(form.retry_count) || 3,
        events: form.events && form.events.length > 0 ? form.events : null,
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

  const handleTest = async (id) => {
    setTesting(id);
    try {
      const res = await settings.testWebhook(id);
      if (res.success) {
        toast.success(`✅ تست موفق — ${res.detail}`);
      } else {
        toast.error(`❌ تست ناموفق — ${res.detail}`);
      }
    } catch (e) {
      toast.error(e.message || 'خطا در تست');
    } finally {
      setTesting(null);
    }
  };

  // Build event label lookup
  const eventLabelMap = {};
  EVENT_GROUPS.forEach((g) => g.events.forEach((e) => { eventLabelMap[e.key] = `${e.icon} ${e.label}`; }));

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
            <input placeholder="نام (مثلاً: n8n-crm)" className="border rounded px-3 py-2 text-sm" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input placeholder="https://n8n.example.com/webhook/..." dir="ltr" className="border rounded px-3 py-2 text-sm" value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-gray-500">Timeout (ثانیه)</label>
              <input type="number" className="w-full border rounded px-3 py-2 text-sm" value={form.timeout}
                onChange={(e) => setForm({ ...form, timeout: e.target.value })} />
            </div>
            <div>
              <label className="text-xs text-gray-500">تعداد تلاش مجدد</label>
              <input type="number" className="w-full border rounded px-3 py-2 text-sm" value={form.retry_count}
                onChange={(e) => setForm({ ...form, retry_count: e.target.value })} />
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.is_active} className="accent-indigo-600"
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
                فعال
              </label>
            </div>
          </div>

          {/* Event Picker */}
          <EventPicker
            selected={form.events}
            onChange={(events) => setForm({ ...form, events })}
          />

          <div>
            <label className="text-xs text-gray-500">هدرهای سفارشی (JSON)</label>
            <input dir="ltr" className="w-full border rounded px-3 py-2 text-sm font-mono" value={form.headers}
              onChange={(e) => setForm({ ...form, headers: e.target.value })} placeholder='{"X-Token": "..."}' />
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

      <div className="space-y-3">
        {webhooks.map((w) => (
          <div key={w.id} className="bg-white border rounded-lg px-4 py-3 space-y-2">
            {/* Header row */}
            <div className="flex items-center justify-between">
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
                <button
                  onClick={() => handleTest(w.id)}
                  disabled={testing === w.id}
                  className="text-xs px-3 py-1 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 disabled:opacity-50"
                >
                  {testing === w.id ? '⏳' : '🧪 تست'}
                </button>
                <button onClick={() => handleEdit(w)} className="text-indigo-600 hover:text-indigo-800 text-sm">✏️</button>
                <button onClick={() => handleDelete(w.id, w.name)} className="text-red-500 hover:text-red-700 text-sm">🗑️</button>
              </div>
            </div>
            {/* Event tags */}
            <div className="flex flex-wrap gap-1">
              {(!w.events || w.events.length === 0) ? (
                <span className="text-[11px] bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">📡 همه رویدادها</span>
              ) : (
                w.events.map((ev) => (
                  <span key={ev} className="text-[11px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                    {eventLabelMap[ev] || ev}
                  </span>
                ))
              )}
              <span className="text-[11px] text-gray-400 px-1">• timeout: {w.timeout}s • retry: {w.retry_count}x</span>
            </div>
          </div>
        ))}
        {webhooks.length === 0 && (
          <div className="text-center py-10 text-gray-400">
            <p className="text-lg mb-2">🔗</p>
            <p>هیچ وب‌هوکی تعریف نشده</p>
            <p className="text-xs mt-1">برای اتصال بات به CRM یا n8n، یک وب‌هوک جدید اضافه کنید</p>
          </div>
        )}
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
/* ── Engagement & SMS Tab ──────────────── */

function EngagementSmsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    settings.getSmsStatus()
      .then(setData)
      .catch((e) => toast.error(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-10 text-gray-400">در حال بارگذاری...</div>;
  if (!data) return <div className="text-center py-10 text-red-400">خطا در دریافت اطلاعات</div>;

  const sms = data.sms;
  const engagement = data.engagement;

  return (
    <div className="space-y-6">
      {/* SMS Status */}
      <div>
        <h3 className="font-bold text-gray-700 mb-3">📱 وضعیت SMS (کاوه‌نگار)</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className="bg-white border rounded-lg p-4 text-center">
            <div className={`text-lg font-bold ${sms.enabled ? 'text-green-600' : 'text-red-600'}`}>
              {sms.enabled ? '✅ فعال' : '⛔ غیرفعال'}
            </div>
            <div className="text-xs text-gray-500 mt-1">وضعیت سرویس</div>
          </div>
          <div className="bg-white border rounded-lg p-4 text-center">
            <div className={`text-lg font-bold ${sms.configured ? 'text-green-600' : 'text-red-600'}`}>
              {sms.configured ? '✅ پیکربندی شده' : '❌ بدون API Key'}
            </div>
            <div className="text-xs text-gray-500 mt-1">کلید API</div>
          </div>
          <div className="bg-white border rounded-lg p-4 text-center">
            <div className="text-lg font-bold text-blue-600">{sms.total_sent?.toLocaleString('fa-IR')}</div>
            <div className="text-xs text-gray-500 mt-1">کل ارسال‌شده</div>
          </div>
          <div className="bg-white border rounded-lg p-4 text-center">
            <div className="text-lg font-bold text-purple-600">****{sms.sender}</div>
            <div className="text-xs text-gray-500 mt-1">شماره ارسال</div>
          </div>
        </div>

        {/* SMS Tiers */}
        <div className="bg-gray-50 rounded-lg border p-4">
          <h4 className="text-sm font-bold text-gray-600 mb-2">سطوح ارسال SMS</h4>
          <div className="space-y-2">
            {sms.tiers.map((tier, i) => (
              <div key={i} className="flex items-center gap-3 bg-white rounded-lg px-3 py-2 border text-sm">
                <span className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs">{i + 1}</span>
                <span className="font-medium">{tier.name}</span>
                <span className="text-gray-500">—</span>
                <span className="text-gray-600">{tier.description}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-gray-500">
            <span>📨 حداکثر: {sms.max_per_user} SMS برای هر کاربر</span>
            <span>📊 حداقل پیشرفت: {sms.min_progress}</span>
            <span>⏰ ساعات ارسال: {sms.sending_hours}</span>
          </div>
        </div>
      </div>

      {/* Engagement Stats */}
      <div>
        <h3 className="font-bold text-gray-700 mb-3">🔥 آمار تعامل</h3>
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-orange-700">{engagement.streak_users?.toLocaleString('fa-IR')}</div>
            <div className="text-xs text-orange-600 mt-1">کاربران با استریک فعال</div>
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-amber-700">{engagement.badge_users?.toLocaleString('fa-IR')}</div>
            <div className="text-xs text-amber-600 mt-1">دارندگان نشان</div>
          </div>
        </div>

        {/* Top Streaks Leaderboard */}
        {engagement.top_streaks?.length > 0 && (
          <div className="bg-white border rounded-lg overflow-hidden">
            <div className="bg-gray-50 px-4 py-2 border-b">
              <h4 className="text-sm font-bold text-gray-600">🏆 رتبه‌بندی استریک</h4>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-right text-gray-500">#</th>
                  <th className="px-4 py-2 text-right text-gray-500">نام</th>
                  <th className="px-4 py-2 text-center text-gray-500">🔥 فعلی</th>
                  <th className="px-4 py-2 text-center text-gray-500">⚡ بهترین</th>
                  <th className="px-4 py-2 text-center text-gray-500">🏅 نشان</th>
                </tr>
              </thead>
              <tbody>
                {engagement.top_streaks.map((u, i) => (
                  <tr key={i} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-2 font-bold text-gray-400">{i + 1}</td>
                    <td className="px-4 py-2 font-medium">{u.name}</td>
                    <td className="px-4 py-2 text-center">
                      {u.streak_days > 0 && <span className="px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 text-xs font-bold">{u.streak_days}</span>}
                    </td>
                    <td className="px-4 py-2 text-center">
                      <span className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 text-xs font-bold">{u.best_streak}</span>
                    </td>
                    <td className="px-4 py-2 text-center">
                      {u.badges_count > 0 && <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-bold">{u.badges_count}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}


/* ── Main Settings Page ────────────────────── */
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
        {tab === 'engagement' && <EngagementSmsTab />}
      </div>
    </div>
  );
}
