import { useState, useEffect } from 'react';
import { stats } from '../api';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
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

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    stats.get()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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
    </div>
  );
}
