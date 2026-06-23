import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./components/protected-route";
import { LoginPage } from "./features/auth/login-page";
import { SignupPage } from "./features/auth/signup-page";
import { DashboardPage } from "./features/dashboard/dashboard-page";
import { CompliancePage } from "./features/compliance/compliance-page";
import { ShipmentsPage } from "./features/shipments/shipments-page";
import { NewShipmentPage } from "./features/shipments/new-shipment-page";
import { ShipmentDetailPage } from "./features/shipments/shipment-detail-page";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/compliance" element={<ProtectedRoute><CompliancePage /></ProtectedRoute>} />
      <Route path="/shipments" element={<ProtectedRoute><ShipmentsPage /></ProtectedRoute>} />
      <Route path="/shipments/new" element={<ProtectedRoute><NewShipmentPage /></ProtectedRoute>} />
      <Route path="/shipments/:id" element={<ProtectedRoute><ShipmentDetailPage /></ProtectedRoute>} />
      <Route path="/" element={<Navigate to="/shipments" replace />} />
      <Route path="*" element={<Navigate to="/shipments" replace />} />
    </Routes>
  );
}
