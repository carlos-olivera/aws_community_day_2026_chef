import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Experience from "./pages/Experience";
import Presenter from "./pages/Presenter";

export default function App() {
  const linkClass = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : "");
  return (
    <div className="shell">
      <nav>
        <NavLink to="/" end className={linkClass}>Chef Andino</NavLink>
        <NavLink to="/presenter" className={linkClass}>Presentador</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Experience />} />
        <Route path="/presenter" element={<Presenter />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
