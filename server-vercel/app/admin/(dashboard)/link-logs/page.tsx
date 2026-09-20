'use client';

import { useState, useEffect } from 'react';
import {
  Link2,
  Search,
  RefreshCw,
  Copy,
  Check,
  ExternalLink,
  Trash2,
  Clock,
  Laptop,
} from 'lucide-react';

export default function AdminLinkLogsPage() {
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  async function fetchLogs() {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/link-logs?q=${encodeURIComponent(search)}&limit=100`);
      let json: any = null;
      try { json = await res.json(); } catch {}
      if (res.ok && json?.ok) {
        setLogs(json.logs || []);
        setTotal(json.total || 0);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchLogs();
  }, [search]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchLogs, 10000);
    return () => clearInterval(interval);
  }, [autoRefresh, search]);

  function copyToClipboard(id: number, text: string) {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  }

  async function deleteLog(id: number) {
    if (!confirm('Delete this link log?')) return;
    try {
      const res = await fetch(`/api/admin/link-logs?id=${id}`, { method: 'DELETE' });
      let json: any = null;
      try { json = await res.json(); } catch {}
      if (res.ok && json?.ok) {
        fetchLogs();
      }
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="space-y-6 pt-12 md:pt-0">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">Target Link Logs</h2>
          <p className="text-xs text-[#8b97a7] mt-0.5">
            Real-time feed of URLs submitted and automated across desktop sessions
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-[#8b97a7] cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-[#232c39] bg-[#10151f] text-[#6d5efc] focus:ring-0"
            />
            <span>Auto-refresh (10s)</span>
          </label>

          <button
            onClick={fetchLogs}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl border border-[#232c39] bg-[#141a24] px-4 py-2 text-xs font-medium text-[#8b97a7] hover:text-white hover:border-[#3b4657] transition disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Search & Counter */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-center">
        <div className="relative w-full sm:max-w-md">
          <Search className="absolute left-3.5 top-3 h-4 w-4 text-[#5f6b7a]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search target URL, user, device ID..."
            className="w-full rounded-xl border border-[#232c39] bg-[#141a24] pl-10 pr-4 py-2.5 text-xs text-white placeholder-[#5f6b7a] focus:border-[#6d5efc] focus:outline-none transition"
          />
        </div>
        <div className="text-xs text-[#8b97a7] self-end sm:self-center">
          Total links captured: <span className="font-bold text-white">{total}</span>
        </div>
      </div>

      {/* Logs Table */}
      <div className="rounded-2xl border border-[#232c39] bg-[#141a24] overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-[#232c39] bg-[#10151f] text-[#8b97a7] font-semibold">
              <tr>
                <th className="px-5 py-3.5">Time</th>
                <th className="px-5 py-3.5">User</th>
                <th className="px-5 py-3.5">Target Verification URL</th>
                <th className="px-5 py-3.5">Browser</th>
                <th className="px-5 py-3.5">Device Fingerprint</th>
                <th className="px-5 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#232c39]/50">
              {loading && logs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-[#8b97a7]">
                    Loading links...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-[#5f6b7a]">
                    No links logged yet. When desktop users click Start, links will appear here instantly.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-[#19212d]/50 transition">
                    <td className="px-5 py-3.5 whitespace-nowrap text-[#8b97a7]">
                      <div className="flex items-center gap-1.5">
                        <Clock className="h-3 w-3 text-[#5f6b7a]" />
                        <span>{new Date(log.created_at).toLocaleString()}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 font-semibold text-white whitespace-nowrap">
                      {log.username || 'Unknown'}
                    </td>
                    <td className="px-5 py-3.5 max-w-md">
                      <div className="font-mono text-[#e6edf3] break-all select-all text-[11px] bg-[#10151f] p-2 rounded-lg border border-[#232c39]/70">
                        {log.url}
                      </div>
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      <span className="inline-block px-2.5 py-1 rounded-full text-[10px] font-semibold bg-[#6d5efc]/15 text-[#6d5efc] border border-[#6d5efc]/30 uppercase">
                        {log.browser || 'adspower'}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap text-[#5f6b7a] font-mono text-[10px]">
                      <div className="flex items-center gap-1.5">
                        <Laptop className="h-3 w-3" />
                        <span>{log.device_id ? log.device_id.slice(0, 16) + '...' : '-'}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-right whitespace-nowrap space-x-1.5">
                      <button
                        title="Copy URL"
                        onClick={() => copyToClipboard(log.id, log.url)}
                        className="p-1.5 rounded-lg border border-[#232c39] bg-[#10151f] text-[#8b97a7] hover:text-white hover:border-[#3b4657] transition"
                      >
                        {copiedId === log.id ? (
                          <Check className="h-3.5 w-3.5 text-[#2ee6a6]" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                      <a
                        href={log.url}
                        target="_blank"
                        rel="noreferrer"
                        title="Open URL"
                        className="inline-block p-1.5 rounded-lg border border-[#232c39] bg-[#10151f] text-[#8b97a7] hover:text-white hover:border-[#3b4657] transition"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                      <button
                        title="Delete entry"
                        onClick={() => deleteLog(log.id)}
                        className="p-1.5 rounded-lg border border-[#ff5c7a]/30 bg-[#ff5c7a]/10 text-[#ff5c7a] hover:bg-[#ff5c7a]/20 transition"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
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
