import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Members from "@/pages/Members";
import Contributions from "@/pages/Contributions";
import Benefits from "@/pages/Benefits";
import MedicalAid from "@/pages/MedicalAid";
import DeathAssistance from "@/pages/DeathAssistance";
import Financials from "@/pages/Financials";
import Committee from "@/pages/Committee";
import Meetings from "@/pages/Meetings";
import Reports from "@/pages/Reports";
import Users from "@/pages/Users";
import Notifications from "@/pages/Notifications";
import Audit from "@/pages/Audit";

function ProtectedRoute({ children }) {
  const { user } = useAuth();
  if (user === null) return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50">
      <div className="flex items-center gap-3 text-stone-600">
        <div className="w-5 h-5 border-2 border-green-800 border-t-transparent rounded-full animate-spin" />
        <span className="font-medium">Loading...</span>
      </div>
    </div>
  );
  if (user === false) return <Navigate to="/login" replace />;
  return children;
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user && user !== null && user !== false ? <Navigate to="/dashboard" replace /> : <Login />} />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="members" element={<Members />} />
        <Route path="contributions" element={<Contributions />} />
        <Route path="benefits" element={<Benefits />} />
        <Route path="medical-aid" element={<MedicalAid />} />
        <Route path="death-assistance" element={<DeathAssistance />} />
        <Route path="financials" element={<Financials />} />
        <Route path="committee" element={<Committee />} />
        <Route path="meetings" element={<Meetings />} />
        <Route path="reports" element={<Reports />} />
        <Route path="users" element={<Users />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="audit" element={<Audit />} />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
