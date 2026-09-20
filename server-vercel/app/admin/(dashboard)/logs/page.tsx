'use client';

import { useState, useEffect } from 'react';
import { FileText, RefreshCw, ShieldAlert, CheckCircle2, XCircle, Clock } from 'lucide-react';

export default function AdminLogsPage() {
  const [activeTab, setActiveTab] = useState<'activity' | 'login'>('activity');
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  async function fetchLogs(type: 'activity' | 'login') {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/logs?type=${type}`);
      let json: any = null;
      try { json = await res.json(); } catch {}
      if (res.ok && json?.ok) {
        setLogs(json.logs || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchLogs(activeTab);
  }, [activeTab]);

  return (
    <div className="space-y-6 pt-12 md:pt-0">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">System & Audit Logs</h2>
          <p className="text-xs text-[#8b97a7] mt-0.5">
            Security audit trail, authentication history, and administrative activity
          </p>
        </div>

        <button
          onClick={() => fetchLogs(activeTab)}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-xl border border-[#232c39] bg-[#141a24] px-4 py-2 text-xs font-medium text-[#8b97a7] hover:text-white hover:border-[#3b4657] transition disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-[#232c39] pb-3">
        <button
          onClick={() => setActiveTab('activity')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeTab === 'activity'
              ? 'bg-[#6d5efc] text-white shadow-md shadow-[#6d5efc]/25'
              : 'text-[#8b97a7] hover:bg-[#141a24] hover:text-white'
          }`}
        >
          Activity Logs
        </button>
        <button
          onClick={() => setActiveTab('login')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeTab === 'login'
              ? 'bg-[#6d5efc] text-white shadow-md shadow-[#6d5efc]/25'
              : 'text-[#8b97a7] hover:bg-[#141a24] hover:text-white'
          }`}
        >
          Login History
        </button>
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-[#232c39] bg-[#141a24] overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          {activeTab === 'activity' ? (
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[#232c39] bg-[#10151f] text-[#8b97a7] font-semibold">
                <tr>
                  <th className="px-5 py-3.5">Time</th>
                  <th className="px-5 py-3.5">User</th>
                  <th className="px-5 py-3.5">Action</th>
                  <th className="px-5 py-3.5">IP Address</th>
                  <th className="px-5 py-3.5">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#232c39]/50">
                {loading && logs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-[#8b97a7]">
                      Loading logs...
                    </td>
                  </tr>
                ) : logs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-[#5f6b7a]">
                      No activity logs recorded yet.
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => (
                    <tr key={log.id} className="hover:bg-[#19212d]/50 transition">
                      <td className="px-5 py-4 whitespace-nowrap text-[#8b97a7]">
                        <div className="flex items-center gap-1.5">
                          <Clock className="h-3 w-3 text-[#5f6b7a]" />
                          <span>{new Date(log.created_at).toLocaleString()}</span>
                        </div>
                      </td>
                      <td className="px-5 py-4 font-semibold text-white whitespace-nowrap">
                        {log.username || 'System'}
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap">
                        <span className="inline-block px-2.5 py-1 rounded-full text-[10px] font-semibold bg-[#232c39] text-[#00c2ff] uppercase">
                          {log.action}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-[#8b97a7] font-mono text-[11px] whitespace-nowrap">
                        {log.ip_address || '-'}
                      </td>
                      <td className="px-5 py-4 text-[#8b97a7] font-mono text-[11px] break-all max-w-md">
                        {log.details || '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[#232c39] bg-[#10151f] text-[#8b97a7] font-semibold">
                <tr>
                  <th className="px-5 py-3.5">Time</th>
                  <th className="px-5 py-3.5">Username Attempted</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">IP Address</th>
                  <th className="px-5 py-3.5">Failure Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#232c39]/50">
                {loading && logs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-[#8b97a7]">
                      Loading history...
                    </td>
                  </tr>
                ) : logs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-[#5f6b7a]">
                      No login attempts recorded yet.
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => (
                    <tr key={log.id} className="hover:bg-[#19212d]/50 transition">
                      <td className="px-5 py-4 whitespace-nowrap text-[#8b97a7]">
                        <div className="flex items-center gap-1.5">
                          <Clock className="h-3 w-3 text-[#5f6b7a]" />
                          <span>{new Date(log.created_at).toLocaleString()}</span>
                        </div>
                      </td>
                      <td className="px-5 py-4 font-semibold text-white whitespace-nowrap">
                        {log.username}
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap">
                        {log.success ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold bg-[#2ee6a6]/10 text-[#2ee6a6]">
                            <CheckCircle2 className="h-3 w-3" />
                            Success
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold bg-[#ff5c7a]/10 text-[#ff5c7a]">
                            <XCircle className="h-3 w-3" />
                            Failed
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-[#8b97a7] font-mono text-[11px] whitespace-nowrap">
                        {log.ip_address || '-'}
                      </td>
                      <td className="px-5 py-4 font-mono text-[11px] text-[#ff5c7a] whitespace-nowrap">
                        {log.reason || '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
