import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./components/protected-route";
import { LoginPage } from "./features/auth/login-page";
import { SignupPage } from "./features/auth/signup-page";
import { VerifyEmailPage } from "./features/auth/verify-email-page";
import { ForgotPasswordPage } from "./features/auth/forgot-password-page";
import { ResetPasswordPage } from "./features/auth/reset-password-page";
import { DashboardPage } from "./features/dashboard/dashboard-page";
import { CountryComplianceCheckerPage } from "./features/compliance/country-compliance-checker-page";
import { HsnFinderPage } from "./features/hsn/hsn-finder-page";
import { IncentiveFinderPage } from "./features/incentives/incentive-finder-page";
import { ExportQuotePage } from "./features/calculators/export-quote-page";
import { ShipmentsPage } from "./features/shipments/shipments-page";
import { NewShipmentPage } from "./features/shipments/new-shipment-page";
import { ShipmentDetailPage } from "./features/shipments/shipment-detail-page";
import { DocumentBuilderPage } from "./features/documents/document-builder-page";
import { DocumentVerifierPage } from "./features/documents/document-verifier-page";
import { ToolsPage } from "./features/tools/tools-page";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<SignupPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/tools" element={<ProtectedRoute><ToolsPage /></ProtectedRoute>} />
      <Route path="/hsn" element={<ProtectedRoute><HsnFinderPage /></ProtectedRoute>} />
      <Route path="/incentives" element={<ProtectedRoute><IncentiveFinderPage /></ProtectedRoute>} />
      <Route path="/calculators/export-quote" element={<ProtectedRoute><ExportQuotePage /></ProtectedRoute>} />
      <Route path="/compliance" element={<Navigate to="/compliance/checker" replace />} />
      <Route path="/compliance/checker" element={<ProtectedRoute><CountryComplianceCheckerPage /></ProtectedRoute>} />
      <Route path="/shipments" element={<ProtectedRoute><ShipmentsPage /></ProtectedRoute>} />
      <Route path="/shipments/new" element={<ProtectedRoute><NewShipmentPage /></ProtectedRoute>} />
      <Route path="/shipments/:id" element={<ProtectedRoute><ShipmentDetailPage /></ProtectedRoute>} />
      <Route path="/documents" element={<ProtectedRoute><DocumentBuilderPage /></ProtectedRoute>} />
      <Route path="/document-verifier" element={<ProtectedRoute><DocumentVerifierPage /></ProtectedRoute>} />
      <Route path="/document-verifier/:runId" element={<ProtectedRoute><DocumentVerifierPage /></ProtectedRoute>} />
      <Route path="/" element={<Navigate to="/tools" replace />} />
      <Route path="*" element={<Navigate to="/tools" replace />} />
    </Routes>
  );
}
