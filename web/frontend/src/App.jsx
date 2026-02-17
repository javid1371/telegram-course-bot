import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { isAuthenticated } from './api';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Courses from './pages/Courses';
import CourseEdit from './pages/CourseEdit';
import LessonEdit from './pages/LessonEdit';
import Users from './pages/Users';
import RegistrationFields from './pages/RegistrationFields';
import MediaLibrary from './pages/MediaLibrary';

function PrivateRoute({ children }) {
  return isAuthenticated() ? children : <Navigate to="/login" />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-center" toastOptions={{ style: { fontFamily: 'Vazirmatn' } }} />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <PrivateRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/courses" element={<Courses />} />
                  <Route path="/courses/:id" element={<CourseEdit />} />
                  <Route path="/lessons/:id" element={<LessonEdit />} />
                  <Route path="/users" element={<Users />} />
                  <Route path="/registration-fields" element={<RegistrationFields />} />
                  <Route path="/media" element={<MediaLibrary />} />
                </Routes>
              </Layout>
            </PrivateRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
