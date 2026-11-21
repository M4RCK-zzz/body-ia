import { createBrowserRouter } from "react-router-dom";
import { LoginPage } from "@/features/auth/LoginPage";
import { RegisterPage } from "@/features/auth/RegisterPage";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { ProfileDetailPage } from "@/features/profiles/ProfileDetailPage";
import { ProfilesPage } from "@/features/profiles/ProfilesPage";
import { AppShell } from "../layouts/AppShell";
import { NotFoundPage } from "./NotFoundPage";

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
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);