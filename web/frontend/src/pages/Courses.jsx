import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { courses } from '../api';

export default function Courses() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: '', description: '' });
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    courses.list()
      .then(setItems)
      .catch(() => toast.error('خطا در دریافت دوره‌ها'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      const res = await courses.create(form);
      toast.success('دوره ایجاد شد');
      setShowCreate(false);
      setForm({ title: '', description: '' });
      navigate(`/courses/${res.id}`);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleDelete = async (id, title) => {
    if (!confirm(`آیا از حذف دوره «${title}» مطمئنید؟`)) return;
    try {
      await courses.delete(id);
      toast.success('دوره حذف شد');
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">📚 مدیریت دوره‌ها</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm"
        >
          ➕ دوره جدید
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <form onSubmit={handleCreate} className="bg-white rounded-xl border p-5 mb-6">
          <h2 className="font-semibold mb-4">ایجاد دوره جدید</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">عنوان دوره</label>
              <input
                type="text"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">توضیحات</label>
              <input
                type="text"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          </div>
          <div className="mt-4 flex gap-2">
            <button type="submit" className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700">
              ✅ ذخیره
            </button>
            <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 bg-gray-200 rounded-lg text-sm hover:bg-gray-300">
              انصراف
            </button>
          </div>
        </form>
      )}

      {/* Course list */}
      {loading ? (
        <div className="text-center py-10 text-gray-500">در حال بارگذاری...</div>
      ) : items.length === 0 ? (
        <div className="text-center py-10 text-gray-400">هیچ دوره‌ای وجود ندارد</div>
      ) : (
        <div className="grid gap-4">
          {items.map((c) => (
            <div
              key={c.id}
              className="bg-white rounded-xl border p-5 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h2 className="text-lg font-semibold text-gray-800">{c.title}</h2>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${c.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                      {c.is_active ? 'فعال' : 'غیرفعال'}
                    </span>
                  </div>
                  {c.description && <p className="text-sm text-gray-500 mt-1">{c.description}</p>}
                  <div className="flex gap-4 mt-2 text-xs text-gray-400">
                    <span>📖 {c.lesson_count} درس</span>
                    <span>👥 {c.user_count} کاربر</span>
                    <span>ترتیب: {c.order}</span>
                    {c.allow_2x && <span>⚡ ۲x</span>}
                    {c.allow_fast_track && <span>🚀 فست‌ترک</span>}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => navigate(`/courses/${c.id}`)}
                    className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg text-sm hover:bg-blue-100 transition"
                  >
                    ✏️ ویرایش
                  </button>
                  <button
                    onClick={() => handleDelete(c.id, c.title)}
                    className="px-3 py-1.5 bg-red-50 text-red-700 rounded-lg text-sm hover:bg-red-100 transition"
                  >
                    🗑️ حذف
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
