import { createBrowserRouter } from 'react-router-dom'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { AppShell } from '../layouts/AppShell'
import { NotFoundPage } from './NotFoundPage'
import { ProfileDetailPage } from "@/features/profiles/ProfileDetailPage";
import { ProfilesPage } from "@/features/profiles/ProfilesPage";

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "expedientes", element: <ProfilesPage /> },
      { path: "expedientes/:profileId", element: <ProfileDetailPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])