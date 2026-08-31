const API = "/api";

export interface Book {
  id: number;
  title: string;
  author: string;
  num_pages: number;
  status: "uploaded" | "processing" | "ready" | "error";
  error: string;
}

export interface Chapter {
  id: number;
  number: number | null;
  title: string;
  start_page: number;
  end_page: number;
  source: string;
  summary: string;
  tldr: string;
  summarized: number;
}

export async function listBooks(): Promise<Book[]> {
  const r = await fetch(`${API}/books`);
  if (!r.ok) throw new Error("Failed to load books");
  return r.json();
}

export async function uploadBook(file: File, title?: string, author?: string): Promise<Book> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  form.append("author", author ?? "");
  const r = await fetch(`${API}/books`, { method: "POST", body: form });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Upload failed");
  return r.json();
}

export async function deleteBook(id: number): Promise<void> {
  const r = await fetch(`${API}/books/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error("Delete failed");
}

export async function getChapters(bookId: number): Promise<Chapter[]> {
  const r = await fetch(`${API}/books/${bookId}/chapters`);
  if (!r.ok) throw new Error("Failed to load chapters");
  return r.json();
}

export async function summarizeChapter(bookId: number, chapterId: number): Promise<void> {
  const r = await fetch(`${API}/books/${bookId}/chapters/${chapterId}/summarize`, {
    method: "POST",
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Summarization failed to start");
}

export async function editChapter(
  bookId: number,
  chapterId: number,
  body: { title?: string; start_page?: number; end_page?: number }
): Promise<Chapter> {
  const r = await fetch(`${API}/books/${bookId}/chapters/${chapterId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("Edit failed");
  return r.json();
}

export async function setProgress(bookId: number, lastPage: number): Promise<void> {
  await fetch(`${API}/books/${bookId}/progress`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ last_page: lastPage }),
  });
}

export async function getProgress(bookId: number): Promise<{ last_page: number; percent: number }> {
  const r = await fetch(`${API}/books/${bookId}/progress`);
  return r.json();
}

export function pdfUrl(bookId: number): string {
  return `${API}/books/${bookId}/file`;
}
