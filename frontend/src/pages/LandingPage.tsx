import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowRight, FileText, Lock, Zap, Github } from "lucide-react";

export default function LandingPage() {
  const { t } = useTranslation();
  return (
    <div className="min-h-full">
      <header className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2">
          <div className="grid h-8 w-8 place-items-center rounded-md bg-brand-600 text-white font-bold">
            D
          </div>
          <span className="font-semibold tracking-tight">DocFormatConverter</span>
        </div>
        <nav className="flex items-center gap-2 text-sm">
          <a
            href="https://github.com/badhope/DocFormatConverter"
            target="_blank"
            rel="noreferrer"
            className="btn-ghost"
          >
            <Github className="h-4 w-4" />
            GitHub
          </a>
          <Link to="/login" className="btn-ghost">
            {t("auth.login")}
          </Link>
          <Link to="/register" className="btn-primary">
            {t("auth.register")} <ArrowRight className="h-4 w-4" />
          </Link>
        </nav>
      </header>

      <section className="mx-auto max-w-5xl px-6 py-20 text-center">
        <h1 className="bg-gradient-to-br from-brand-700 to-brand-400 bg-clip-text text-5xl font-bold tracking-tight text-transparent">
          {t("app.tagline")}
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-slate-600 dark:text-slate-300">
          Convert documents, spreadsheets, presentations, images, ebooks and structured
          data between 40+ formats. JWT or API-Key auth. Batch processing, webhooks,
          real-time progress over WebSockets.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link to="/register" className="btn-primary">
            Get started <ArrowRight className="h-4 w-4" />
          </Link>
          <Link to="/login" className="btn-secondary">
            {t("auth.login")}
          </Link>
        </div>
      </section>

      <section className="mx-auto grid max-w-5xl gap-4 px-6 pb-20 sm:grid-cols-3">
        {[
          { icon: Zap, title: "Fast", body: "Async tasks, parallel workers, batched I/O." },
          { icon: Lock, title: "Secure", body: "Argon2id, RS256 JWT, antivirus, magic-byte validation." },
          { icon: FileText, title: "40+ formats", body: "PDF, DOCX, XLSX, PPTX, MD, HTML, JSON, images, ebooks…" },
        ].map((f) => (
          <div key={f.title} className="card p-5">
            <f.icon className="h-6 w-6 text-brand-500" />
            <h3 className="mt-2 font-semibold">{f.title}</h3>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{f.body}</p>
          </div>
        ))}
      </section>

      <footer className="border-t border-slate-200 px-6 py-4 text-center text-xs text-slate-500 dark:border-slate-800">
        © {new Date().getFullYear()} DocFormatConverter · MIT
      </footer>
    </div>
  );
}
