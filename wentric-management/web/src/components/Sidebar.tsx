"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import {
  Home, Users, FolderKanban, CheckSquare, Clock3, WalletCards, Megaphone,
  CalendarDays, BookOpen, Lightbulb, FileText, Bell, BadgeDollarSign,
  ClipboardList, ShieldCheck, Star, Ticket,
} from "lucide-react";
import { api } from "@/lib/api";

const groups = [
  { name: "UMUMIY", links: [["Boshqaruv paneli", "/dashboard", Home], ["Jamoa", "/dashboard/employees", Users], ["Arizalar", "/dashboard/applications", Users], ["Taklif kodlari", "/dashboard/invites", Ticket], ["Xodimlar bahosi", "/dashboard/ratings", Star], ["Loyihalar", "/dashboard/projects", FolderKanban], ["Vazifalar", "/dashboard/tasks", CheckSquare]] },
  { name: "ISH JARAYONI", links: [["Davomat", "/dashboard/attendance", Clock3], ["Ish jadvali", "/dashboard/schedules", Clock3], ["Ruxsat so‘rovlari", "/dashboard/leave-requests", Clock3], ["Wentric Card", "/dashboard/cards", WalletCards], ["E’lonlar", "/dashboard/announcements", Megaphone], ["Uchrashuvlar", "/dashboard/meetings", CalendarDays]] },
  { name: "BILIM VA ALOQA", links: [["Bilimlar bazasi", "/dashboard/knowledge", BookOpen], ["Taklif va muammolar", "/dashboard/suggestions", Lightbulb], ["Fayllar", "/dashboard/files", FileText], ["Bildirishnomalar", "/dashboard/notifications", Bell]] },
  { name: "BOSHQARUV", links: [["Moliya", "/dashboard/finance", BadgeDollarSign], ["Hisobotlar", "/dashboard/reports", ClipboardList], ["Xavfsizlik jurnali", "/dashboard/security", ShieldCheck]] },
] as const;

function canSee(href: string, roles: string[]) {
  const has = (...allowed: string[]) => roles.some((role) => allowed.includes(role));
  if (href === "/dashboard/finance") return has("SUPER_ADMIN", "CEO");
  if (href === "/dashboard/security") return has("SUPER_ADMIN");
  if (["/dashboard/applications", "/dashboard/invites"].includes(href)) return has("SUPER_ADMIN", "CEO", "COO");
  if (href === "/dashboard/ratings") return has("SUPER_ADMIN", "CEO", "CTO", "COO", "PROJECT_LEADER");
  if (href === "/dashboard/employees") return has("SUPER_ADMIN", "CEO", "CTO", "COO", "PROJECT_LEADER");
  if (href === "/dashboard/reports") return has("SUPER_ADMIN", "CEO", "CTO", "COO", "PROJECT_LEADER");
  return true;
}

export default function Sidebar() {
  const path = usePathname();
  const [roles, setRoles] = useState<string[]>([]);
  useEffect(() => { api<{ roles: string[] }>("/auth/me").then((me) => setRoles(me.roles ?? [])).catch(() => setRoles([])); }, []);
  const visibleGroups = useMemo(() => groups.map((group) => ({ ...group, links: group.links.filter(([, href]) => canSee(href, roles)) })).filter((group) => group.links.length > 0), [roles]);

  return <aside className="sidebar">
    <Link href="/dashboard" className="brand"><div className="brand-mark">W</div><div><div className="brand-name">wentric</div><div className="brand-sub">MANAGEMENT OS</div></div></Link>
    {visibleGroups.map((group) => <div key={group.name}><div className="nav-label">{group.name}</div>{group.links.map(([label, href, Icon]) => <Link key={href} href={href} className={`nav-item ${path === href ? "active" : ""}`}><Icon size={16}/><span>{label}</span></Link>)}</div>)}
    <div className="sidebar-bottom">Wentric IT Group<br/>Management Platform · v0.1</div>
  </aside>;
}
