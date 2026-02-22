import { NavLink, useNavigate } from 'react-router-dom';
import { clearToken } from '../api';

const NAV_ITEMS = [
  { to: '/', label: 'داشبورد', icon: '📊' },
  { to: '/courses', label: 'دوره‌ها', icon: '📚' },
  { to: '/users', label: 'کاربران', icon: '👥' },
  { to: '/lesson-progress', label: 'روند دروس', icon: '📊' },
  { to: '/registration-fields', label: 'فرم ثبت‌نام', icon: '📝' },
  { to: '/media', label: 'کتابخانه فایل‌ها', icon: '📁' },
  { to: '/settings', label: 'تنظیمات', icon: '⚙️' },
];

export default function Layout({ children }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    clearToken();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-60 bg-slate-800 text-white flex flex-col">
        <div className="p-5 border-b border-slate-700">
          <h1 className="text-lg font-bold">🎓 پنل مدیریت</h1>
          <p className="text-xs text-slate-400 mt-1">مدیریت دوره‌های آموزشی</p>
        </div>
        <nav className="flex-1 py-4">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-3 text-sm transition-colors ${
                  isActive
                    ? 'bg-slate-700 text-white border-l-4 border-blue-400'
                    : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
                }`
              }
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <button
          onClick={handleLogout}
          className="m-4 px-4 py-2 text-sm bg-red-600/20 text-red-300 rounded hover:bg-red-600/40 transition-colors"
        >
          🚪 خروج
        </button>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-6 overflow-auto bg-gray-50">
        {children}
      </main>
    </div>
  );
}
