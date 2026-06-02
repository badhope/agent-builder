import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="grid min-h-full place-items-center p-6 text-center">
      <div>
        <h1 className="text-6xl font-bold text-slate-300 dark:text-slate-700">404</h1>
        <p className="mt-2 text-slate-600 dark:text-slate-300">
          The page you’re looking for doesn’t exist.
        </p>
        <Link to="/" className="btn-primary mt-4">
          Go home
        </Link>
      </div>
    </div>
  );
}
