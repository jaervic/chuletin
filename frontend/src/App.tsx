import { useEffect, useState } from "react";
import { api } from "./lib/api";

export default function App() {
  const [status, setStatus] = useState<string>("comprobando…");

  useEffect(() => {
    api
      .health()
      .then((data) => setStatus(data.status === "ok" ? "conectado" : "degradado"))
      .catch(() => setStatus("sin conexión"));
  }, []);

  return (
    <main className="flex min-h-full items-center justify-center bg-slate-950 text-slate-100">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Chuletín</h1>
        <p className="mt-2 text-sm text-slate-400">
          Tus apuntes, con fuentes verificables.
        </p>
        <p className="mt-6 text-xs uppercase tracking-widest text-slate-500">
          API: {status}
        </p>
      </div>
    </main>
  );
}
