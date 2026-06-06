import { Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "./components/protected-route";
import { DashboardPage } from "./features/dashboard/dashboard-page";
import { LoginPage } from "./features/auth/login-page";
import { SignupPage } from "./features/auth/signup-page";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
