import { useState, useEffect } from 'react';
import { stats } from '../api';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ComposedChart, Line, Cell,
} from 'recharts';

function StatCard({ label, value, icon, color = 'blue' }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
    orange: 'bg-orange-50 text-orange-700 border-orange-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    cyan: 'bg-cyan-50 text-cyan-700 border-cyan-200',
  };

  return (
    <div className={`rounded-xl border p-5 ${colors[color]}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm opacity-75">{label}</p>
          <p className="text-2xl font-bold mt-1">{value?.toLocaleString('fa-IR') ?? '—'}</p>
        </div>
        <span className="text-3xl">{icon}</span>
      </div>
    </div>
  );
}

function FunnelDropBadge({ rate }) {
  if (rate > 30) return <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">⚠️ {rate}%</span>;
  if (rate > 15) return <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full">⚡ {rate}%</span>;
  if (rate > 0) return <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{rate}%</span>;
  return null;
}

function getBarColor(dropRate) {
  if (dropRate > 30) return '#ef4444';
  if (dropRate > 15) return '#f97316';
  return '#3b82f6';
}

const CustomFunnelTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-white border rounded-lg shadow-lg p-3 text-sm" dir="rtl">
      <p className="font-bold mb-1">{d.title}</p>
      <p>شروع: <b>{d.started?.toLocaleString('fa-IR')}</b></p>
      <p>تکمیل: <b>{d.completed?.toLocaleString('fa-IR')}</b></p>
      <p>نرخ تکمیل: <b>{d.completion_rate}%</b></p>
      {d.drop_off_rate > 0 && <p className="text-red-600">ریزش: <b>{d.drop_off_rate}%</b></p>}
    </div>
  );
};

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [funnelData, setFunnelData] = useState(null);
  const [funnelCourses, setFunnelCourses] = useState([]);
  const [selectedCourse, setSelectedCourse] = useState('');
  const [funnelLoading, setFunnelLoading] = useState(false);

  useEffect(() => {
    stats.get()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
    // Load funnel data
    loadFunnel();
  }, []);

  const loadFunnel = (courseId) => {
    setFunnelLoading(true);
    stats.funnel(courseId || undefined)
      .then((res) => {
        setFunnelData(res.funnel || []);
        setFunnelCourses(res.courses || []);
      })
      .catch(() => {})
      .finally(() => setFunnelLoading(false));
  };

  const handleCourseFilter = (e) => {
    const val = e.target.value;
    setSelectedCourse(val);
    loadFunnel(val || undefined);
  };

  if (loading) return <div className="text-center py-20 text-gray-500">در حال بارگذاری...</div>;
  if (!data) return <div className="text-center py-20 text-red-500">خطا در دریافت آمار</div>;

  const chartData = (data.daily_registrations || []).map((d) => ({
    date: d.date ? new Date(d.date).toLocaleDateString('fa-IR', { month: 'short', day: 'numeric' }) : '',
    count: d.count,
  }));

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">داشبورد</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-8">
        <StatCard label="کل کاربران" value={data.total_users} icon="👥" color="blue" />
        <StatCard label="کاربران فعال (۷ روز)" value={data.active_users_7d} icon="🟢" color="green" />
        <StatCard label="ثبت‌نام امروز" value={data.new_today} icon="📥" color="cyan" />
        <StatCard label="ثبت‌نام هفته" value={data.new_this_week} icon="📈" color="purple" />
        <StatCard label="دوره‌ها" value={data.total_courses} icon="📚" color="orange" />
        <StatCard label="درس‌ها" value={data.total_lessons} icon="📖" color="blue" />
        <StatCard label="تکمیل‌شده" value={data.completed_users} icon="✅" color="green" />
        <StatCard label="درس امروز" value={data.lessons_completed_today} icon="🎯" color="purple" />
      </div>

      {/* Platform breakdown */}
      {data.platforms && Object.keys(data.platforms).length > 0 && (
        <div className="bg-white rounded-xl border p-5 mb-6">
          <h2 className="text-lg font-semibold mb-3">پلتفرم‌ها</h2>
          <div className="flex gap-6">
            {Object.entries(data.platforms).map(([platform, count]) => (
              <div key={platform} className="text-center">
                <span className="text-2xl">{platform === 'telegram' ? '📱' : '💬'}</span>
                <p className="font-bold text-lg">{count.toLocaleString('fa-IR')}</p>
                <p className="text-sm text-gray-500">{platform}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Registration chart */}
      {chartData.length > 0 && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="text-lg font-semibold mb-4">ثبت‌نام ۱۴ روز اخیر</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} name="ثبت‌نام" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Funnel Analysis */}
      <div className="bg-white rounded-xl border p-5 mt-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">📊 تحلیل فانل (ریزش درس به درس)</h2>
          <select
            value={selectedCourse}
            onChange={handleCourseFilter}
            className="border rounded-lg px-3 py-1.5 text-sm bg-gray-50"
          >
            <option value="">همه دوره‌ها</option>
            {funnelCourses.map((c) => (
              <option key={c.id} value={c.id}>{c.title}</option>
            ))}
          </select>
        </div>

        {funnelLoading ? (
          <div className="text-center py-10 text-gray-400">در حال بارگذاری فانل...</div>
        ) : !funnelData || funnelData.length === 0 ? (
          <div className="text-center py-10 text-gray-400">📭 داده‌ای برای تحلیل وجود ندارد</div>
        ) : (
          <>
            {/* Summary row */}
            {funnelData.length >= 2 && (
              <div className="flex gap-4 mb-4 text-sm">
                <div className="bg-blue-50 rounded-lg px-4 py-2 border border-blue-200">
                  <span className="text-blue-600">شروع: </span>
                  <b>{funnelData[0].started?.toLocaleString('fa-IR')}</b>
                </div>
                <div className="bg-green-50 rounded-lg px-4 py-2 border border-green-200">
                  <span className="text-green-600">تکمیل آخرین درس: </span>
                  <b>{funnelData[funnelData.length - 1].completed?.toLocaleString('fa-IR')}</b>
                </div>
                <div className="bg-purple-50 rounded-lg px-4 py-2 border border-purple-200">
                  <span className="text-purple-600">نرخ کل: </span>
                  <b>
                    {funnelData[0].started > 0
                      ? Math.round((funnelData[funnelData.length - 1].completed / funnelData[0].started) * 100)
                      : 0}%
                  </b>
                </div>
              </div>
            )}

            {/* Funnel Chart */}
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={funnelData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="order"
                  tick={{ fontSize: 12 }}
                  tickFormatter={(v, i) => funnelData[i] ? `درس ${v}` : v}
                />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip content={<CustomFunnelTooltip />} />
                <Bar dataKey="started" name="شروع" opacity={0.3} fill="#93c5fd" radius={[4, 4, 0, 0]} />
                <Bar dataKey="completed" name="تکمیل" radius={[4, 4, 0, 0]}>
                  {funnelData.map((entry, idx) => (
                    <Cell key={idx} fill={getBarColor(entry.drop_off_rate)} />
                  ))}
                </Bar>
                <Line
                  type="monotone"
                  dataKey="completion_rate"
                  name="نرخ تکمیل %"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  yAxisId={1}
                />
                <YAxis yAxisId={1} orientation="left" domain={[0, 100]} hide />
              </ComposedChart>
            </ResponsiveContainer>

            {/* Funnel Table */}
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="text-right py-2 px-3">درس</th>
                    <th className="text-center py-2 px-3">شروع</th>
                    <th className="text-center py-2 px-3">تکمیل</th>
                    <th className="text-center py-2 px-3">نرخ تکمیل</th>
                    <th className="text-center py-2 px-3">ریزش</th>
                  </tr>
                </thead>
                <tbody>
                  {funnelData.map((item) => (
                    <tr key={item.lesson_id} className="border-t hover:bg-gray-50">
                      <td className="py-2 px-3">
                        <span className="text-gray-400 ml-1">{item.order}.</span>
                        {item.title}
                      </td>
                      <td className="text-center py-2 px-3">{item.started?.toLocaleString('fa-IR')}</td>
                      <td className="text-center py-2 px-3">{item.completed?.toLocaleString('fa-IR')}</td>
                      <td className="text-center py-2 px-3">{item.completion_rate}%</td>
                      <td className="text-center py-2 px-3">
                        <FunnelDropBadge rate={item.drop_off_rate} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-3 text-xs text-gray-400">
              ⚠️ = ریزش بالا ({'>'}30%)  ⚡ = ریزش متوسط ({'>'}15%)
            </div>
          </>
        )}
      </div>
    </div>
  );
}
