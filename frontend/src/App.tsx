import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AlertPage } from "./pages/AlertPage";
import { FeedPage } from "./pages/FeedPage";
import { LoginPage } from "./pages/LoginPage";
import { MetricsPage } from "./pages/MetricsPage";
import { NotFoundPage } from "./pages/NotFoundPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Layout />}>
        <Route path="/" element={<FeedPage />} />
        <Route path="/alerts/:id" element={<AlertPage />} />
        <Route path="/metrics" element={<MetricsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
