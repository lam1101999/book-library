import { useCallback, useEffect, useRef, useState } from "react";
import type React from "react";
import { Link, useParams } from "react-router-dom";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import {
  Chapter, createChapter, deleteChapter, getChapters, getProgress, pdfUrl,
  saveOutlineToPdf, setProgress, summarizeChapter,
} from "../api";

// cMaps fix CID-encoded text (Vietnamese/CJK garbage symbols) and standard
// fonts cover PDFs that rely on non-embedded base fonts
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

const CMAP_URL = "https://unpkg.com/pdfjs-dist@4.4.168/cmaps/";
const STD_FONTS_URL = "https://unpkg.com/pdfjs-dist@4.4.168/standard_fonts/";

const editInputStyle: React.CSSProperties = {
  fontSize: 12, padding: "4px 6px", width: "100%", boxSizing: "border-box",
};

const OPTIONS = {
  cMapUrl: CMAP_URL,
  cMapPacked: true,
  standardFontDataUrl: STD_FONTS_URL,
};

export default function ReaderPage() {
  const { id } = useParams();
  const bookId = Number(id);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [page, setPage] = useState(1);
  const [scale, setScale] = useState(1.2);
  const [error, setError] = useState("");
  const [summarizing, setSummarizing] = useState<Set<number>>(new Set());
  const [editing, setEditing] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editPage, setEditPage] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [addTitle, setAddTitle] = useState("");
  const [addPage, setAddPage] = useState(String(page));
  const [savingPdf, setSavingPdf] = useState(false);
  const [flash, setFlash] = useState("");
  const paneRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSynced = useRef(0);

  useEffect(() => {
    getChapters(bookId).then(setChapters).catch(() => setError("Failed to load chapters"));
    getProgress(bookId).then((p) => p.last_page > 0 && setPage(p.last_page + 1)).catch(() => {});
  }, [bookId]);

  // track current page while scrolling + sync progress (cross-device)
  useEffect(() => {
    const pane = paneRef.current;
    if (!pane) return;
    const onScroll = () => {
      let current = 1;
      for (const [p, el] of pageRefs.current) {
        if (el.getBoundingClientRect().top < window.innerHeight * 0.4) current = p;
      }
      setPage(current);
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => {
        // only sync when position actually changed since last save
        if (current - 1 !== lastSynced.current) {
          lastSynced.current = current - 1;
          setProgress(bookId, current - 1).catch(() => {});
        }
      }, 800);
    };
    pane.addEventListener("scroll", onScroll);
    return () => pane.removeEventListener("scroll", onScroll);
  }, [bookId]);

  const goToPage = useCallback((p: number) => {
    const el = pageRefs.current.get(p);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const openChapter = (ch: Chapter) => {
    setActive(ch.id);
    goToPage(ch.start_page + 1);
  };

  const startEdit = (ch: Chapter) => {
    setEditing(ch.id);
    setEditTitle(ch.title);
    setEditPage(String(ch.start_page + 1));
  };

  const saveEdit = async (ch: Chapter) => {
    // edit = delete + recreate (keeps API surface small)
    try {
      await deleteChapter(bookId, ch.id);
      const created = await createChapter(bookId, {
        title: editTitle.trim() || ch.title,
        start_page: Math.max(0, Number(editPage) - 1 || 0),
        end_page: ch.end_page,
      });
      const fresh = await getChapters(bookId);
      setChapters(fresh);
      setActive(created.id);
    } catch (e) {
      setError(String(e));
    }
    setEditing(null);
  };

  const addChapter = async () => {
    try {
      const created = await createChapter(bookId, {
        title: addTitle.trim() || "Untitled",
        start_page: Math.max(0, Number(addPage) - 1 || 0),
      });
      const fresh = await getChapters(bookId);
      setChapters(fresh);
      setActive(created.id);
    } catch (e) {
      setError(String(e));
    }
    setShowAdd(false);
    setAddTitle("");
  };

  const removeChapter = async (ch: Chapter) => {
    try {
      await deleteChapter(bookId, ch.id);
      setChapters((cs) => cs.filter((c) => c.id !== ch.id));
    } catch (e) {
      setError(String(e));
    }
  };

  const doSaveToPdf = async () => {
    setSavingPdf(true);
    try {
      setFlash(await saveOutlineToPdf(bookId));
      setTimeout(() => setFlash(""), 4000);
    } catch (e) {
      setError(String(e));
    }
    setSavingPdf(false);
  };

  const doSummarize = async (ch: Chapter) => {
    setSummarizing((s) => new Set(s).add(ch.id));
    try {
      await summarizeChapter(bookId, ch.id);
      const poll = setInterval(async () => {
        const fresh = await getChapters(bookId);
        setChapters(fresh);
        const now = fresh.find((c) => c.id === ch.id);
        if (now?.summarized) {
          clearInterval(poll);
          setSummarizing((s) => {
            const n = new Set(s); n.delete(ch.id); return n;
          });
        }
      }, 3000);
      setTimeout(() => clearInterval(poll), 180000);
    } catch (err) {
      setError(String(err));
      setSummarizing((s) => {
        const n = new Set(s); n.delete(ch.id); return n;
      });
    }
  };

  return (
    <div className="reader">
      <aside className="sidebar">
        <Link className="back" to="/">← Library</Link>
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Outline</div>
        {flash && <div className="panel" style={{ fontSize: 12, padding: 8, marginBottom: 8 }}>{flash}</div>}
        <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
          <button className="btn ghost" style={{ fontSize: 12, padding: "4px 10px" }}
            onClick={() => { setShowAdd((v) => !v); setAddPage(String(page)); }}>
            ＋ Add
          </button>
          <button className="btn ghost" style={{ fontSize: 12, padding: "4px 10px" }}
            disabled={savingPdf || chapters.length === 0} onClick={doSaveToPdf}>
            {savingPdf ? "Saving…" : "💾 Save into PDF"}
          </button>
        </div>
        {showAdd && (
          <div className="panel" style={{ padding: 8, marginBottom: 10, display: "grid", gap: 6 }}>
            <input placeholder="Title" value={addTitle}
              onChange={(e) => setAddTitle(e.target.value)} style={editInputStyle} />
            <input placeholder={`Page (1-${numPages || "?"})`} type="number" min={1} value={addPage}
              onChange={(e) => setAddPage(e.target.value)} style={editInputStyle} />
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn" style={{ fontSize: 12, padding: "4px 10px" }}
                onClick={addChapter} disabled={!addTitle.trim()}>Add</button>
              <button className="btn ghost" style={{ fontSize: 12, padding: "4px 10px" }}
                onClick={() => setShowAdd(false)}>Cancel</button>
            </div>
          </div>
        )}
        {chapters.length === 0 && !showAdd && (
          <div className="loading">
            {error || "No embedded outline in this PDF. Use ＋ Add to create one."}
          </div>
        )}
        {chapters.map((ch) => (
          <div key={ch.id}>
            {editing === ch.id ? (
              <div className="panel" style={{ padding: 8, marginBottom: 8, display: "grid", gap: 6 }}>
                <input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} style={editInputStyle} />
                <input type="number" min={1} value={editPage}
                  onChange={(e) => setEditPage(e.target.value)} style={editInputStyle} />
                <div style={{ display: "flex", gap: 6 }}>
                  <button className="btn" style={{ fontSize: 12, padding: "4px 10px" }}
                    onClick={() => saveEdit(ch)}>Save</button>
                  <button className="btn ghost" style={{ fontSize: 12, padding: "4px 10px" }}
                    onClick={() => setEditing(null)}>Cancel</button>
                </div>
              </div>
            ) : (
              <div className={`chapter-item ${active === ch.id ? "active" : ""}`}
                onClick={() => openChapter(ch)}>
                <span className="ch-num">{ch.number ?? "•"}</span>
                <span style={{ flex: 1 }}>{ch.title}</span>
                {ch.summarized === 1 && <span className="sum-dot">✓</span>}
                <span onClick={(e) => { e.stopPropagation(); startEdit(ch); }}
                  title="Edit" style={{ cursor: "pointer", opacity: 0.6, marginLeft: 6 }}>✎</span>
                <span onClick={(e) => { e.stopPropagation(); removeChapter(ch); }}
                  title="Delete" style={{ cursor: "pointer", opacity: 0.6, marginLeft: 4 }}>✕</span>
              </div>
            )}
            {active === ch.id && (
              <div className="summary-box panel">
                {ch.summarized === 1 ? (
                  <>
                    <div className="tldr">{ch.tldr}</div>
                    <div>{ch.summary}</div>
                  </>
                ) : (
                  <button className="btn" style={{ fontSize: 12, padding: "6px 12px" }}
                    disabled={summarizing.has(ch.id)} onClick={() => doSummarize(ch)}>
                    {summarizing.has(ch.id) ? "Summarizing…" : "✨ Summarize this chapter"}
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </aside>

      <main className="pdf-pane" ref={paneRef}>
        <div className="toolbar">
          <button className="btn ghost" onClick={() => setScale((s) => Math.max(0.6, s - 0.2))}>−</button>
          <input type="range" min={0.6} max={2.5} step={0.1} value={scale}
            onChange={(e) => setScale(Number(e.target.value))} />
          <button className="btn ghost" onClick={() => setScale((s) => Math.min(2.5, s + 0.2))}>+</button>
          {error && <span className="error-msg">{error}</span>}
        </div>
        <Document
          file={pdfUrl(bookId)}
          options={OPTIONS}
          onLoadSuccess={({ numPages: n }) => setNumPages(n)}
          onLoadError={(e) => setError(`PDF load failed: ${e.message}`)}
          loading={<div className="loading">Loading PDF…</div>}
        >
          {Array.from({ length: numPages }, (_, i) => (
            <div key={i} ref={(el) => { if (el) pageRefs.current.set(i + 1, el); }}>
              <Page pageNumber={i + 1} scale={scale} />
            </div>
          ))}
        </Document>
      </main>
      <div className="pdf-page-num">p. {page}{numPages ? ` / ${numPages}` : ""}</div>
    </div>
  );
}
