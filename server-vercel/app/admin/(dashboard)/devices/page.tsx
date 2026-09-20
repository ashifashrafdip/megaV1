'use client';

import { useState, useEffect } from 'react';
import { Laptop, RefreshCw, CheckCircle2, XCircle, Clock } from 'lucide-react';

export default function AdminDevicesPage() {
  const [devices, setDevices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  async function fetchDevices() {
    setLoading(true);
    try {
      const res = await fetch('/api/admin/devices');
      const json = await res.json();
      if (json.ok) {
        setDevices(json.devices || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchDevices();
  }, []);

  async function handleToggleAuth(id: number, currentAuth: number) {
    const action = currentAuth ? 'revoke' : 'authorize';
    try {
      const res = await fetch('/api/admin/devices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_row_id: id, action }),
      });
      const json = await res.json();
      if (json.ok) {
        fetchDevices();
      }
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="space-y-6 pt-12 md:pt-0">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">Registered Hardware Devices</h2>
          <p className="text-xs text-[#8b97a7] mt-0.5">
            Hardware fingerprints bound to team member user accounts
          </p>
        </div>
        <button
          onClick={fetchDevices}
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
                <th className="px-5 py-3.5">PC / Machine Name</th>
                <th className="px-5 py-3.5">Hardware Device ID (SHA256)</th>
                <th className="px-5 py-3.5">Authorized</th>
                <th className="px-5 py-3.5">Last Seen</th>
                <th className="px-5 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#232c39]/50">
              {loading && devices.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-[#8b97a7]">
                    Loading devices...
                  </td>
                </tr>
              ) : devices.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-[#5f6b7a]">
                    No devices registered yet. Devices register on first successful desktop login.
                  </td>
                </tr>
              ) : (
                devices.map((d) => (
                  <tr key={d.id} className="hover:bg-[#19212d]/50 transition">
                    <td className="px-5 py-4 font-semibold text-white whitespace-nowrap">
                      {d.username}
                    </td>
                    <td className="px-5 py-4 text-white whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <Laptop className="h-3.5 w-3.5 text-[#8b97a7]" />
                        <span>{d.pc_name || 'Windows Host'}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4 font-mono text-[11px] text-[#8b97a7] break-all max-w-xs">
                      {d.device_id}
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap">
                      {d.is_authorized ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold bg-[#2ee6a6]/10 text-[#2ee6a6]">
                          <CheckCircle2 className="h-3 w-3" />
                          Authorized
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold bg-[#ff5c7a]/10 text-[#ff5c7a]">
                          <XCircle className="h-3 w-3" />
                          Revoked
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-4 text-[#8b97a7] whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <Clock className="h-3 w-3 text-[#5f6b7a]" />
                        <span>{new Date(d.last_seen_at).toLocaleString()}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4 text-right whitespace-nowrap">
                      <button
                        onClick={() => handleToggleAuth(d.id, d.is_authorized)}
                        className={`px-3 py-1.5 rounded-xl border text-xs font-semibold transition ${
                          d.is_authorized
                            ? 'border-[#ff5c7a]/30 bg-[#ff5c7a]/10 text-[#ff5c7a] hover:bg-[#ff5c7a]/20'
                            : 'border-[#2ee6a6]/30 bg-[#2ee6a6]/10 text-[#2ee6a6] hover:bg-[#2ee6a6]/20'
                        }`}
                      >
                        {d.is_authorized ? 'Revoke Device' : 'Authorize'}
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
