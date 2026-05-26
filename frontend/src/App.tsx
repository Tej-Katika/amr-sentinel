import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import AntibiogramPage from "./pages/AntibiogramPage";
import AlertsPage from "./pages/AlertsPage";
import ChatPage from "./pages/ChatPage";
import GLASSPage from "./pages/GLASSPage";

function isAuthed(): boolean {
  return Boolean(localStorage.getItem("amr_token"));
}

function Protected({ children }: { children: JSX.Element }) {
  return isAuthed() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="antibiogram" element={<AntibiogramPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="glass" element={<GLASSPage />} />
      </Route>
    </Routes>
  );
}
