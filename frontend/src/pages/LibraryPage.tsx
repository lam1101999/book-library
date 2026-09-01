import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Book, Shelf, User, deleteBook, getAllProgress, listBooks, listShelves, logout, me, uploadBook } from "../api";

export default function LibraryPage() {
  const [user, setUser] = useState<User | null>(null);
  const [books, setBooks] = useState<Book[]>([]);
  const [shelves, setShelves] = useState<Shelf[]>([]);
  const [progress, setProgress] = useState<Record<string, { last_page: number; percent: number }>>({});
  const [activeShelf, setActiveShelf] = useState<number | null>(null); // null = all
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [menuBook, setMenuBook] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const nav = useNavigate();

  const refresh = useCallback(async () => {
    try {
      const [u, bs, ss, pr] = await Promise.all([me(), listBooks(), listShelves(), getAllProgress()]);
      setUser(u); setBooks(bs); setShelves(ss); setProgress(pr);
    } catch {
      // 401 redirects to /login via api.ts
    }
  }, []);

  useEffect(() => { refresh(); const t = setInterval(refresh, 4000); return () => clearInterval(t); }, [refresh]);

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError("");
    try {
      await uploadBook(file);
      await refresh();
    } catch (err) { setError(String(err)); } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation(); setMenuBook(null);
    await deleteBook(id); refresh();
  };

  const onAddToShelf = async (e: React.MouseEvent, shelfId: number, bookId: number) => {
    e.stopPropagation(); setMenuBook(null);
    const { addToShelf } = await import("../api");
    await addToShelf(shelfId, bookId); refresh();
  };

  const shown = activeShelf === null ? books
    : books.filter((b) => shelves.find((s) => s.id === activeShelf)?.book_ids.includes(b.id));

  return (
    <div className="container">
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        <h1 style={{ margin: 0 }}>📚 My Library</h1>
        {user && (
          <div style={{ display: "flex", gap: 12, alignItems: "center", fontSize: 14 }}>
            <span style={{ color: "var(--muted)" }}>{user.name || user.email}</span>
            <button className="btn ghost" style={{ fontSize: 12, padding: "6px 12px" }}
              onClick={async () => { await logout(); nav("/login"); }}>
              Sign out
            </button>
          </div>
        )}
      </header>

      {/* shelf tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        <ShelfTab label="All books" active={activeShelf === null} onClick={() => setActiveShelf(null)} />
        {shelves.map((s) => (
          <ShelfTab key={s.id} label={`${s.name} (${s.book_ids.length})`}
            active={activeShelf === s.id} onClick={() => setActiveShelf(s.id)} />
        ))}
      </div>

      <div className="upload-row">
        <input ref={fileRef} type="file" accept=".pdf" id="file-input"
          style={{ display: "none" }} onChange={onUpload} />
        <button className="btn" disabled={uploading} onClick={() => fileRef.current?.click()}>
          {uploading ? "Uploading…" : "＋ Upload PDF"}
        </button>
        {error && <span className="error-msg">{error}</span>}
      </div>

      <div className="book-grid">
        {shown.map((b) => {
          const p = progress[String(b.id)];
          return (
            <div key={b.id} className="book-card" onClick={() => nav(`/book/${b.id}`)}>
              <div className="title">{b.title}</div>
              <div className="meta">
                {b.author || "Unknown author"}
                {b.num_pages ? ` · ${b.num_pages} pages` : ""}
              </div>
              {p && p.percent > 0 && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ height: 4, background: "var(--panel2)", borderRadius: 4 }}>
                    <div style={{ height: 4, width: `${p.percent}%`, background: "var(--accent)", borderRadius: 4 }} />
                  </div>
                  <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
                    {Math.round(p.percent)}% · p.{p.last_page + 1}
                  </div>
                </div>
              )}
              <span className={`badge ${b.status}`}>
                {b.status === "error" ? `error: ${b.error.slice(0, 60)}` : b.status}
              </span>
              <div style={{ marginTop: 10, position: "relative" }}>
                <button className="btn ghost" style={{ fontSize: 12, padding: "5px 10px" }}
                  onClick={(e) => { e.stopPropagation(); setMenuBook(menuBook === b.id ? null : b.id); }}>
                  ⋯
                </button>
                {menuBook === b.id && (
                  <div className="panel" style={{ position: "absolute", zIndex: 10, top: 34, left: 0, minWidth: 180 }}>
                    <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>Add to shelf</div>
                    {shelves.map((s) => (
                      <div key={s.id} className="chapter-item" style={{ padding: "6px 8px" }}
                        onClick={(e) => onAddToShelf(e, s.id, b.id)}>
                        {s.name}
                      </div>
                    ))}
                    <div style={{ borderTop: "1px solid var(--border)", margin: "6px 0" }} />
                    <div className="chapter-item" style={{ padding: "6px 8px", color: "var(--down)" }}
                      onClick={(e) => onDelete(e, b.id)}>
                      Delete book
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {shown.length === 0 && !error && (
          <div className="panel" style={{ gridColumn: "1/-1", color: "var(--muted)" }}>
            {activeShelf === null
              ? "No books yet — upload a PDF to get started."
              : "This shelf is empty — use the ⋯ menu on a book to add it here."}
          </div>
        )}
      </div>
    </div>
  );
}

function ShelfTab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      background: active ? "var(--panel2)" : "transparent",
      border: `1px solid ${active ? "var(--border)" : "transparent"}`,
      color: active ? "var(--ink)" : "var(--muted)",
      borderRadius: 8, padding: "7px 14px", fontSize: 13, cursor: "pointer",
    }}>
      {label}
    </button>
  );
}
