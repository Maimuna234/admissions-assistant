import { useState } from "react";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import Register from "./pages/Register";
import AdminDashboard from "./pages/admin/AdminDashboard";
import TutorDashboard from "./pages/TutorDashboard";

type AuthScreen = "login" | "register";

export default function AppShell() {
  const { user, isAuthenticated, dbReady } = useAuth();
  const [authScreen, setAuthScreen] = useState<AuthScreen>("login");

  if (!dbReady) {
    return <div className="min-h-screen flex items-center justify-center">Initialising Admissions Assistant...</div>;
  }

  if (!isAuthenticated || !user) {
    return authScreen === "login"
      ? <Login onNavigateRegister={() => setAuthScreen("register")} />
      : <Register onNavigateLogin={() => setAuthScreen("login")} />;
  }

  return user.role === "admin" ? <AdminDashboard /> : <TutorDashboard />;
}
