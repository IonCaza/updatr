import { Sidebar } from "@/components/sidebar";
import { HealthBanner } from "@/components/health-banner";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <HealthBanner />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
