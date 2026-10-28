import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Spinner } from "@repo/ui";
import { ProtectedRoute } from "./components/protected-route";
import { LoginPage } from "./features/auth/login-page";
import { SignupPage } from "./features/auth/signup-page";
import { VerifyEmailPage } from "./features/auth/verify-email-page";
import { ForgotPasswordPage } from "./features/auth/forgot-password-page";
import { ResetPasswordPage } from "./features/auth/reset-password-page";

const DashboardPage = lazy(() =>
  import("./features/dashboard/dashboard-page").then((m) => ({ default: m.DashboardPage }))
);
const CountryComplianceCheckerPage = lazy(() =>
  import("./features/compliance/country-compliance-checker-page").then((m) => ({
    default: m.CountryComplianceCheckerPage,
  }))
);
const HsnFinderPage = lazy(() =>
  import("./features/hsn/hsn-finder-page").then((m) => ({ default: m.HsnFinderPage }))
);
const IncentiveFinderPage = lazy(() =>
  import("./features/incentives/incentive-finder-page").then((m) => ({
    default: m.IncentiveFinderPage,
  }))
);
const ExportQuotePage = lazy(() =>
  import("./features/calculators/export-quote-page").then((m) => ({ default: m.ExportQuotePage }))
);
const ShipmentsPage = lazy(() =>
  import("./features/shipments/shipments-page").then((m) => ({ default: m.ShipmentsPage }))
);
const NewShipmentPage = lazy(() =>
  import("./features/shipments/new-shipment-page").then((m) => ({ default: m.NewShipmentPage }))
);
const ShipmentDetailPage = lazy(() =>
  import("./features/shipments/shipment-detail-page").then((m) => ({
    default: m.ShipmentDetailPage,
  }))
);
const DocumentBuilderPage = lazy(() =>
  import("./features/documents/document-builder-page").then((m) => ({
    default: m.DocumentBuilderPage,
  }))
);
const DocumentVerifierPage = lazy(() =>
  import("./features/documents/document-verifier-page").then((m) => ({
    default: m.DocumentVerifierPage,
  }))
);
const ToolsPage = lazy(() =>
  import("./features/tools/tools-page").then((m) => ({ default: m.ToolsPage }))
);

export default function App() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-canvas">
          <Spinner />
        </div>
      }
    >
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<SignupPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tools"
          element={
            <ProtectedRoute>
              <ToolsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/hsn"
          element={
            <ProtectedRoute>
              <HsnFinderPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/incentives"
          element={
            <ProtectedRoute>
              <IncentiveFinderPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/calculators/export-quote"
          element={
            <ProtectedRoute>
              <ExportQuotePage />
            </ProtectedRoute>
          }
        />
        <Route path="/compliance" element={<Navigate to="/compliance/checker" replace />} />
        <Route
          path="/compliance/checker"
          element={
            <ProtectedRoute>
              <CountryComplianceCheckerPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/shipments"
          element={
            <ProtectedRoute>
              <ShipmentsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/shipments/new"
          element={
            <ProtectedRoute>
              <NewShipmentPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/shipments/:id"
          element={
            <ProtectedRoute>
              <ShipmentDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/documents"
          element={
            <ProtectedRoute>
              <DocumentBuilderPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/document-verifier"
          element={
            <ProtectedRoute>
              <DocumentVerifierPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/document-verifier/:runId"
          element={
            <ProtectedRoute>
              <DocumentVerifierPage />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/tools" replace />} />
        <Route path="*" element={<Navigate to="/tools" replace />} />
      </Routes>
    </Suspense>
  );
}
