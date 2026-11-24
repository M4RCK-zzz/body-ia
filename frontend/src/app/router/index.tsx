import { createBrowserRouter } from "react-router-dom";
import { LoginPage } from "@/features/auth/LoginPage";
import { RegisterPage } from "@/features/auth/RegisterPage";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { ProfileDetailPage } from "@/features/profiles/ProfileDetailPage";
import { ProfilesPage } from "@/features/profiles/ProfilesPage";
import { CaptureHomePage } from "@/features/capture/CaptureHomePage";
import { CapturePage } from "@/features/capture/CapturePage";
import { PoseListPage } from "@/features/pose/PoseListPage";
import { PoseAnalysisDetailPage } from "@/features/pose/PoseAnalysisDetailPage";
import { ReportsPage } from "@/features/reports/ReportsPage";
import { ReportDetailPage } from "@/features/reports/ReportDetailPage";
import { AnalyticsPage } from "@/features/analytics/AnalyticsPage";
import { SimulationsPage } from "@/features/simulations/SimulationsPage";
import { SimulationWorkspacePage } from "@/features/simulations/SimulationWorkspacePage";
import { SimulationDetailPage } from "@/features/simulations/SimulationDetailPage";
import { AdminPage } from "@/features/admin/AdminPage";
import { RequireAdmin } from "@/features/admin/RequireAdmin";
import { AppShell } from "../layouts/AppShell";
import { NotFoundPage } from "./NotFoundPage";
import { LazyViewer } from "./LazyViewer";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/registro", element: <RegisterPage /> },
  {
    path: "/",
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "expedientes", element: <ProfilesPage /> },
      { path: "expedientes/:profileId", element: <ProfileDetailPage /> },
      { path: "capture", element: <CaptureHomePage /> },
      { path: "capture/:profileId", element: <CapturePage /> },
      { path: "analyses", element: <PoseListPage /> },
      { path: "analyses/:id", element: <PoseAnalysisDetailPage /> },
      { path: "reports", element: <ReportsPage /> },
      { path: "reports/:reportId", element: <ReportDetailPage /> },
      { path: "analytics/:profileId", element: <AnalyticsPage /> },
      { path: "simulations", element: <SimulationsPage /> },
      { path: "simulations/:profileId", element: <SimulationWorkspacePage /> },
      { path: "simulations/:profileId/:simulationId", element: <SimulationDetailPage /> },
      {
        path: "admin",
        element: (
          <RequireAdmin>
            <AdminPage />
          </RequireAdmin>
        ),
      },
      { path: "viewer", element: <LazyViewer /> },
      { path: "viewer/:profileId", element: <LazyViewer /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);