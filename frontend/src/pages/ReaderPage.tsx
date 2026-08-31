import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { Chapter, getChapters, getProgress, pdfUrl, setProgress, summarizeChapter } from "../api";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

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
  const paneRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    getChapters(bookId).then(setChapters).catch(() => setError("Failed to load chapters"));
    getProgress(bookId).then((p) => p.last_page > 0 && setPage(p.last_page + 1)).catch(() => {});
  }, [bookId]);

  // track current page while scrolling
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
      saveTimer.current = setTimeout(() => setProgress(bookId, current - 1), 800);
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

  const doSummarize = async (ch: Chapter) => {
    setSummarizing((s) => new Set(s).add(ch.id));
    try {
      await summarizeChapter(bookId, ch.id);
      // poll until summary arrives (background task)
      const poll = setInterval(async () => {
        const fresh = await getChapters(bookId);
        setChapters(fresh);
        const now = fresh.find((c) => c.id === ch.id);
        if (now?.summarized) {
          clearInterval(poll);
          setSummarizing((s) => {
            const n = new Set(s);
            n.delete(ch.id);
            return n;
          });
        }
      }, 3000);
      setTimeout(() => clearInterval(poll), 180000); // give up after 3 min
    } catch (err) {
      setError(String(err));
      setSummarizing((s) => {
        const n = new Set(s);
        n.delete(ch.id);
        return n;
      });
    }
  };

  const activeChapter = chapters.find((c) => c.id === active);

  return (
    <div className="reader">
      <aside className="sidebar">
        <Link className="back" to="/">← Library</Link>
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Chapters</div>
        {chapters.length === 0 && (
          <div className="loading">
            {error || "No chapters detected yet. If the book just finished processing, refresh."}
          </div>
        )}
        {chapters.map((ch) => (
          <div key={ch.id}>
            <div
              className={`chapter-item ${active === ch.id ? "active" : ""}`}
              onClick={() => openChapter(ch)}
            >
              <span className="ch-num">{ch.number ?? "•"}</span>
              {ch.title}
              {ch.summarized === 1 && <span className="sum-dot">✓</span>}
            </div>
            {active === ch.id && (
              <div className="summary-box panel">
                {ch.summarized === 1 ? (
                  <>
                    <div className="tldr">{ch.tldr}</div>
                    <div>{ch.summary}</div>
                  </>
                ) : (
                  <button
                    className="btn"
                    style={{ fontSize: 12, padding: "6px 12px" }}
                    disabled={summarizing.has(ch.id)}
                    onClick={() => doSummarize(ch)}
                  >
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
          <input
            type="range" min={0.6} max={2.5} step={0.1} value={scale}
            onChange={(e) => setScale(Number(e.target.value))}
          />
          <button className="btn ghost" onClick={() => setScale((s) => Math.min(2.5, s + 0.2))}>+</button>
          {error && <span className="error-msg">{error}</span>}
        </div>
        <Document
          file={pdfUrl(bookId)}
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
