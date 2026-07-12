export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-slate-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-slate-900">OmniAgent</h1>
          <p className="mt-1 text-sm text-slate-500">
            Ton copilote IA pour candidater plus vite.
          </p>
        </div>
        {children}
      </div>
    </main>
  );
}