'use client';

import { useState, useEffect } from 'react';
import { Settings, Save, AlertCircle, CheckCircle2, Shield } from 'lucide-react';

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<Record<string, string>>({
    app_name: 'Automation Hub',
    heartbeat_interval: '45',
    session_timeout: '3600',
    offline_grace_seconds: '300',
    single_session: '1',
  });
  const [isSuper, setIsSuper] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: 'error' | 'success'; text: string } | null>(null);

  async function fetchSettings() {
    setLoading(true);
    try {
      const res = await fetch('/api/admin/settings');
      const json = await res.json();
      if (json.ok) {
        setSettings(json.settings || {});
        setIsSuper(json.is_super || false);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchSettings();
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMsg(null);
    try {
      const res = await fetch('/api/admin/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        setMsg({ type: 'error', text: json.message || 'Failed to save settings' });
        return;
      }
      setMsg({ type: 'success', text: 'Settings saved successfully!' });
    } catch (err: any) {
      setMsg({ type: 'error', text: err.message || 'Save failed' });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6 pt-12 md:pt-0 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">System Settings</h2>
        <p className="text-xs text-[#8b97a7] mt-0.5">
          Configure security timeouts, heartbeat cycles and single-session policies
        </p>
      </div>

      {msg && (
        <div
          className={`flex items-center gap-2 rounded-xl p-3 text-xs border ${
            msg.type === 'error'
              ? 'border-[#ff5c7a]/30 bg-[#ff5c7a]/10 text-[#ff5c7a]'
              : 'border-[#2ee6a6]/30 bg-[#2ee6a6]/10 text-[#2ee6a6]'
          }`}
        >
          {msg.type === 'error' ? (
            <AlertCircle className="h-4 w-4 shrink-0" />
          ) : (
            <CheckCircle2 className="h-4 w-4 shrink-0" />
          )}
          <span>{msg.text}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        <div className="rounded-2xl border border-[#232c39] bg-[#141a24] p-6 space-y-5">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Shield className="h-4 w-4 text-[#6d5efc]" />
            Security & Session Rules
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block text-[#8b97a7] mb-1.5 font-medium">Application Name</label>
              <input
                type="text"
                value={settings.app_name || ''}
                onChange={(e) => setSettings({ ...settings, app_name: e.target.value })}
                className="w-full rounded-xl border border-[#232c39] bg-[#10151f] px-3.5 py-2.5 text-white focus:border-[#6d5efc] outline-none"
              />
            </div>

            <div>
              <label className="block text-[#8b97a7] mb-1.5 font-medium">
                Heartbeat Interval (Seconds)
              </label>
              <input
                type="number"
                min="15"
                max="300"
                value={settings.heartbeat_interval || '45'}
                onChange={(e) => setSettings({ ...settings, heartbeat_interval: e.target.value })}
                className="w-full rounded-xl border border-[#232c39] bg-[#10151f] px-3.5 py-2.5 text-white focus:border-[#6d5efc] outline-none"
              />
              <span className="text-[11px] text-[#5f6b7a] mt-1 block">
                How often the desktop app pings the server (default: 45s).
              </span>
            </div>

            <div>
              <label className="block text-[#8b97a7] mb-1.5 font-medium">
                Session Inactivity Timeout (Seconds)
              </label>
              <input
                type="number"
                min="300"
                value={settings.session_timeout || '3600'}
                onChange={(e) => setSettings({ ...settings, session_timeout: e.target.value })}
                className="w-full rounded-xl border border-[#232c39] bg-[#10151f] px-3.5 py-2.5 text-white focus:border-[#6d5efc] outline-none"
              />
              <span className="text-[11px] text-[#5f6b7a] mt-1 block">
                Session automatically expires after this duration of inactivity (default: 3600s).
              </span>
            </div>

            <div>
              <label className="block text-[#8b97a7] mb-1.5 font-medium">Single Session Mode</label>
              <select
                value={settings.single_session || '1'}
                onChange={(e) => setSettings({ ...settings, single_session: e.target.value })}
                className="w-full rounded-xl border border-[#232c39] bg-[#10151f] px-3.5 py-2.5 text-white focus:border-[#6d5efc] outline-none"
              >
                <option value="1">Enabled (One Active Session Per User)</option>
                <option value="0">Disabled (Allow Multi-Device Login)</option>
              </select>
              <span className="text-[11px] text-[#5f6b7a] mt-1 block">
                Blocks concurrent logins on different computers when enabled.
              </span>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving || !isSuper}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#6d5efc] to-[#5846f6] px-6 py-2.5 text-xs font-semibold text-white shadow-lg shadow-[#6d5efc]/25 hover:opacity-95 transition disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            <span>{saving ? 'Saving...' : 'Save Settings'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
