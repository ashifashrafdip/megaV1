'use client';

import { useState, useEffect } from 'react';
import {
  Users,
  UserPlus,
  Search,
  KeyRound,
  ShieldBan,
  ShieldCheck,
  Calendar,
  Trash2,
  AlertCircle,
  CheckCircle2,
  X,
  Loader2,
} from 'lucide-react';

export default function AdminUsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [roles, setRoles] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [modalType, setModalType] = useState<string | null>(null);
  const [selectedUser, setSelectedUser] = useState<any | null>(null);

  // Form states
  const [formData, setFormData] = useState<any>({});
  const [formMsg, setFormMsg] = useState<{ type: 'error' | 'success'; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function fetchUsers() {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/users?q=${encodeURIComponent(search)}`);
      const json = await res.json();
      if (json.ok) {
        setUsers(json.users || []);
        setRoles(json.roles || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchUsers();
  }, [search]);

  function openModal(type: string, user: any = null) {
    setModalType(type);
    setSelectedUser(user);
    setFormMsg(null);
    if (type === 'create') {
      setFormData({ username: '', password: '', role_id: 3, expires_at: '' });
    } else if (type === 'reset_password') {
      setFormData({ new_password: '' });
    } else if (type === 'update_license') {
      const expiresFormatted = user.expires_at ? user.expires_at.slice(0, 10) : '';
      setFormData({ license_status: user.license_status || 'active', expires_at: expiresFormatted });
    }
  }

  function closeModal() {
    setModalType(null);
    setSelectedUser(null);
    setFormMsg(null);
  }

  async function handleAction(action: string, payload: any = {}) {
    setSubmitting(true);
    setFormMsg(null);
    try {
      const res = await fetch('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          user_id: selectedUser?.id,
          ...payload,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        setFormMsg({ type: 'error', text: json.message || 'Operation failed' });
        setSubmitting(false);
        return;
      }
      setFormMsg({ type: 'success', text: json.message || 'Success' });
      fetchUsers();
      setTimeout(closeModal, 1000);
    } catch (err: any) {
      setFormMsg({ type: 'error', text: err.message || 'Request failed' });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6 pt-12 md:pt-0">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">User Management</h2>
          <p className="text-xs text-[#8b97a7] mt-0.5">
            Manage authorized operators, roles, passwords and licensing
          </p>
        </div>
        <button
          onClick={() => openModal('create')}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#6d5efc] to-[#5846f6] px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-[#6d5efc]/25 hover:opacity-95 transition"
        >
          <UserPlus className="h-4 w-4" />
          <span>Add User</span>
        </button>
      </div>

      {/* Search Bar */}
      <div className="relative max-w-md">
        <Search className="absolute left-3.5 top-3 h-4 w-4 text-[#5f6b7a]" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by username or email..."
          className="w-full rounded-xl border border-[#232c39] bg-[#141a24] pl-10 pr-4 py-2.5 text-xs text-white placeholder-[#5f6b7a] focus:border-[#6d5efc] focus:outline-none transition"
        />
      </div>

      {/* Users Table */}
      <div className="rounded-2xl border border-[#232c39] bg-[#141a24] overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-[#232c39] bg-[#10151f] text-[#8b97a7] font-semibold">
              <tr>
                <th className="px-5 py-3.5">User</th>
                <th className="px-5 py-3.5">Role</th>
                <th className="px-5 py-3.5">Status</th>
                <th className="px-5 py-3.5">License Expiry</th>
                <th className="px-5 py-3.5">Last Login</th>
                <th className="px-5 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#232c39]/50">
              {loading ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-[#8b97a7]">
                    Loading users...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-[#5f6b7a]">
                    No users found matching query.
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id} className="hover:bg-[#19212d]/50 transition">
                    <td className="px-5 py-4">
                      <div className="font-semibold text-white">{u.username}</div>
                      <div className="text-[11px] text-[#5f6b7a]">{u.email || 'No email'}</div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="inline-block px-2.5 py-1 rounded-full text-[10px] font-semibold bg-[#232c39] text-[#e6edf3]">
                        {u.role_label || u.role_name}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold ${
                          u.status === 'active'
                            ? 'bg-[#2ee6a6]/10 text-[#2ee6a6]'
                            : u.status === 'banned'
                            ? 'bg-[#ff5c7a]/10 text-[#ff5c7a]'
                            : 'bg-[#ffb454]/10 text-[#ffb454]'
                        }`}
                      >
                        <span
                          className={`h-1.5 w-1.5 rounded-full ${
                            u.status === 'active'
                              ? 'bg-[#2ee6a6]'
                              : u.status === 'banned'
                              ? 'bg-[#ff5c7a]'
                              : 'bg-[#ffb454]'
                          }`}
                        />
                        <span className="capitalize">{u.status}</span>
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      {u.expires_at ? (
                        <div>
                          <span className="text-white">{new Date(u.expires_at).toLocaleDateString()}</span>
                          <span className="ml-1.5 text-[10px] text-[#8b97a7]">
                            ({u.days_left !== null ? `${u.days_left}d left` : 'Expired'})
                          </span>
                        </div>
                      ) : (
                        <span className="text-[#5f6b7a]">Never (Perpetual)</span>
                      )}
                    </td>
                    <td className="px-5 py-4 text-[#8b97a7]">
                      {u.last_login_at
                        ? new Date(u.last_login_at).toLocaleString()
                        : 'Never logged in'}
                    </td>
                    <td className="px-5 py-4 text-right space-x-1">
                      <button
                        title="Reset Password"
                        onClick={() => openModal('reset_password', u)}
                        className="p-1.5 rounded-lg border border-[#232c39] bg-[#10151f] text-[#8b97a7] hover:text-white hover:border-[#3b4657] transition"
                      >
                        <KeyRound className="h-3.5 w-3.5" />
                      </button>
                      <button
                        title="Update License"
                        onClick={() => openModal('update_license', u)}
                        className="p-1.5 rounded-lg border border-[#232c39] bg-[#10151f] text-[#8b97a7] hover:text-white hover:border-[#3b4657] transition"
                      >
                        <Calendar className="h-3.5 w-3.5" />
                      </button>
                      {u.status === 'banned' ? (
                        <button
                          title="Unban User"
                          onClick={() => {
                            setSelectedUser(u);
                            handleAction('unban');
                          }}
                          className="p-1.5 rounded-lg border border-[#2ee6a6]/30 bg-[#2ee6a6]/10 text-[#2ee6a6] hover:bg-[#2ee6a6]/20 transition"
                        >
                          <ShieldCheck className="h-3.5 w-3.5" />
                        </button>
                      ) : (
                        <button
                          title="Ban User"
                          onClick={() => {
                            setSelectedUser(u);
                            handleAction('ban');
                          }}
                          className="p-1.5 rounded-lg border border-[#ff5c7a]/30 bg-[#ff5c7a]/10 text-[#ff5c7a] hover:bg-[#ff5c7a]/20 transition"
                        >
                          <ShieldBan className="h-3.5 w-3.5" />
                        </button>
                      )}
                      <button
                        title="Delete User"
                        onClick={() => {
                          if (confirm(`Delete user "${u.username}"?`)) {
                            setSelectedUser(u);
                            handleAction('delete');
                          }
                        }}
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

      {/* Modal Dialog */}
      {modalType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-[#232c39] bg-[#141a24] p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-bold text-white capitalize">
                {modalType.replace('_', ' ')}
                {selectedUser ? ` - ${selectedUser.username}` : ''}
              </h3>
              <button onClick={closeModal} className="text-[#8b97a7] hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            {formMsg && (
              <div
                className={`mb-4 flex items-center gap-2 rounded-xl p-3 text-xs border ${
                  formMsg.type === 'error'
                    ? 'border-[#ff5c7a]/30 bg-[#ff5c7a]/10 text-[#ff5c7a]'
                    : 'border-[#2ee6a6]/30 bg-[#2ee6a6]/10 text-[#2ee6a6]'
                }`}
              >
                {formMsg.type === 'error' ? (
                  <AlertCircle className="h-4 w-4 shrink-0" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                )}
                <span>{formMsg.text}</span>
              </div>
            )}

            {modalType === 'create' && (
              <div className="space-y-4 text-xs">
                <div>
                  <label className="block text-[#8b97a7] mb-1">Username</label>
                  <input
                    type="text"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    className="w-full rounded-xl border border-[#232c39] bg-[#10151f] px-3.5 py-2 text-white focus:border-[#6d5efc] outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[#8b97a7] mb-1">Password (min 8 chars)</label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="w-full rounded-xl border border-[#232c39] bg-[#10151f] px-3.5 py-2 text-white focus:border-[#6d5efc] outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[#8b97a7] mb-1">Role</label>
                  <select
                    value={formData.role_id}
                    onChange={(e) => setFormData({ ...formData, role_id: parseInt(e.target.value, 10) })}
                    className="w-full rounded-xl border border-[#232c39] bg-[#10151f] px-3.5 py-2 text-white focus:border-[#6d5efc] outline-none"
                  >
                    {roles.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[#8b97a7] mb-1">License Expiry Date (Optional)</label>
                  <input
                    type="date"
                    value={formData.expires_at}
                    onChange={(e) => setFormData({ ...formData, expires_at: e.target.value })}
                    className="w-full rounded-xl border border-[#232c39] bg-[#10151f] px-3.5 py-2 text-white focus:border-[#6d5efc] outline-none"
                  />
                </div>
                <button
                  disabled={submitting}
                  onClick={() => handleAction('create', formData)}
                  className="w-full rounded-xl bg-gradient-to-r from-[#6d5efc] to-[#5846f6] py-2.5 text-xs font-semibold text-white mt-2 disabled:opacity-50"
                >
                  {submitting ? 'Creating...' : 'Create User'}
                </button>
              </div>
            )}

            {modalType === 'reset_password' && (
              <div className="space-y-4 text-xs">
                <div>
                  <label className="block text-[#8b97a7] mb-1">New Password (min 8 chars)</label>
                  <input
                    type="password"
                    value={formData.new_password}
                    onChange={(e) => setFormData({ ...formData, new_password: e.target.value })}
                    className="w-full rounded-xl border border-[#232c39] bg-[#10151f] px-3.5 py-2 text-white focus:border-[#6d5efc] outline-none"
                  />
                </div>
                <button
                  disabled={submitting}
                  onClick={() => handleAction('reset_password', { new_password: formData.new_password })}
                  className="w-full rounded-xl bg-gradient-to-r from-[#6d5efc] to-[#5846f6] py-2.5 text-xs font-semibold text-white mt-2 disabled:opacity-50"
                >
                  {submitting ? 'Updating...' : 'Set Password'}
                </button>
              </div>
            )}

            {modalType === 'update_license' && (
              <div className="space-y-4 text-xs">
                <div>
                  <label className="block text-[#8b97a7] mb-1">License Status</label>
                  <select
                    value={formData.license_status}
                    onChange={(e) => setFormData({ ...formData, license_status: e.target.value })}
                    className="w-full rounded-xl border border-[#232c39] bg-[#10151f] px-3.5 py-2 text-white focus:border-[#6d5efc] outline-none"
                  >
                    <option value="active">Active</option>
                    <option value="trial">Trial</option>
                    <option value="inactive">Inactive</option>
                    <option value="revoked">Revoked</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[#8b97a7] mb-1">Expiry Date</label>
                  <input
                    type="date"
                    value={formData.expires_at}
                    onChange={(e) => setFormData({ ...formData, expires_at: e.target.value })}
                    className="w-full rounded-xl border border-[#232c39] bg-[#10151f] px-3.5 py-2 text-white focus:border-[#6d5efc] outline-none"
                  />
                </div>
                <button
                  disabled={submitting}
                  onClick={() =>
                    handleAction('update_license', {
                      license_status: formData.license_status,
                      expires_at: formData.expires_at,
                    })
                  }
                  className="w-full rounded-xl bg-gradient-to-r from-[#6d5efc] to-[#5846f6] py-2.5 text-xs font-semibold text-white mt-2 disabled:opacity-50"
                >
                  {submitting ? 'Saving...' : 'Save License'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
