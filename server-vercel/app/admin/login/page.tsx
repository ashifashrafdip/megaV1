'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Lock, User, AlertCircle, Loader2 } from 'lucide-react';

export default function AdminLoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();
      if (!res.ok || !data.ok) {
        setError(data.message || 'Invalid login credentials');
        setLoading(false);
        return;
      }

      router.push('/admin');
      router.refresh();
    } catch (err: any) {
      setError(err.message || 'Network error occurred');
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4 bg-[#0b0e14]">
      <div className="w-full max-w-md rounded-2xl border border-[#232c39] bg-[#141a24] p-8 shadow-2xl shadow-black/50">
        <div className="mb-8 text-center">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-[#6d5efc]/15 text-[#6d5efc] border border-[#6d5efc]/30 mb-3">
            <Lock className="h-6 w-6" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white">Admin Console</h2>
          <p className="text-xs text-[#8b97a7] mt-1">Sign in to manage users, licenses and target links</p>
        </div>

        {error && (
          <div className="mb-6 flex items-center gap-2 rounded-xl border border-[#ff5c7a]/30 bg-[#ff5c7a]/10 p-3 text-sm text-[#ff5c7a]">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-[#8b97a7] mb-1.5">Username</label>
            <div className="relative">
              <User className="absolute left-3.5 top-3 h-4 w-4 text-[#5f6b7a]" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="superadmin"
                className="w-full rounded-xl border border-[#232c39] bg-[#10151f] pl-10 pr-4 py-2.5 text-sm text-white placeholder-[#5f6b7a] focus:border-[#6d5efc] focus:outline-none focus:ring-1 focus:ring-[#6d5efc] transition"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#8b97a7] mb-1.5">Password</label>
            <div className="relative">
              <Lock className="absolute left-3.5 top-3 h-4 w-4 text-[#5f6b7a]" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-xl border border-[#232c39] bg-[#10151f] pl-10 pr-4 py-2.5 text-sm text-white placeholder-[#5f6b7a] focus:border-[#6d5efc] focus:outline-none focus:ring-1 focus:ring-[#6d5efc] transition"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center rounded-xl bg-gradient-to-r from-[#6d5efc] to-[#5846f6] py-3 text-sm font-semibold text-white shadow-lg shadow-[#6d5efc]/25 hover:opacity-95 disabled:opacity-50 transition"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Signing in...
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <div className="mt-8 text-center text-xs text-[#5f6b7a]">
          Default superadmin: <span className="font-mono text-[#8b97a7]">superadmin</span> / <span className="font-mono text-[#8b97a7]">Admin@12345</span>
        </div>
      </div>
    </div>
  );
}
