import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { lessons, upload } from '../api';

const CONTENT_TYPES = [
  { value: 'text', label: '📝 متن', icon: '📝' },
  { value: 'video', label: '🎬 ویدیو', icon: '🎬' },
  { value: 'audio', label: '🎵 صدا', icon: '🎵' },
  { value: 'voice', label: '🎙 ویس', icon: '🎙' },
  { value: 'photo', label: '🖼 عکس', icon: '🖼' },
  { value: 'document', label: '📎 فایل', icon: '📎' },
  { value: 'form', label: '📋 فرم', icon: '📋' },
];

const FORM_FIELD_TYPES = [
  { value: 'text', label: 'متن' },
  { value: 'number', label: 'عدد' },
  { value: 'select', label: 'انتخابی' },
];

function ContentBlock({ item, index, total, onMoveUp, onMoveDown, onDelete, onReplace }) {
  const typeInfo = CONTENT_TYPES.find((t) => t.value === item.type) || { icon: '❓', label: item.type };

  return (
    <div className="flex items-center gap-3 p-3 bg-white border rounded-lg group hover:shadow-sm transition">
      {/* Order arrows */}
      <div className="flex flex-col gap-1">
        <button
          onClick={onMoveUp}
          disabled={index === 0}
          className="text-xs text-gray-400 hover:text-gray-700 disabled:opacity-20"
          title="بالا"
        >▲</button>
        <button
          onClick={onMoveDown}
          disabled={index === total - 1}
          className="text-xs text-gray-400 hover:text-gray-700 disabled:opacity-20"
          title="پایین"
        >▼</button>
      </div>

      {/* Type icon */}
      <span className="text-xl">{typeInfo.icon}</span>

      {/* Content preview */}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-gray-500">{typeInfo.label} — بلاک {index + 1}</p>
        {item.type === 'text' && (
          <p className="text-sm text-gray-700 truncate mt-0.5">{item.text?.slice(0, 100)}</p>
        )}
        {item.type === 'form' && item.form_data && (
          <div className="mt-0.5">
            <p className="text-sm text-orange-600">📋 فرم — {item.form_data.fields?.length || 0} فیلد</p>
            <p className="text-xs text-gray-400 truncate">
              {(item.form_data.fields || []).map(f => f.label).join('، ')}
            </p>
          </div>
        )}
        {item.type === 'form' && !item.form_data && (
          <p className="text-sm text-orange-600 mt-0.5">📋 فرم</p>
        )}
        {item.file_id && (
          <p className="text-xs text-gray-400 font-mono truncate mt-0.5" dir="ltr">
            {item.file_id.slice(0, 40)}...
          </p>
        )}
        {item.caption && (
          <p className="text-xs text-gray-500 truncate mt-0.5">📝 {item.caption.slice(0, 60)}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={onReplace}
          className="px-2 py-1 bg-yellow-50 text-yellow-700 rounded text-xs hover:bg-yellow-100"
          title="جایگزین"
        >🔄</button>
        <button
          onClick={onDelete}
          className="px-2 py-1 bg-red-50 text-red-700 rounded text-xs hover:bg-red-100"
          title="حذف"
        >🗑️</button>
      </div>
    </div>
  );
}

export default function LessonEdit() {
  const { id } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [lesson, setLesson] = useState(null);
  const [contents, setContents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  // Add content modal
  const [showAdd, setShowAdd] = useState(false);
  const [addType, setAddType] = useState('text');
  const [addText, setAddText] = useState('');
  const [addCaption, setAddCaption] = useState('');
  const [addFile, setAddFile] = useState(null);

  // Replace modal
  const [replaceIndex, setReplaceIndex] = useState(null);
  const [replaceType, setReplaceType] = useState('text');
  const [replaceText, setReplaceText] = useState('');
  const [replaceCaption, setReplaceCaption] = useState('');
  const [replaceFile, setReplaceFile] = useState(null);

  // Form builder state
  const [formFields, setFormFields] = useState([]);
  const [showFormFieldModal, setShowFormFieldModal] = useState(false);
  const [editingFieldIndex, setEditingFieldIndex] = useState(null);
  const [fieldLabel, setFieldLabel] = useState('');
  const [fieldType, setFieldType] = useState('text');
  const [fieldOptions, setFieldOptions] = useState('');

  // Replace form builder state
  const [replaceFormFields, setReplaceFormFields] = useState([]);
  const [showReplaceFormFieldModal, setShowReplaceFormFieldModal] = useState(false);
  const [replaceEditingFieldIndex, setReplaceEditingFieldIndex] = useState(null);
  const [replaceFieldLabel, setReplaceFieldLabel] = useState('');
  const [replaceFieldType, setReplaceFieldType] = useState('text');
  const [replaceFieldOptions, setReplaceFieldOptions] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const data = await lessons.get(id);
      setLesson(data);
      setContents(data.contents || []);
    } catch {
      toast.error('خطا در بارگذاری');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);

  // Save lesson settings
  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await lessons.update(id, {
        title: lesson.title,
        description: lesson.description,
        is_active: lesson.is_active,
        order: lesson.order,
        delay_hours: lesson.delay_hours,
        view_deadline_hours: lesson.view_deadline_hours,
        cta_text: lesson.cta_text,
        cta_url: lesson.cta_url,
      });
      toast.success('ذخیره شد');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  // Content management
  const handleMoveUp = async (index) => {
    if (index === 0) return;
    const newContents = [...contents];
    [newContents[index - 1], newContents[index]] = [newContents[index], newContents[index - 1]];
    try {
      await lessons.updateContents(id, newContents);
      setContents(newContents);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleMoveDown = async (index) => {
    if (index >= contents.length - 1) return;
    const newContents = [...contents];
    [newContents[index], newContents[index + 1]] = [newContents[index + 1], newContents[index]];
    try {
      await lessons.updateContents(id, newContents);
      setContents(newContents);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleDeleteContent = async (index) => {
    if (!confirm('آیا از حذف این محتوا مطمئنید؟')) return;
    try {
      await lessons.deleteContent(id, index);
      const newContents = [...contents];
      newContents.splice(index, 1);
      setContents(newContents);
      toast.success('محتوا حذف شد');
    } catch (err) {
      toast.error(err.message);
    }
  };

  // Add content
  const handleAddContent = async () => {
    if (addType === 'text') {
      if (!addText.trim()) { toast.error('متن خالی است'); return; }
      try {
        await lessons.addContent(id, { type: 'text', text: addText });
        setContents([...contents, { type: 'text', text: addText }]);
        setAddText('');
        setShowAdd(false);
        toast.success('محتوا اضافه شد');
      } catch (err) { toast.error(err.message); }
    } else if (addType === 'form') {
      if (formFields.length === 0) { toast.error('حداقل یک فیلد اضافه کنید'); return; }
      try {
        const formData = { fields: formFields };
        await lessons.saveForm(id, formData);
        // Reload to get updated contents
        await load();
        setFormFields([]);
        setShowAdd(false);
        toast.success('فرم ذخیره شد');
      } catch (err) { toast.error(err.message); }
    }
    // File types handled by handleFileUpload
  };

  // Form field helpers
  const openAddFormField = () => {
    setFieldLabel('');
    setFieldType('text');
    setFieldOptions('');
    setEditingFieldIndex(null);
    setShowFormFieldModal(true);
  };

  const openEditFormField = (idx) => {
    const f = formFields[idx];
    setFieldLabel(f.label);
    setFieldType(f.type);
    setFieldOptions((f.options || []).join('، '));
    setEditingFieldIndex(idx);
    setShowFormFieldModal(true);
  };

  const saveFormField = () => {
    if (!fieldLabel.trim()) { toast.error('عنوان فیلد خالی است'); return; }
    const field = {
      name: editingFieldIndex !== null ? formFields[editingFieldIndex].name : `field_${formFields.length + 1}`,
      label: fieldLabel.trim(),
      type: fieldType,
    };
    if (fieldType === 'select') {
      field.options = fieldOptions.split(/[,،]/).map(o => o.trim()).filter(Boolean);
      if (field.options.length < 2) { toast.error('حداقل ۲ گزینه وارد کنید'); return; }
    }
    const newFields = [...formFields];
    if (editingFieldIndex !== null) {
      newFields[editingFieldIndex] = field;
    } else {
      newFields.push(field);
    }
    setFormFields(newFields);
    setShowFormFieldModal(false);
  };

  const deleteFormField = (idx) => {
    setFormFields(formFields.filter((_, i) => i !== idx));
  };

  const moveFormField = (idx, dir) => {
    const newFields = [...formFields];
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= newFields.length) return;
    [newFields[idx], newFields[newIdx]] = [newFields[newIdx], newFields[idx]];
    setFormFields(newFields);
  };

  const handleFileUpload = async (file, contentType, caption = '', isReplace = false, index = -1) => {
    setUploading(true);
    setUploadProgress(0);
    try {
      const result = await upload.file(file, contentType, caption, (pct) => setUploadProgress(pct));
      const item = { type: contentType, file_id: result.file_id };
      if (caption) item.caption = caption;

      if (isReplace && index >= 0) {
        await lessons.replaceContent(id, index, item);
        const newContents = [...contents];
        newContents[index] = item;
        setContents(newContents);
        setReplaceIndex(null);
        toast.success('محتوا جایگزین شد');
      } else {
        await lessons.addContent(id, item);
        setContents([...contents, item]);
        setShowAdd(false);
        toast.success('فایل آپلود و اضافه شد');
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  // Replace content
  const openReplace = (index) => {
    const item = contents[index];
    setReplaceIndex(index);
    setReplaceType(item.type);
    setReplaceText(item.text || '');
    setReplaceCaption(item.caption || '');
    if (item.type === 'form' && item.form_data) {
      setReplaceFormFields(item.form_data.fields || []);
    } else {
      setReplaceFormFields([]);
    }
  };

  const handleReplace = async () => {
    if (replaceType === 'text') {
      if (!replaceText.trim()) { toast.error('متن خالی است'); return; }
      try {
        await lessons.replaceContent(id, replaceIndex, { type: 'text', text: replaceText });
        const newContents = [...contents];
        newContents[replaceIndex] = { type: 'text', text: replaceText };
        setContents(newContents);
        setReplaceIndex(null);
        toast.success('محتوا جایگزین شد');
      } catch (err) { toast.error(err.message); }
    } else if (replaceType === 'form') {
      if (replaceFormFields.length === 0) { toast.error('حداقل یک فیلد اضافه کنید'); return; }
      try {
        const formData = { fields: replaceFormFields };
        await lessons.saveForm(id, formData);
        await load();
        setReplaceIndex(null);
        setReplaceFormFields([]);
        toast.success('فرم به‌روزرسانی شد');
      } catch (err) { toast.error(err.message); }
    }
  };

  // Replace form field helpers
  const openAddReplaceFormField = () => {
    setReplaceFieldLabel('');
    setReplaceFieldType('text');
    setReplaceFieldOptions('');
    setReplaceEditingFieldIndex(null);
    setShowReplaceFormFieldModal(true);
  };

  const openEditReplaceFormField = (idx) => {
    const f = replaceFormFields[idx];
    setReplaceFieldLabel(f.label);
    setReplaceFieldType(f.type);
    setReplaceFieldOptions((f.options || []).join('، '));
    setReplaceEditingFieldIndex(idx);
    setShowReplaceFormFieldModal(true);
  };

  const saveReplaceFormField = () => {
    if (!replaceFieldLabel.trim()) { toast.error('عنوان فیلد خالی است'); return; }
    const field = {
      name: replaceEditingFieldIndex !== null ? replaceFormFields[replaceEditingFieldIndex].name : `field_${replaceFormFields.length + 1}`,
      label: replaceFieldLabel.trim(),
      type: replaceFieldType,
    };
    if (replaceFieldType === 'select') {
      field.options = replaceFieldOptions.split(/[,،]/).map(o => o.trim()).filter(Boolean);
      if (field.options.length < 2) { toast.error('حداقل ۲ گزینه وارد کنید'); return; }
    }
    const newFields = [...replaceFormFields];
    if (replaceEditingFieldIndex !== null) {
      newFields[replaceEditingFieldIndex] = field;
    } else {
      newFields.push(field);
    }
    setReplaceFormFields(newFields);
    setShowReplaceFormFieldModal(false);
  };

  const deleteReplaceFormField = (idx) => {
    setReplaceFormFields(replaceFormFields.filter((_, i) => i !== idx));
  };

  const moveReplaceFormField = (idx, dir) => {
    const newFields = [...replaceFormFields];
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= newFields.length) return;
    [newFields[idx], newFields[newIdx]] = [newFields[newIdx], newFields[idx]];
    setReplaceFormFields(newFields);
  };

  if (loading) return <div className="text-center py-20 text-gray-500">در حال بارگذاری...</div>;
  if (!lesson) return <div className="text-center py-20 text-red-500">درس یافت نشد</div>;

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate(lesson.course_id ? `/courses/${lesson.course_id}` : '/courses')}
          className="text-gray-500 hover:text-gray-700"
        >← بازگشت</button>
        <h1 className="text-2xl font-bold text-gray-800">ویرایش درس: {lesson.title}</h1>
      </div>

      {/* Lesson settings */}
      <form onSubmit={handleSaveSettings} className="bg-white rounded-xl border p-5 mb-6">
        <h2 className="font-semibold mb-4">⚙️ تنظیمات درس</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">عنوان</label>
            <input
              type="text"
              value={lesson.title}
              onChange={(e) => setLesson({ ...lesson, title: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">توضیحات</label>
            <input
              type="text"
              value={lesson.description || ''}
              onChange={(e) => setLesson({ ...lesson, description: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">ترتیب</label>
            <input
              type="number"
              value={lesson.order}
              onChange={(e) => setLesson({ ...lesson, order: parseInt(e.target.value) || 0 })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">تأخیر (دقیقه)</label>
            <input
              type="number"
              value={lesson.delay_hours}
              onChange={(e) => setLesson({ ...lesson, delay_hours: parseInt(e.target.value) || 0 })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">مهلت مشاهده (ساعت)</label>
            <input
              type="number"
              value={lesson.view_deadline_hours || ''}
              onChange={(e) => setLesson({ ...lesson, view_deadline_hours: e.target.value ? parseInt(e.target.value) : null })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="بدون مهلت"
            />
          </div>
          <div className="flex items-center pt-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={lesson.is_active}
                onChange={(e) => setLesson({ ...lesson, is_active: e.target.checked })}
                className="w-4 h-4"
              />
              <span className="text-sm">فعال</span>
            </label>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">متن CTA</label>
            <input
              type="text"
              value={lesson.cta_text || ''}
              onChange={(e) => setLesson({ ...lesson, cta_text: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="مثلاً: خرید دوره"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">لینک CTA</label>
            <input
              type="text"
              value={lesson.cta_url || ''}
              onChange={(e) => setLesson({ ...lesson, cta_url: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="https://"
              dir="ltr"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={saving}
          className="mt-4 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {saving ? '⏳ ذخیره...' : '💾 ذخیره تنظیمات'}
        </button>
      </form>

      {/* Content management */}
      <div className="bg-white rounded-xl border p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">📦 محتواهای درس ({contents.length} بلاک)</h2>
          <button
            onClick={() => { setShowAdd(true); setAddType('text'); setAddText(''); setAddCaption(''); setFormFields([]); setAddFile(null); }}
            className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 transition"
          >
            ➕ افزودن محتوا
          </button>
        </div>

        {contents.length === 0 ? (
          <p className="text-gray-400 text-center py-6">هیچ محتوایی اضافه نشده</p>
        ) : (
          <div className="space-y-2">
            {contents.map((item, idx) => (
              <ContentBlock
                key={idx}
                item={item}
                index={idx}
                total={contents.length}
                onMoveUp={() => handleMoveUp(idx)}
                onMoveDown={() => handleMoveDown(idx)}
                onDelete={() => handleDeleteContent(idx)}
                onReplace={() => openReplace(idx)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Add content modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowAdd(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">➕ افزودن محتوای جدید</h3>

            {/* Type selector */}
            <div className="flex flex-wrap gap-2 mb-4">
              {CONTENT_TYPES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setAddType(t.value)}
                  className={`px-3 py-1.5 rounded-lg text-sm border transition ${
                    addType === t.value
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {addType === 'text' && (
              <div>
                <textarea
                  value={addText}
                  onChange={(e) => setAddText(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none min-h-[120px]"
                  placeholder="متن محتوا..."
                />
                <div className="mt-4 flex gap-2">
                  <button
                    onClick={handleAddContent}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700"
                  >✅ افزودن</button>
                  <button onClick={() => setShowAdd(false)} className="px-4 py-2 bg-gray-200 rounded-lg text-sm">انصراف</button>
                </div>
              </div>
            )}

            {addType === 'form' && (
              <div>
                <p className="text-sm text-gray-600 mb-3">فیلدهای فرم را اضافه کنید. کاربران هنگام مشاهده درس، این فرم را پر خواهند کرد.</p>

                {formFields.length > 0 && (
                  <div className="space-y-2 mb-4 max-h-60 overflow-y-auto">
                    {formFields.map((f, idx) => (
                      <div key={idx} className="flex items-center gap-2 p-2 bg-gray-50 border rounded-lg">
                        <div className="flex flex-col gap-0.5">
                          <button onClick={() => moveFormField(idx, -1)} disabled={idx === 0} className="text-xs text-gray-400 hover:text-gray-700 disabled:opacity-20">▲</button>
                          <button onClick={() => moveFormField(idx, 1)} disabled={idx === formFields.length - 1} className="text-xs text-gray-400 hover:text-gray-700 disabled:opacity-20">▼</button>
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium">{f.label}</p>
                          <p className="text-xs text-gray-500">
                            {FORM_FIELD_TYPES.find(t => t.value === f.type)?.label || f.type}
                            {f.options && ` — ${f.options.join('، ')}`}
                          </p>
                        </div>
                        <button onClick={() => openEditFormField(idx)} className="px-2 py-1 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100">✏️</button>
                        <button onClick={() => deleteFormField(idx)} className="px-2 py-1 text-xs bg-red-50 text-red-700 rounded hover:bg-red-100">🗑️</button>
                      </div>
                    ))}
                  </div>
                )}

                <button
                  onClick={openAddFormField}
                  className="w-full py-2 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:border-orange-400 hover:text-orange-600 transition"
                >
                  ➕ افزودن فیلد
                </button>

                <div className="mt-4 flex gap-2">
                  <button
                    onClick={handleAddContent}
                    disabled={formFields.length === 0}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
                  >✅ ذخیره فرم</button>
                  <button onClick={() => setShowAdd(false)} className="px-4 py-2 bg-gray-200 rounded-lg text-sm">انصراف</button>
                </div>
              </div>
            )}

            {addType !== 'text' && addType !== 'form' && (
              <div>
                <div className="mb-3">
                  <label className="block text-sm font-medium text-gray-700 mb-1">کپشن (اختیاری)</label>
                  <input
                    type="text"
                    value={addCaption}
                    onChange={(e) => setAddCaption(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setAddFile(f);
                  }}
                  className="w-full"
                />
                {addFile && !uploading && (
                  <p className="mt-2 text-sm text-green-700 bg-green-50 px-3 py-1.5 rounded-lg">
                    📎 {addFile.name} ({(addFile.size / 1024).toFixed(0)} KB)
                  </p>
                )}
                {uploading && (
                  <div className="mt-2">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-blue-500 text-sm">⏳ در حال آپلود... {uploadProgress}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2.5">
                      <div
                        className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                        style={{ width: `${uploadProgress}%` }}
                      />
                    </div>
                  </div>
                )}
                <div className="mt-4 flex gap-2">
                  <button
                    onClick={() => { if (addFile) handleFileUpload(addFile, addType, addCaption); }}
                    disabled={!addFile || uploading}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50 transition"
                  >{uploading ? '⏳ در حال آپلود...' : '✅ آپلود و ذخیره'}</button>
                  <button onClick={() => setShowAdd(false)} className="px-4 py-2 bg-gray-200 rounded-lg text-sm" disabled={uploading}>انصراف</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Replace content modal */}
      {replaceIndex !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setReplaceIndex(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">🔄 جایگزینی محتوای بلاک {replaceIndex + 1}</h3>

            <div className="flex flex-wrap gap-2 mb-4">
              {CONTENT_TYPES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setReplaceType(t.value)}
                  className={`px-3 py-1.5 rounded-lg text-sm border transition ${
                    replaceType === t.value
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {replaceType === 'text' && (
              <div>
                <textarea
                  value={replaceText}
                  onChange={(e) => setReplaceText(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none min-h-[120px]"
                />
                <div className="mt-4 flex gap-2">
                  <button onClick={handleReplace} className="px-4 py-2 bg-yellow-600 text-white rounded-lg text-sm hover:bg-yellow-700">
                    🔄 جایگزین
                  </button>
                  <button onClick={() => setReplaceIndex(null)} className="px-4 py-2 bg-gray-200 rounded-lg text-sm">انصراف</button>
                </div>
              </div>
            )}

            {replaceType === 'form' && (
              <div>
                <p className="text-sm text-gray-600 mb-3">فیلدهای فرم را ویرایش کنید.</p>

                {replaceFormFields.length > 0 && (
                  <div className="space-y-2 mb-4 max-h-60 overflow-y-auto">
                    {replaceFormFields.map((f, idx) => (
                      <div key={idx} className="flex items-center gap-2 p-2 bg-gray-50 border rounded-lg">
                        <div className="flex flex-col gap-0.5">
                          <button onClick={() => moveReplaceFormField(idx, -1)} disabled={idx === 0} className="text-xs text-gray-400 hover:text-gray-700 disabled:opacity-20">▲</button>
                          <button onClick={() => moveReplaceFormField(idx, 1)} disabled={idx === replaceFormFields.length - 1} className="text-xs text-gray-400 hover:text-gray-700 disabled:opacity-20">▼</button>
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium">{f.label}</p>
                          <p className="text-xs text-gray-500">
                            {FORM_FIELD_TYPES.find(t => t.value === f.type)?.label || f.type}
                            {f.options && ` — ${f.options.join('، ')}`}
                          </p>
                        </div>
                        <button onClick={() => openEditReplaceFormField(idx)} className="px-2 py-1 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100">✏️</button>
                        <button onClick={() => deleteReplaceFormField(idx)} className="px-2 py-1 text-xs bg-red-50 text-red-700 rounded hover:bg-red-100">🗑️</button>
                      </div>
                    ))}
                  </div>
                )}

                <button
                  onClick={openAddReplaceFormField}
                  className="w-full py-2 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:border-orange-400 hover:text-orange-600 transition"
                >
                  ➕ افزودن فیلد
                </button>

                <div className="mt-4 flex gap-2">
                  <button
                    onClick={handleReplace}
                    disabled={replaceFormFields.length === 0}
                    className="px-4 py-2 bg-yellow-600 text-white rounded-lg text-sm hover:bg-yellow-700 disabled:opacity-50"
                  >🔄 ذخیره فرم</button>
                  <button onClick={() => setReplaceIndex(null)} className="px-4 py-2 bg-gray-200 rounded-lg text-sm">انصراف</button>
                </div>
              </div>
            )}

            {replaceType !== 'text' && replaceType !== 'form' && (
              <div>
                <div className="mb-3">
                  <label className="block text-sm font-medium text-gray-700 mb-1">کپشن (اختیاری)</label>
                  <input
                    type="text"
                    value={replaceCaption}
                    onChange={(e) => setReplaceCaption(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
                <input
                  type="file"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setReplaceFile(f);
                  }}
                  className="w-full"
                />
                {replaceFile && !uploading && (
                  <p className="mt-2 text-sm text-green-700 bg-green-50 px-3 py-1.5 rounded-lg">
                    📎 {replaceFile.name} ({(replaceFile.size / 1024).toFixed(0)} KB)
                  </p>
                )}
                {uploading && (
                  <div className="mt-2">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-blue-500 text-sm">⏳ در حال آپلود... {uploadProgress}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2.5">
                      <div
                        className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                        style={{ width: `${uploadProgress}%` }}
                      />
                    </div>
                  </div>
                )}
                <div className="mt-4 flex gap-2">
                  <button
                    onClick={() => { if (replaceFile) handleFileUpload(replaceFile, replaceType, replaceCaption, true, replaceIndex); }}
                    disabled={!replaceFile || uploading}
                    className="px-4 py-2 bg-yellow-600 text-white rounded-lg text-sm hover:bg-yellow-700 disabled:opacity-50 transition"
                  >{uploading ? '⏳ در حال آپلود...' : '🔄 آپلود و جایگزینی'}</button>
                  <button onClick={() => setReplaceIndex(null)} className="px-4 py-2 bg-gray-200 rounded-lg text-sm" disabled={uploading}>انصراف</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Form field modal (Add) */}
      {showFormFieldModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]" onClick={() => setShowFormFieldModal(false)}>
          <div className="bg-white rounded-xl p-5 w-full max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
            <h4 className="font-semibold mb-3">{editingFieldIndex !== null ? '✏️ ویرایش فیلد' : '➕ فیلد جدید'}</h4>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">عنوان فیلد</label>
                <input
                  type="text"
                  value={fieldLabel}
                  onChange={(e) => setFieldLabel(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="مثلاً: نام و نام خانوادگی"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">نوع فیلد</label>
                <div className="flex gap-2">
                  {FORM_FIELD_TYPES.map(t => (
                    <button
                      key={t.value}
                      onClick={() => setFieldType(t.value)}
                      className={`px-3 py-1.5 rounded-lg text-sm border transition ${
                        fieldType === t.value
                          ? 'bg-orange-600 text-white border-orange-600'
                          : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                      }`}
                    >{t.label}</button>
                  ))}
                </div>
              </div>
              {fieldType === 'select' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">گزینه‌ها (با کاما جدا کنید)</label>
                  <input
                    type="text"
                    value={fieldOptions}
                    onChange={(e) => setFieldOptions(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="گزینه ۱، گزینه ۲، گزینه ۳"
                  />
                </div>
              )}
            </div>
            <div className="mt-4 flex gap-2">
              <button onClick={saveFormField} className="px-4 py-2 bg-orange-600 text-white rounded-lg text-sm hover:bg-orange-700">
                {editingFieldIndex !== null ? '✅ ذخیره' : '➕ افزودن'}
              </button>
              <button onClick={() => setShowFormFieldModal(false)} className="px-4 py-2 bg-gray-200 rounded-lg text-sm">انصراف</button>
            </div>
          </div>
        </div>
      )}

      {/* Form field modal (Replace) */}
      {showReplaceFormFieldModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]" onClick={() => setShowReplaceFormFieldModal(false)}>
          <div className="bg-white rounded-xl p-5 w-full max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
            <h4 className="font-semibold mb-3">{replaceEditingFieldIndex !== null ? '✏️ ویرایش فیلد' : '➕ فیلد جدید'}</h4>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">عنوان فیلد</label>
                <input
                  type="text"
                  value={replaceFieldLabel}
                  onChange={(e) => setReplaceFieldLabel(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="مثلاً: نام و نام خانوادگی"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">نوع فیلد</label>
                <div className="flex gap-2">
                  {FORM_FIELD_TYPES.map(t => (
                    <button
                      key={t.value}
                      onClick={() => setReplaceFieldType(t.value)}
                      className={`px-3 py-1.5 rounded-lg text-sm border transition ${
                        replaceFieldType === t.value
                          ? 'bg-orange-600 text-white border-orange-600'
                          : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                      }`}
                    >{t.label}</button>
                  ))}
                </div>
              </div>
              {replaceFieldType === 'select' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">گزینه‌ها (با کاما جدا کنید)</label>
                  <input
                    type="text"
                    value={replaceFieldOptions}
                    onChange={(e) => setReplaceFieldOptions(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="گزینه ۱، گزینه ۲، گزینه ۳"
                  />
                </div>
              )}
            </div>
            <div className="mt-4 flex gap-2">
              <button onClick={saveReplaceFormField} className="px-4 py-2 bg-orange-600 text-white rounded-lg text-sm hover:bg-orange-700">
                {replaceEditingFieldIndex !== null ? '✅ ذخیره' : '➕ افزودن'}
              </button>
              <button onClick={() => setShowReplaceFormFieldModal(false)} className="px-4 py-2 bg-gray-200 rounded-lg text-sm">انصراف</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
