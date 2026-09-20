'use client';

import { useState, useEffect } from 'react';
import { Activity, RefreshCw, Power, Laptop, Globe, Clock } from 'lucide-react';

export default function AdminSessionsPage() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  async function fetchSessions() {
    setLoading(true);
    try {
      const res = await fetch('/api/admin/sessions');
      const json = await res.json();
      if (json.ok) {
        setSessions(json.sessions || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchSessions();
  }, []);

  async function forceLogout(sessionId: number) {
    if (!confirm('Force logout this active desktop session? The user will be locked within 45 seconds.')) {
      return;
    }
    try {
      const res = await fetch('/api/admin/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });
      const json = await res.json();
      if (json.ok) {
        fetchSessions();
      }
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="space-y-6 pt-12 md:pt-0">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">Active Sessions</h2>
          <p className="text-xs text-[#8b97a7] mt-0.5">
            View live connected desktop instances and remotely terminate sessions
          </p>
        </div>
        <button
          onClick={fetchSessions}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-xl border border-[#232c39] bg-[#141a24] px-4 py-2 text-xs font-medium text-[#8b97a7] hover:text-white hover:border-[#3b4657] transition disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      <div className="rounded-2xl border border-[#232c39] bg-[#141a24] overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-[#232c39] bg-[#10151f] text-[#8b97a7] font-semibold">
              <tr>
                <th className="px-5 py-3.5">User</th>
                <th className="px-5 py-3.5">PC / Machine</th>
                <th className="px-5 py-3.5">Device ID</th>
                <th className="px-5 py-3.5">IP Address</th>
                <th className="px-5 py-3.5">Last Seen</th>
                <th className="px-5 py-3.5">Expires</th>
                <th className="px-5 py-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#232c39]/50">
              {loading && sessions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-[#8b97a7]">
                    Loading sessions...
                  </td>
                </tr>
              ) : sessions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-[#5f6b7a]">
                    No active sessions found.
                  </td>
                </tr>
              ) : (
                sessions.map((s) => (
                  <tr key={s.id} className="hover:bg-[#19212d]/50 transition">
                    <td className="px-5 py-4 whitespace-nowrap">
                      <div className="font-semibold text-white">{s.username}</div>
                      <span className="inline-block text-[10px] text-[#2ee6a6]">Active Online</span>
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap text-white">
                      <div className="flex items-center gap-1.5">
                        <Laptop className="h-3.5 w-3.5 text-[#8b97a7]" />
                        <span>{s.pc_name || 'Windows Desktop'}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap font-mono text-[11px] text-[#5f6b7a]">
                      {s.device_id ? s.device_id.slice(0, 16) + '...' : '-'}
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap text-[#8b97a7]">
                      <div className="flex items-center gap-1.5">
                        <Globe className="h-3.5 w-3.5 text-[#5f6b7a]" />
                        <span>{s.ip_address || '-'}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap text-[#8b97a7]">
                      <div className="flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 text-[#5f6b7a]" />
                        <span>{new Date(s.last_seen_at).toLocaleTimeString()}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap text-[#5f6b7a]">
                      {new Date(s.expires_at).toLocaleTimeString()}
                    </td>
                    <td className="px-5 py-4 text-right whitespace-nowrap">
                      <button
                        onClick={() => forceLogout(s.id)}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-[#ff5c7a]/30 bg-[#ff5c7a]/10 px-3 py-1.5 text-xs font-semibold text-[#ff5c7a] hover:bg-[#ff5c7a]/20 transition"
                      >
                        <Power className="h-3.5 w-3.5" />
                        <span>Force Logout</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
