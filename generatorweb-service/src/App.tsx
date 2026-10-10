import { Route, Routes } from "react-router-dom";

import { AppProvider } from "@/app/AppProvider";
import { AppLayout } from "@/components/layout/AppLayout";
import { GenerationPage } from "@/pages/GenerationPage";
import { HistoryPage } from "@/pages/HistoryPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { SettingsPage } from "@/pages/SettingsPage";

export function App() {
  return (
    <AppProvider>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<GenerationPage />} />
          <Route path="historique" element={<HistoryPage />} />
          <Route path="parametres" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </AppProvider>
  );
}
