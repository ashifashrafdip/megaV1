'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Users,
  Activity,
  Link2,
  Laptop,
  ShieldCheck,
  RefreshCw,
  ExternalLink,
  Clock,
} from 'lucide-react';

export default function AdminDashboardPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  async function fetchStats() {
    setLoading(true);
    try {
      const res = await fetch('/api/admin/stats');
      const json = await res.json();
      if (json.ok) {
        setData(json);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 15000); // 15s auto-refresh
    return () => clearInterval(interval);
  }, []);

  const stats = data?.stats || {
    total_users: 0,
    online_sessions: 0,
    today_links: 0,
    total_links: 0,
    total_devices: 0,
    active_licenses: 0,
  };

  return (
    <div className="space-y-8 pt-12 md:pt-0">
      {/* Top Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">System Overview</h2>
          <p className="text-xs text-[#8b97a7] mt-0.5">
            Real-time monitoring of desktop automation sessions and links
          </p>
        </div>
        <button
          onClick={fetchStats}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-xl border border-[#232c39] bg-[#141a24] px-4 py-2 text-xs font-medium text-[#8b97a7] hover:text-white hover:border-[#3b4657] transition disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-[#232c39] bg-[#141a24] p-5 shadow-lg shadow-black/20">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#8b97a7]">Total Users</span>
            <div className="rounded-xl bg-[#6d5efc]/15 p-2 text-[#6d5efc]">
              <Users className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-3 text-2xl font-bold text-white">{stats.total_users}</div>
          <div className="mt-1 text-[11px] text-[#2ee6a6]">{stats.active_licenses} active licenses</div>
        </div>

        <div className="rounded-2xl border border-[#232c39] bg-[#141a24] p-5 shadow-lg shadow-black/20">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#8b97a7]">Online Sessions</span>
            <div className="rounded-xl bg-[#2ee6a6]/15 p-2 text-[#2ee6a6]">
              <Activity className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-3 text-2xl font-bold text-white">{stats.online_sessions}</div>
          <div className="mt-1 text-[11px] text-[#8b97a7]">Running app in last 3m</div>
        </div>

        <div className="rounded-2xl border border-[#232c39] bg-[#141a24] p-5 shadow-lg shadow-black/20">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#8b97a7]">Links Today</span>
            <div className="rounded-xl bg-[#00c2ff]/15 p-2 text-[#00c2ff]">
              <Link2 className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-3 text-2xl font-bold text-white">{stats.today_links}</div>
          <div className="mt-1 text-[11px] text-[#8b97a7]">{stats.total_links} total logged</div>
        </div>

        <div className="rounded-2xl border border-[#232c39] bg-[#141a24] p-5 shadow-lg shadow-black/20">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#8b97a7]">Registered Devices</span>
            <div className="rounded-xl bg-[#ffb454]/15 p-2 text-[#ffb454]">
              <Laptop className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-3 text-2xl font-bold text-white">{stats.total_devices}</div>
          <div className="mt-1 text-[11px] text-[#8b97a7]">Unique HWID fingerprints</div>
        </div>
      </div>

      {/* Two Column Layout: Recent Links & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Links */}
        <div className="rounded-2xl border border-[#232c39] bg-[#141a24] p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Link2 className="h-4 w-4 text-[#00c2ff]" />
              <h3 className="text-sm font-bold text-white">Recent Automation Links</h3>
            </div>
            <Link
              href="/admin/link-logs"
              className="text-xs font-medium text-[#6d5efc] hover:underline flex items-center gap-1"
            >
              View All <ExternalLink className="h-3 w-3" />
            </Link>
          </div>

          <div className="space-y-3">
            {(data?.recent_links || []).length === 0 ? (
              <p className="text-xs text-[#5f6b7a] py-6 text-center">No links logged yet.</p>
            ) : (
              (data?.recent_links || []).map((item: any) => (
                <div
                  key={item.id}
                  className="p-3 rounded-xl bg-[#10151f] border border-[#232c39] flex flex-col gap-1.5"
                >
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-white">{item.username || 'Unknown'}</span>
                    <span className="text-[#5f6b7a] flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {new Date(item.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-xs text-[#8b97a7] font-mono truncate">{item.url}</p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="rounded-2xl border border-[#232c39] bg-[#141a24] p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-[#2ee6a6]" />
              <h3 className="text-sm font-bold text-white">Audit & Security Feed</h3>
            </div>
            <Link
              href="/admin/logs"
              className="text-xs font-medium text-[#6d5efc] hover:underline flex items-center gap-1"
            >
              View All <ExternalLink className="h-3 w-3" />
            </Link>
          </div>

          <div className="space-y-3">
            {(data?.recent_activities || []).length === 0 ? (
              <p className="text-xs text-[#5f6b7a] py-6 text-center">No recent activity.</p>
            ) : (
              (data?.recent_activities || []).map((item: any) => (
                <div
                  key={item.id}
                  className="p-3 rounded-xl bg-[#10151f] border border-[#232c39] flex items-center justify-between"
                >
                  <div>
                    <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#232c39] text-[#8b97a7] uppercase mr-2">
                      {item.action}
                    </span>
                    <span className="text-xs text-white font-medium">{item.username || 'System'}</span>
                  </div>
                  <span className="text-[11px] text-[#5f6b7a]">
                    {new Date(item.created_at).toLocaleTimeString()}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
