"use client";

import { useEffect, useRef, useState } from "react";
import { Upload, FileText, Trash2, Loader2, AlertTriangle, Download, CheckCircle2 } from "lucide-react";
import { API, devAuthHeaders } from "@/lib/api";

interface CVMeta {
  filename: string;
  size_bytes: number;
  content_type: string;
  uploaded_at: string;
  storage_key: string;
  stored_path: string;
  extracted_text_preview: string;
  extracted_text_length: number;
}

function fmtSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

function fmtDate(iso: string): string {
  if (!iso) return "-";
  try { return new Date(iso).toLocaleString("fr-FR"); } catch { return iso; }
}

export default function CVUpload() {
  const [cv, setCv] = useState<CVMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let abort = false;
    (async () => {
      try {
        const r = await fetch(API.cv.get, { headers: devAuthHeaders("user"), cache: "no-store" });
        if (r.status === 404) { if (!abort) setCv(null); return; }
        if (!r.ok) {
          // Erreur autre que 404 : silencieuse (log seulement)
          if (!abort) console.warn("[CVUpload] GET /cv HTTP", r.status);
          return;
        }
        const data = await r.json();
        console.info("[CVUpload] GET /cv ->", data);
        if (!abort) setCv(data.cv || null);
      } catch (e: any) {
        // Silencieux au mount : on ne veut pas bloquer l UX avec un message
        // technique au premier rendu.
        if (!abort) console.warn("[CVUpload] GET /cv failed:", e?.message);
      } finally {
        if (!abort) setLoading(false);
      }
    })();
    return () => { abort = true; };
  }, []);

  async function uploadFile(file: File) {
    setActionError(null); setSuccess(null);
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setActionError("Le fichier doit etre un PDF (extension .pdf)."); return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setActionError(`Fichier trop volumineux (${fmtSize(file.size)} > 5 MB).`); return;
    }
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await fetch(API.cv.upload, {
        method: "POST",
        headers: { ...devAuthHeaders("user") }, // pas de Content-Type => le navigateur met le boundary
        body: fd,
      });
      if (!r.ok) {
        const txt = await r.text();
        throw new Error(`HTTP ${r.status} - ${txt || "echec upload"}`);
      }
      const data = await r.json();
      setCv(data.cv);
      setSuccess("CV televerse avec succes.");
      setTimeout(() => setSuccess(null), 3000);
    } catch (e: any) {
      setActionError(e?.message || "Erreur lors du televersement");
    } finally {
      setUploading(false);
    }
  }

  async function onDelete() {
    if (!confirm("Supprimer definitivement ton CV ? Cette action'est irreversible.")) return;
    setDeleting(true); setActionError(null);
    try {
      const r = await fetch(API.cv.remove, { method: "DELETE", headers: devAuthHeaders("user") });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setCv(null);
      setSuccess("CV supprime.");
      setTimeout(() => setSuccess(null), 3000);
    } catch (e: any) {
      setActionError(e?.message || "Erreur lors de la suppression");
    } finally {
      setDeleting(false);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault(); setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f) uploadFile(f);
  }

  function onDragOver(e: React.DragEvent) {
    e.preventDefault(); setDrag(true);
  }

  function onDragLeave(e: React.DragEvent) {
    e.preventDefault(); setDrag(false);
  }

  if (loading) {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 className="w-4 h-4 animate-spin" /> Chargement du CV...
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <FileText className="w-5 h-5 text-indigo-500" />
        <h2 className="text-lg font-medium text-slate-900">Mon CV</h2>
        {cv ? <span className="text-xs text-slate-500">{fmtSize(cv.size_bytes)} - uploade le {fmtDate(cv.uploaded_at)}</span> : null}
      </div>

      {actionError ? (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> {actionError}
        </div>
      ) : null}
      {success ? (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
          <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" /> {success}
        </div>
      ) : null}

      {cv ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-start gap-3">
            <div className="shrink-0 w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
              <FileText className="w-5 h-5 text-indigo-600" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-medium text-slate-900 truncate">{cv.filename}</div>
              <div className="text-xs text-slate-500 mt-0.5">
                {fmtSize(cv.size_bytes)} - {cv.content_type}
              </div>
              {cv.extracted_text_length > 0 ? (
                <div className="mt-2 text-xs text-slate-600 italic border-l-2 border-slate-300 pl-2">
                  Extrait : {cv.extracted_text_preview.slice(0, 200)}
                  {cv.extracted_text_length > 200 ? "..." : ""}
                </div>
              ) : (
                <div className="mt-2 text-xs text-slate-400 italic">
                  Extraction de texte indisponible (PDF scanne ou bibliotheque absente). Le CV sera quand meme transmis a l'agent.
                </div>
              )}
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
            <a
              href={API.cv.download}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-slate-200 text-xs font-medium text-slate-700 hover:border-indigo-400 hover:text-indigo-700"
            >
              <Download className="w-3.5 h-3.5" /> Telecharger
            </a>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-slate-200 text-xs font-medium text-slate-700 hover:border-indigo-400 hover:text-indigo-700 disabled:opacity-50"
            >
              {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
              Remplacer
            </button>
            <button
              type="button"
              onClick={onDelete}
              disabled={deleting}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-rose-200 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
            >
              {deleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
              Supprimer
            </button>
          </div>
        </div>
      ) : (
        <div
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          className={"rounded-xl border-2 border-dashed p-8 text-center transition cursor-pointer " +
            (drag ? "border-indigo-400 bg-indigo-50" : "border-slate-300 bg-slate-50 hover:border-indigo-400 hover:bg-indigo-50")}
          onClick={() => fileInputRef.current?.click()}
        >
          {uploading ? (
            <div className="flex flex-col items-center gap-2 text-slate-600">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
              <div className="text-sm">Upload en cours...</div>
            </div>
          ) : (
            <>
              <Upload className="w-10 h-10 mx-auto text-indigo-500 mb-2" />
              <div className="text-sm font-medium text-slate-700">
                Glisse-depose ton CV ici ou clique pour le selectionner
              </div>
              <div className="text-xs text-slate-500 mt-1">
                Format PDF uniquement, taille maximale 5 Mo
              </div>
              <div className="mt-3 text-[11px] text-slate-400">
                Une fois televerse, les boutons Voir, Remplacer et Supprimer apparaitront ici.
              </div>
            </>
          )}
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) uploadFile(f);
          e.target.value = ""; // reset pour pouvoir re-uploader le meme fichier
        }}
      />
    </section>
  );
}
