import { redirect } from 'next/navigation';
import { getAdminSession } from '@/lib/admin-auth';
import AdminNav from '@/components/AdminNav';

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const admin = await getAdminSession();
  if (!admin) {
    redirect('/admin/login');
  }

  return (
    <div className="flex min-h-screen bg-[#0b0e14]">
      {/* Sidebar Navigation */}
      <AdminNav admin={admin} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 md:pl-64">
        <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
