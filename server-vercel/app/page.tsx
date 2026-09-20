import Link from 'next/link';

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6 text-center">
      <div className="relative mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-tr from-[#6d5efc] to-[#00c2ff] p-0.5 shadow-xl shadow-[#6d5efc]/20">
        <div className="flex h-full w-full items-center justify-center rounded-[14px] bg-[#0b0e14]">
          <span className="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-[#6d5efc] to-[#00c2ff]">
            AH
          </span>
        </div>
      </div>

      <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
        Automation Hub Server
      </h1>
      <p className="mt-3 max-w-md text-sm text-[#8b97a7]">
        Vercel Serverless Backend with Neon PostgreSQL for desktop automation auth, link tracking, and device management.
      </p>

      <div className="mt-8 flex flex-wrap gap-4 justify-center">
        <Link
          href="/admin/login"
          className="rounded-xl bg-gradient-to-r from-[#6d5efc] to-[#5846f6] px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-[#6d5efc]/25 hover:opacity-95 transition"
        >
          Open Admin Panel
        </Link>
        <Link
          href="/api/setup?secret=dev-desktop-app-key-change-me"
          className="rounded-xl border border-[#232c39] bg-[#141a24] px-6 py-3 text-sm font-semibold text-[#8b97a7] hover:text-white hover:border-[#3b4657] transition"
        >
          Initialize Database
        </Link>
      </div>

      <div className="mt-12 rounded-xl border border-[#232c39] bg-[#10151f] p-4 max-w-md text-left text-xs text-[#8b97a7]">
        <div className="flex items-center gap-2 mb-2 font-mono font-medium text-[#2ee6a6]">
          <span className="h-2 w-2 rounded-full bg-[#2ee6a6] animate-pulse"></span>
          Serverless API Ready
        </div>
        <p>• API Endpoints compatible with desktop app requests (.php)</p>
        <p>• Neon PostgreSQL Connection Pooling Enabled</p>
        <p>• Single Active Session & 45s Heartbeats Protected</p>
      </div>
    </div>
  );
}
