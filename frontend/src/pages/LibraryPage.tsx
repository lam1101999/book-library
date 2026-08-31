import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Book, deleteBook, listBooks, uploadBook } from "../api";

export default function LibraryPage() {
  const [books, setBooks] = useState<Book[]>([]);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const nav = useNavigate();

  const refresh = useCallback(async () => {
    try {
      setBooks(await listBooks());
    } catch {
      setError("Cannot reach backend. Is it running on :8000?");
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000); // poll while books process
    return () => clearInterval(t);
  }, [refresh]);

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      await uploadBook(file);
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    await deleteBook(id);
    refresh();
  };

  return (
    <div className="container">
      <h1>📚 Book Library</h1>
      <div className="upload-row">
        <input
          ref={fileRef}
          type="file"
          accept=".pdf"
          id="file-input"
          style={{ display: "none" }}
          onChange={onUpload}
        />
        <button className="btn" disabled={uploading} onClick={() => fileRef.current?.click()}>
          {uploading ? "Uploading…" : "＋ Upload PDF"}
        </button>
        {error && <span className="error-msg">{error}</span>}
      </div>

      <div className="book-grid">
        {books.map((b) => (
          <div key={b.id} className="book-card" onClick={() => nav(`/book/${b.id}`)}>
            <div className="title">{b.title}</div>
            <div className="meta">
              {b.author || "Unknown author"}
              {b.num_pages ? ` · ${b.num_pages} pages` : ""}
            </div>
            <span className={`badge ${b.status}`}>
              {b.status === "error" ? `error: ${b.error.slice(0, 60)}` : b.status}
            </span>
            <div style={{ marginTop: 10 }}>
              <button className="btn ghost" style={{ fontSize: 12, padding: "5px 10px" }}
                onClick={(e) => onDelete(e, b.id)}>
                Delete
              </button>
            </div>
          </div>
        ))}
        {books.length === 0 && !error && (
          <div className="panel" style={{ gridColumn: "1/-1", color: "var(--muted)" }}>
            No books yet — upload a PDF to get started. Chapters are detected automatically
            from the PDF outline, or by scanning the text.
          </div>
        )}
      </div>
    </div>
  );
}
