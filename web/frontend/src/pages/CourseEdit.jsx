import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { courses, lessons as lessonsApi } from '../api';

export default function CourseEdit() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [course, setCourse] = useState(null);
  const [lessonList, setLessonList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showCreateLesson, setShowCreateLesson] = useState(false);
  const [newLesson, setNewLesson] = useState({ title: '', delay_hours: 0 });

  const load = async () => {
    setLoading(true);
    try {
      const [c, l] = await Promise.all([courses.get(id), courses.lessons(id)]);
      setCourse(c);
      setLessonList(l);
    } catch {
      toast.error('خطا در بارگذاری');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await courses.update(id, course);
      toast.success('ذخیره شد');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleCreateLesson = async (e) => {
    e.preventDefault();
    try {
      const maxOrder = lessonList.reduce((max, l) => Math.max(max, l.order), 0);
      const res = await lessonsApi.create({
        course_id: parseInt(id),
        title: newLesson.title,
        delay_hours: newLesson.delay_hours,
        order: maxOrder + 1,
        content_type: 'text',
      });
      toast.success('درس ایجاد شد');
      setShowCreateLesson(false);
      setNewLesson({ title: '', delay_hours: 0 });
      navigate(`/lessons/${res.id}`);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleDeleteLesson = async (lessonId, title) => {
    if (!confirm(`آیا از حذف درس «${title}» مطمئنید؟`)) return;
    try {
      await lessonsApi.delete(lessonId);
      toast.success('درس حذف شد');
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  if (loading) return <div className="text-center py-20 text-gray-500">در حال بارگذاری...</div>;
  if (!course) return <div className="text-center py-20 text-red-500">دوره یافت نشد</div>;

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/courses')} className="text-gray-500 hover:text-gray-700">← بازگشت</button>
        <h1 className="text-2xl font-bold text-gray-800">ویرایش دوره: {course.title}</h1>
      </div>

      {/* Course settings */}
      <form onSubmit={handleSave} className="bg-white rounded-xl border p-5 mb-6">
        <h2 className="font-semibold mb-4">تنظیمات دوره</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">عنوان</label>
            <input
              type="text"
              value={course.title}
              onChange={(e) => setCourse({ ...course, title: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">توضیحات</label>
            <input
              type="text"
              value={course.description || ''}
              onChange={(e) => setCourse({ ...course, description: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">ترتیب</label>
            <input
              type="number"
              value={course.order}
              onChange={(e) => setCourse({ ...course, order: parseInt(e.target.value) || 0 })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">تأخیر فست‌ترک (دقیقه)</label>
            <input
              type="number"
              value={course.fast_track_delay}
              onChange={(e) => setCourse({ ...course, fast_track_delay: parseInt(e.target.value) || 5 })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <div className="flex items-center gap-6 pt-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={course.is_active}
                onChange={(e) => setCourse({ ...course, is_active: e.target.checked })}
                className="w-4 h-4"
              />
              <span className="text-sm">فعال</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={course.allow_2x}
                onChange={(e) => setCourse({ ...course, allow_2x: e.target.checked })}
                className="w-4 h-4"
              />
              <span className="text-sm">سرعت ۲x</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={course.allow_fast_track}
                onChange={(e) => setCourse({ ...course, allow_fast_track: e.target.checked })}
                className="w-4 h-4"
              />
              <span className="text-sm">فست‌ترک</span>
            </label>
          </div>
        </div>
        <button
          type="submit"
          disabled={saving}
          className="mt-4 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {saving ? '⏳ ذخیره...' : '💾 ذخیره تغییرات'}
        </button>
      </form>

      {/* Lessons */}
      <div className="bg-white rounded-xl border p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">📖 درس‌های این دوره ({lessonList.length})</h2>
          <button
            onClick={() => setShowCreateLesson(!showCreateLesson)}
            className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 transition"
          >
            ➕ درس جدید
          </button>
        </div>

        {showCreateLesson && (
          <form onSubmit={handleCreateLesson} className="bg-gray-50 rounded-lg p-4 mb-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">عنوان درس</label>
                <input
                  type="text"
                  value={newLesson.title}
                  onChange={(e) => setNewLesson({ ...newLesson, title: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">تأخیر (دقیقه)</label>
                <input
                  type="number"
                  value={newLesson.delay_hours}
                  onChange={(e) => setNewLesson({ ...newLesson, delay_hours: parseInt(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>
            </div>
            <div className="mt-3 flex gap-2">
              <button type="submit" className="px-4 py-1.5 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700">
                ✅ ایجاد
              </button>
              <button type="button" onClick={() => setShowCreateLesson(false)} className="px-4 py-1.5 bg-gray-200 rounded-lg text-sm">
                انصراف
              </button>
            </div>
          </form>
        )}

        {lessonList.length === 0 ? (
          <p className="text-gray-400 text-center py-6">هنوز درسی اضافه نشده</p>
        ) : (
          <div className="space-y-2">
            {lessonList.map((l, idx) => (
              <div
                key={l.id}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition"
              >
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono bg-gray-200 rounded px-2 py-0.5">{l.order}</span>
                  <span className="font-medium text-gray-800">{l.title}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${l.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {l.is_active ? 'فعال' : 'غیرفعال'}
                  </span>
                  <span className="text-xs text-gray-400">{l.content_type}</span>
                  {l.content_count > 1 && <span className="text-xs text-blue-500">{l.content_count} محتوا</span>}
                  {l.has_quiz && <span className="text-xs text-purple-500">🧩 کوییز</span>}
                  {l.has_form && <span className="text-xs text-orange-500">📝 فرم</span>}
                  {l.delay_hours > 0 && <span className="text-xs text-gray-400">⏱ {l.delay_hours} دقیقه</span>}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => navigate(`/lessons/${l.id}`)}
                    className="px-2.5 py-1 bg-blue-50 text-blue-700 rounded text-xs hover:bg-blue-100 transition"
                  >
                    ✏️ ویرایش
                  </button>
                  <button
                    onClick={() => handleDeleteLesson(l.id, l.title)}
                    className="px-2.5 py-1 bg-red-50 text-red-700 rounded text-xs hover:bg-red-100 transition"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
