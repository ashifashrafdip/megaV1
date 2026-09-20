'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  Users,
  Link2,
  Activity,
  Laptop,
  FileText,
  Settings,
  LogOut,
  Menu,
  X,
  ShieldCheck,
} from 'lucide-react';

interface Props {
  admin: {
    id: number;
    username: string;
    role_name: string;
    role_label: string;
  };
}

export default function AdminNav({ admin }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navItems = [
    { href: '/admin', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/admin/users', label: 'User Management', icon: Users },
    { href: '/admin/link-logs', label: 'Link Logs', icon: Link2 },
    { href: '/admin/sessions', label: 'Active Sessions', icon: Activity },
    { href: '/admin/devices', label: 'Devices', icon: Laptop },
    { href: '/admin/logs', label: 'Audit Logs', icon: FileText },
    ...(admin.role_name === 'super_admin'
      ? [{ href: '/admin/settings', label: 'Settings', icon: Settings }]
      : []),
  ];

  async function handleLogout() {
    await fetch('/api/admin/logout', { method: 'POST' });
    router.push('/admin/login');
    router.refresh();
  }

  return (
    <>
      {/* Mobile Bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 flex items-center justify-between bg-[#10151f] border-b border-[#232c39] px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#6d5efc]/20 text-[#6d5efc] font-bold text-sm">
            AH
          </div>
          <span className="font-semibold text-white text-sm">Automation Hub</span>
        </div>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="p-1 text-[#8b97a7] hover:text-white"
        >
          {mobileOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>

      {/* Sidebar Drawer */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-[#10151f] border-r border-[#232c39] flex flex-col transition-transform duration-200 ease-in-out md:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Logo / Header */}
        <div className="p-6 border-b border-[#232c39]">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-[#6d5efc] to-[#00c2ff] text-white font-black text-base shadow-lg shadow-[#6d5efc]/20">
              AH
            </div>
            <div>
              <h1 className="font-bold text-white tracking-tight text-sm">Automation Hub</h1>
              <span className="inline-flex items-center gap-1 rounded-full bg-[#00c2ff]/10 px-2 py-0.5 text-[10px] font-medium text-[#00c2ff]">
                <ShieldCheck className="h-3 w-3" />
                Vercel Edition
              </span>
            </div>
          </div>
        </div>

        {/* User Badge */}
        <div className="mx-4 my-4 p-3 rounded-xl bg-[#141a24] border border-[#232c39] flex items-center justify-between">
          <div className="truncate">
            <p className="text-xs font-semibold text-white truncate">{admin.username}</p>
            <p className="text-[11px] text-[#8b97a7] capitalize">{admin.role_label}</p>
          </div>
          <span className="h-2 w-2 rounded-full bg-[#2ee6a6] shadow-[0_0_8px_#2ee6a6]" />
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-4 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
                  isActive
                    ? 'bg-[#6d5efc] text-white shadow-md shadow-[#6d5efc]/25'
                    : 'text-[#8b97a7] hover:bg-[#141a24] hover:text-white'
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Logout Button */}
        <div className="p-4 border-t border-[#232c39]">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-medium text-[#ff5c7a] hover:bg-[#ff5c7a]/10 transition"
          >
            <LogOut className="h-4 w-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Backdrop for mobile */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-40 bg-black/60 md:hidden backdrop-blur-sm"
        />
      )}
    </>
  );
}
