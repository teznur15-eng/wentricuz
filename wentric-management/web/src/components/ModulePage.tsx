"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Ban, Check, CheckCircle2, Download, FileDown, Plus, RefreshCw, Search,
  Square, Upload, XCircle, Play,
} from "lucide-react";
import { api, downloadReport } from "@/lib/api";

type Row = Record<string, unknown>;
type Field = { name: string; label: string; type?: string; required?: boolean };
type Column = { key: string; label: string };
type Action = "tasks" | "finance" | "employees" | "cards" | "suggestions" | "attendance" | "files" | "applications" | "leaves" | "notifications" | "invites";
type Config = {
  endpoint: string;
  title: string;
  description: string;
  columns: Column[];
  canCreate?: boolean;
  formFields?: Field[];
  createEndpoint?: string;
  reportPath?: string;
  reportName?: string;
  action?: Action;
};

function showError(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export default function ModulePage({ config }: { config: Config }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [qrImage, setQrImage] = useState("");
  const [currentRoles, setCurrentRoles] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api<Row[]>(config.endpoint);
      setRows(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(showError(err, "Ma’lumotlarni yuklab bo‘lmadi"));
    } finally {
      setLoading(false);
    }
  }, [config.endpoint]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { api<{ roles: string[] }>("/auth/me").then((me) => setCurrentRoles(me.roles ?? [])).catch(() => setCurrentRoles([])); }, []);

  const filtered = useMemo(
    () => rows.filter((row) => JSON.stringify(row).toLowerCase().includes(query.toLowerCase())),
    [rows, query],
  );
  const createRoles: Record<string, string[]> = {
    "/employees": ["SUPER_ADMIN", "CEO", "COO"], "/projects": ["SUPER_ADMIN", "CEO", "CTO", "COO"],
    "/tasks": ["SUPER_ADMIN", "CEO", "CTO", "COO", "PROJECT_LEADER"], "/cards": ["SUPER_ADMIN", "CEO"],
    "/announcements": ["SUPER_ADMIN", "CEO", "CTO", "COO"], "/meetings": ["SUPER_ADMIN", "CEO", "CTO", "COO", "PROJECT_LEADER"],
    "/knowledge": ["SUPER_ADMIN", "CEO", "CTO", "COO", "PROJECT_LEADER"], "/finance": ["SUPER_ADMIN", "CEO"],
    "/ratings": ["SUPER_ADMIN", "CEO", "CTO", "COO", "PROJECT_LEADER"], "/invites": ["SUPER_ADMIN", "CEO", "COO"],
    "/schedules": ["SUPER_ADMIN", "CEO", "COO"],
  };
  const createEndpoint = config.createEndpoint ?? "";
  const canCreate = Boolean(config.canCreate) && (!(createEndpoint in createRoles) || currentRoles.some((role) => createRoles[createEndpoint].includes(role)));

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!config.createEndpoint) return;
    const sensitiveCreate = ["employees", "cards", "invites", "finance"].includes(config.action ?? "");
    if (sensitiveCreate && !window.confirm(config.action === "cards" ? "Wentric Card chiqarish so‘rovini yaratmoqchimisiz? Karta alohida tasdiqlashdan o‘tadi." : "Ushbu yozuvni yaratishni tasdiqlaysizmi?")) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const body: Record<string, unknown> = {};
    for (const field of config.formFields ?? []) {
      const value = String(data.get(field.name) ?? "").trim();
      if (!value) continue;
      if (field.name === "role_codes") {
        body[field.name] = value.split(",").map((role) => role.trim().toUpperCase()).filter(Boolean);
      } else if (field.type === "number") {
        body[field.name] = Number(value);
      } else {
        body[field.name] = value;
      }
    }
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await api<Record<string, unknown>>(config.createEndpoint, {
        method: "POST", body: JSON.stringify(body), ...(sensitiveCreate ? { headers: { "X-Confirm-Action": "confirmed" } } : {}),
      });
      setShowForm(false); form.reset();
      if (result.qr_token_once) {
        setQrImage(typeof result.qr_png_data_url === "string" ? result.qr_png_data_url : "");
        setNotice(`Karta yaratildi. QR token bir marta ko‘rsatiladi: ${String(result.qr_token_once)}. Uni xavfsiz joyda saqlang.`);
      } else if (result.invite_code_once) {
        const link = result.invite_link ? ` · Havola: ${String(result.invite_link)}` : "";
        setNotice(`Taklif kodi bir marta ko‘rsatiladi: ${String(result.invite_code_once)}${link}. Xodimga xavfsiz yuboring.`);
      } else {
        setNotice("Yozuv muvaffaqiyatli saqlandi.");
      }
      await load();
    } catch (err) {
      setError(showError(err, "Saqlashda xatolik"));
    } finally { setSaving(false); }
  }

  async function action(row: Row, operation: string) {
    const confirmedAction = ["finance", "employees", "cards", "applications", "leaves", "invites"].includes(config.action ?? "");
    if (confirmedAction && !window.confirm("Bu amalni bajarishga ishonchingiz komilmi? Amal audit jurnaliga yozilishi mumkin.")) return;
    setError(""); setNotice("");
    const confirmHeaders = confirmedAction ? { headers: { "X-Confirm-Action": "confirmed" } } : {};
    try {
      if (config.action === "tasks") {
        const status = operation === "complete" || operation === "approve" ? "done" : operation;
        await api(`/tasks/${row.id}/status`, { method: "PATCH", body: JSON.stringify({ status, progress: status === "done" ? 100 : row.progress }) });
      } else if (config.action === "finance") {
        await api(`/finance/${row.id}/decision`, { method: "POST", body: JSON.stringify({ decision: operation, comment: "Web-panel orqali ko‘rib chiqildi" }), ...confirmHeaders });
      } else if (config.action === "employees") {
        await api(`/employees/${row.id}/status`, { method: "PATCH", body: JSON.stringify({ status: operation }), ...confirmHeaders });
      } else if (config.action === "cards") {
        if (operation === "block") await api(`/cards/${row.id}/block`, { method: "POST", ...confirmHeaders });
        else await api(`/cards/${row.id}/decision`, { method: "POST", body: JSON.stringify({ decision: operation }), ...confirmHeaders });
      } else if (config.action === "suggestions") {
        await api(`/suggestions/${row.id}/status`, { method: "PATCH", body: JSON.stringify({ status: operation }), ...confirmHeaders });
      } else if (config.action === "applications") {
        await api(`/applications/${row.id}/decision`, { method: "POST", body: JSON.stringify({ decision: operation, role_codes: ["EMPLOYEE"] }), ...confirmHeaders });
      } else if (config.action === "leaves") {
        await api(`/leave-requests/${row.id}/decision`, { method: "POST", body: JSON.stringify({ decision: operation }), ...confirmHeaders });
      } else if (config.action === "notifications") {
        await api(`/notifications/${row.id}/read`, { method: "POST" });
      } else if (config.action === "invites") {
        await api(`/invites/${row.id}/revoke`, { method: "POST", ...confirmHeaders });
      }
      setNotice("Amal bajarildi.");
      await load();
    } catch (err) { setError(showError(err, "Amal bajarilmadi")); }
  }

  async function editRoles(row: Row) {
    if (!currentRoles.includes("SUPER_ADMIN")) return;
    const current = Array.isArray(row.roles) ? row.roles.join(", ") : "EMPLOYEE";
    const value = window.prompt("Yangi rollarni vergul bilan kiriting: SUPER_ADMIN, CEO, CTO, COO, PROJECT_LEADER, EMPLOYEE", current);
    if (value === null) return;
    const roles = value.split(",").map((part) => part.trim().toUpperCase()).filter(Boolean);
    if (!roles.length || !window.confirm(`Xodim #${row.id} rollari ${roles.join(", ")} qilib o‘zgartirilsinmi?`)) return;
    try {
      await api(`/employees/${row.id}/roles`, { method: "PATCH", body: JSON.stringify({ role_codes: roles }), headers: { "X-Confirm-Action": "confirmed" } });
      setNotice("Xodim rollari yangilandi."); await load();
    } catch (err) { setError(showError(err, "Rollarni o‘zgartirib bo‘lmadi")); }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("file") as HTMLInputElement | null;
    if (!input?.files?.[0]) return;
    const data = new FormData(); data.append("file", input.files[0]);
    setUploading(true); setError(""); setNotice("");
    try {
      await api("/files", { method: "POST", body: data });
      setNotice("Fayl yuklandi."); form.reset(); await load();
    } catch (err) { setError(showError(err, "Fayl yuklanmadi")); }
    finally { setUploading(false); }
  }

  async function attendance(mode: "start" | "finish", workMode: "office" | "remote" = "remote") {
    try {
      await api(mode === "start" ? "/attendance/start" : "/attendance/finish", {
        method: "POST", ...(mode === "start" ? { body: JSON.stringify({ mode: workMode }) } : {}),
      });
      setNotice(mode === "start" ? "Ish vaqti boshlandi." : "Ish vaqti tugatildi."); await load();
    } catch (err) { setError(showError(err, "Davomat amalida xatolik")); }
  }

  function renderCell(row: Row, column: Column) {
    const value = row[column.key];
    if (value == null || value === "") return "—";
    if (Array.isArray(value)) return value.join(", ");
    if (typeof value === "object") {
      const date = new Date(String(value));
      return Number.isNaN(date.getTime()) ? JSON.stringify(value) : date.toLocaleString("uz-UZ");
    }
    if (["created_at", "updated_at", "deadline", "started_at", "finished_at", "read_at", "work_date", "starts_at", "ends_at", "start_at", "end_at"].includes(column.key)) {
      const date = new Date(String(value));
      if (!Number.isNaN(date.getTime())) return date.toLocaleString("uz-UZ");
    }
    return String(value);
  }

  function rowActions(row: Row) {
    if (config.action === "tasks") {
      if (row.status === "review") return <button className="secondary-button" onClick={() => action(row, "approve")}><Check size={13}/> Tasdiqlash</button>;
      if (row.status !== "done") return <button className="secondary-button" onClick={() => action(row, "complete")}><CheckCircle2 size={13}/> Bajarildi</button>;
    }
    if (config.action === "finance" && row.status === "pending") return <div className="action-group"><button title="Tasdiqlash" className="secondary-button" onClick={() => action(row, "approve")}><Check size={13}/></button><button title="Rad etish" className="secondary-button" onClick={() => action(row, "reject")}><XCircle size={13}/></button></div>;
    if (config.action === "employees" && row.status === "active") return <div className="action-group"><button className="secondary-button" onClick={() => action(row, "blocked")}><Ban size={13}/> Bloklash</button><button className="secondary-button" onClick={() => action(row, "terminated")}>Ishdan ketdi</button>{currentRoles.includes("SUPER_ADMIN") && <button className="secondary-button" onClick={() => void editRoles(row)}>Rollar</button>}</div>;
    if (config.action === "cards") {
      if (row.status === "pending") return <div className="action-group"><button className="secondary-button" onClick={() => action(row, "approve")}><Check size={13}/></button><button className="secondary-button" onClick={() => action(row, "reject")}><XCircle size={13}/></button></div>;
      if (row.status === "active") return <button className="secondary-button" onClick={() => action(row, "block")}><Ban size={13}/> Bloklash</button>;
    }
    if (config.action === "suggestions" && row.status !== "resolved" && row.status !== "rejected") return <button className="secondary-button" onClick={() => action(row, "resolved")}>Yakunlash</button>;
    if (config.action === "applications" && row.status === "pending") return <div className="action-group"><button className="secondary-button" onClick={() => action(row, "approve")}><Check size={13}/> Tasdiqlash</button><button className="secondary-button" onClick={() => action(row, "reject")}><XCircle size={13}/> Rad etish</button></div>;
    if (config.action === "leaves" && row.status === "pending") return <div className="action-group"><button className="secondary-button" onClick={() => action(row, "approve")}><Check size={13}/> Tasdiqlash</button><button className="secondary-button" onClick={() => action(row, "reject")}><XCircle size={13}/></button></div>;
    if (config.action === "notifications" && !row.read_at) return <button className="secondary-button" onClick={() => action(row, "read")}>O‘qildi</button>;
    if (config.action === "invites" && row.status === "active") return <button className="secondary-button" onClick={() => action(row, "revoke")}><Ban size={13}/> Bekor qilish</button>;
    if (config.action === "files") return <button className="secondary-button" onClick={() => downloadReport(`/files/${row.id}/download`, String(row.original_name || "file")).catch((err) => setError(showError(err, "Yuklab bo‘lmadi")))}><Download size={13}/> Yuklash</button>;
    return null;
  }

  return <>
    <div className="page-head"><div><div className="eyebrow">WENTRIC / MODUL</div><h1 className="page-heading">{config.title}</h1><p className="page-description">{config.description}</p></div><div className="action-group"><button className="secondary-button" onClick={() => void load()}><RefreshCw size={14}/> Yangilash</button>{config.reportPath && <button className="secondary-button" onClick={() => downloadReport(config.reportPath!, config.reportName || "wentric_report.xlsx").catch((err) => setError(showError(err, "Hisobotni yuklab bo‘lmadi")))}><FileDown size={14}/> Eksport</button>}{canCreate && <button className="primary-button" onClick={() => setShowForm((value) => !value)}><Plus size={15}/> Yangi qo‘shish</button>}</div></div>
    {error && <div className="error-message">{error}</div>}{notice && <div className="notice notice-break" style={{ marginBottom: 16 }}>{notice}{qrImage && <div style={{ marginTop: 12 }}><img src={qrImage} alt="Wentric Card QR kodi" width={180} height={180}/></div>}</div>}
    {config.action === "attendance" && <section className="panel"><div className="panel-heading"><div><div className="panel-title">Davomat harakatlari</div><div className="panel-subtitle">Ofis yoki masofaviy ishni belgilang.</div></div></div><div className="action-group"><button className="primary-button" onClick={() => void attendance("start", "office")}><Play size={14}/> Ofisda ishni boshlash</button><button className="primary-button" onClick={() => void attendance("start", "remote")}><Play size={14}/> Masofadan boshlash</button><button className="secondary-button" onClick={() => void attendance("finish")}><Square size={14}/> Ishni tugatish</button></div></section>}
    {config.action === "files" && <section className="panel"><div className="panel-title">Fayl yuklash</div><form onSubmit={upload} className="upload-form"><input name="file" type="file" required/><button className="primary-button" disabled={uploading}><Upload size={14}/>{uploading ? "Yuklanmoqda…" : "Faylni yuklash"}</button></form><div className="footer-note">20 MB gacha. Ruxsat etilgan turlar: PDF, JPG/PNG/WebP, TXT, DOCX, XLSX, CSV, ZIP.</div></section>}
    {showForm && config.formFields && <section className="panel"><div className="panel-heading"><div className="panel-title">Yangi yozuv</div></div><form onSubmit={create} className="form-grid">{config.formFields.map((field) => <div className="field" key={field.name}><label htmlFor={field.name}>{field.label}</label>{field.type === "textarea" ? <textarea id={field.name} name={field.name} rows={3} required={field.required}/> : <input id={field.name} name={field.name} type={field.type || "text"} required={field.required} min={field.type === "number" ? 0 : undefined}/>}</div>)}<div className="field full action-group"><button type="button" className="secondary-button" onClick={() => setShowForm(false)}>Bekor qilish</button><button className="primary-button" disabled={saving}>{saving ? "Saqlanmoqda…" : "Saqlash"}</button></div></form></section>}
    <section className="panel"><div className="toolbar"><div><div className="panel-title">Ro‘yxat</div><div className="panel-subtitle">{filtered.length} ta yozuv</div></div><div className="search-box"><Search size={15}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Bo‘lim ichidan qidirish…"/></div></div>{loading ? <div className="empty-state">Yuklanmoqda…</div> : filtered.length === 0 ? <div className="empty-state">Ma’lumot topilmadi. Kirish huquqi yoki qidiruvni tekshiring.</div> : <div className="table-wrap"><table><thead><tr>{config.columns.map((column) => <th key={column.key}>{column.label}</th>)}{config.action && <th>Amal</th>}</tr></thead><tbody>{filtered.map((row, index) => <tr key={String(row.id ?? index)}>{config.columns.map((column) => <td key={column.key}>{column.key === "status" ? <span className={`status-pill status-${String(row[column.key])}`}>{renderCell(row, column)}</span> : renderCell(row, column)}</td>)}{config.action && <td>{rowActions(row) || "—"}</td>}</tr>)}</tbody></table></div>}</section>
  </>;
}
