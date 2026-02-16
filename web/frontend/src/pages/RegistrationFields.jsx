import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { registrationFields } from '../api';

const FIELD_TYPES = [
  { value: 'text', label: 'متن' },
  { value: 'number', label: 'عدد' },
  { value: 'email', label: 'ایمیل' },
  { value: 'phone', label: 'شماره تلفن' },
  { value: 'date', label: 'تاریخ' },
  { value: 'select', label: 'انتخابی' },
];

const EMPTY_FORM = {
  field_name: '',
  field_label: '',
  field_type: 'text',
  is_required: true,
  order: 0,
  validation_rule: '',
  options: null,
  is_active: true,
};

export default function RegistrationFieldsPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [selectOptions, setSelectOptions] = useState('');

  const load = () => {
    setLoading(true);
    registrationFields
      .list()
      .then(setItems)
      .catch(() => toast.error('خطا در دریافت فیلدها'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...EMPTY_FORM, order: items.length });
    setSelectOptions('');
    setShowForm(true);
  };

  const openEdit = (field) => {
    setEditingId(field.id);
    setForm({
      field_name: field.field_name,
      field_label: field.field_label,
      field_type: field.field_type,
      is_required: field.is_required,
      order: field.order,
      validation_rule: field.validation_rule || '',
      options: field.options,
      is_active: field.is_active,
    });
    setSelectOptions(
      field.options?.choices ? field.options.choices.join('\n') : ''
    );
    setShowForm(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    const payload = { ...form };

    // Build options for select type
    if (form.field_type === 'select' && selectOptions.trim()) {
      payload.options = {
        choices: selectOptions
          .split('\n')
          .map((s) => s.trim())
          .filter(Boolean),
      };
    } else if (form.field_type !== 'select') {
      payload.options = null;
    }

    if (!payload.validation_rule) payload.validation_rule = null;

    try {
      if (editingId) {
        await registrationFields.update(editingId, payload);
        toast.success('فیلد بروزرسانی شد');
      } else {
        await registrationFields.create(payload);
        toast.success('فیلد ایجاد شد');
      }
      setShowForm(false);
      setEditingId(null);
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleDelete = async (id, label) => {
    if (!confirm(`آیا از حذف فیلد «${label}» مطمئنید؟`)) return;
    try {
      await registrationFields.delete(id);
      toast.success('فیلد حذف شد');
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleToggleActive = async (field) => {
    try {
      await registrationFields.update(field.id, {
        is_active: !field.is_active,
      });
      toast.success(field.is_active ? 'فیلد غیرفعال شد' : 'فیلد فعال شد');
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const moveField = async (index, direction) => {
    const sorted = [...items];
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= sorted.length) return;

    // Swap orders
    const reorder = sorted.map((item, i) => ({
      id: item.id,
      order: i === index ? targetIndex : i === targetIndex ? index : i,
    }));

    try {
      await registrationFields.reorder(reorder);
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">📝 فیلدهای ثبت‌نام</h1>
        <button
          onClick={openCreate}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm"
        >
          ➕ فیلد جدید
        </button>
      </div>

      {/* Create/Edit form */}
      {showForm && (
        <form
          onSubmit={handleSave}
          className="bg-white rounded-xl border p-5 mb-6"
        >
          <h2 className="font-semibold mb-4">
            {editingId ? '✏️ ویرایش فیلد' : '➕ فیلد جدید'}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                نام فیلد (انگلیسی)
              </label>
              <input
                type="text"
                value={form.field_name}
                onChange={(e) =>
                  setForm({ ...form, field_name: e.target.value })
                }
                placeholder="مثلاً: full_name"
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-left"
                dir="ltr"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                برچسب فیلد (فارسی)
              </label>
              <input
                type="text"
                value={form.field_label}
                onChange={(e) =>
                  setForm({ ...form, field_label: e.target.value })
                }
                placeholder="مثلاً: نام و نام خانوادگی"
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                نوع فیلد
              </label>
              <select
                value={form.field_type}
                onChange={(e) =>
                  setForm({ ...form, field_type: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              >
                {FIELD_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                ترتیب
              </label>
              <input
                type="number"
                value={form.order}
                onChange={(e) =>
                  setForm({ ...form, order: parseInt(e.target.value) || 0 })
                }
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                قانون اعتبارسنجی (اختیاری)
              </label>
              <input
                type="text"
                value={form.validation_rule}
                onChange={(e) =>
                  setForm({ ...form, validation_rule: e.target.value })
                }
                placeholder="regex یا قانون اعتبارسنجی"
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-left"
                dir="ltr"
              />
            </div>
            <div className="flex items-center gap-6 pt-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_required}
                  onChange={(e) =>
                    setForm({ ...form, is_required: e.target.checked })
                  }
                  className="w-4 h-4 text-blue-600"
                />
                <span className="text-sm text-gray-700">اجباری</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) =>
                    setForm({ ...form, is_active: e.target.checked })
                  }
                  className="w-4 h-4 text-blue-600"
                />
                <span className="text-sm text-gray-700">فعال</span>
              </label>
            </div>
          </div>

          {/* Select options */}
          {form.field_type === 'select' && (
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                گزینه‌ها (هر خط یک گزینه)
              </label>
              <textarea
                value={selectOptions}
                onChange={(e) => setSelectOptions(e.target.value)}
                rows={4}
                placeholder={'گزینه ۱\nگزینه ۲\nگزینه ۳'}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          )}

          <div className="mt-4 flex gap-2">
            <button
              type="submit"
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700"
            >
              ✅ ذخیره
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                setEditingId(null);
              }}
              className="px-4 py-2 bg-gray-200 rounded-lg text-sm hover:bg-gray-300"
            >
              انصراف
            </button>
          </div>
        </form>
      )}

      {/* Field list */}
      {loading ? (
        <div className="text-center py-10 text-gray-500">
          در حال بارگذاری...
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-10 text-gray-400">
          هیچ فیلد ثبت‌نامی وجود ندارد
        </div>
      ) : (
        <div className="bg-white rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-4 py-3 text-right">ترتیب</th>
                <th className="px-4 py-3 text-right">برچسب</th>
                <th className="px-4 py-3 text-right">نام فیلد</th>
                <th className="px-4 py-3 text-right">نوع</th>
                <th className="px-4 py-3 text-center">اجباری</th>
                <th className="px-4 py-3 text-center">وضعیت</th>
                <th className="px-4 py-3 text-center">عملیات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((f, idx) => (
                <tr
                  key={f.id}
                  className="hover:bg-gray-50 transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => moveField(idx, -1)}
                        disabled={idx === 0}
                        className="text-gray-400 hover:text-gray-700 disabled:opacity-30"
                        title="بالا"
                      >
                        ▲
                      </button>
                      <span className="text-gray-500 mx-1">{f.order}</span>
                      <button
                        onClick={() => moveField(idx, 1)}
                        disabled={idx === items.length - 1}
                        className="text-gray-400 hover:text-gray-700 disabled:opacity-30"
                        title="پایین"
                      >
                        ▼
                      </button>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-800">
                    {f.field_label}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-left font-mono text-xs">
                    {f.field_name}
                  </td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">
                      {FIELD_TYPES.find((t) => t.value === f.field_type)
                        ?.label || f.field_type}
                    </span>
                    {f.field_type === 'select' && f.options?.choices && (
                      <span className="text-xs text-gray-400 mr-1">
                        ({f.options.choices.length} گزینه)
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {f.is_required ? (
                      <span className="text-green-600">✓</span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => handleToggleActive(f)}
                      className={`text-xs px-2 py-0.5 rounded-full cursor-pointer ${
                        f.is_active
                          ? 'bg-green-100 text-green-700 hover:bg-green-200'
                          : 'bg-red-100 text-red-700 hover:bg-red-200'
                      }`}
                    >
                      {f.is_active ? 'فعال' : 'غیرفعال'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <button
                        onClick={() => openEdit(f)}
                        className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs hover:bg-blue-100 transition"
                      >
                        ✏️
                      </button>
                      <button
                        onClick={() => handleDelete(f.id, f.field_label)}
                        className="px-2 py-1 bg-red-50 text-red-700 rounded text-xs hover:bg-red-100 transition"
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
