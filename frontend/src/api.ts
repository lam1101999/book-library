const API = "/api";

export interface User {
  id: number;
  email: string;
  name: string;
}

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

export interface Shelf {
  id: number;
  name: string;
  book_ids: number[];
}

async function req(path: string, init?: RequestInit): Promise<Response> {
  const r = await fetch(`${API}${path}`, { credentials: "include", ...init });
  if (r.status === 401) {
    window.location.href = "/login";
    throw new Error("Not signed in");
  }
  return r;
}

// ---- auth ----
export async function register(email: string, password: string, name: string) {
  const r = await fetch(`${API}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Registration failed");
  return r.json();
}

export async function login(email: string, password: string) {
  const r = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Login failed");
  return r.json();
}

export async function logout() {
  await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
}

export async function me(): Promise<User> {
  const r = await req("/auth/me");
  return r.json();
}

export const googleLoginUrl = `${API}/auth/google`;

// ---- books ----
export async function listBooks(): Promise<Book[]> {
  const r = await req("/books");
  return r.json();
}

export async function uploadBook(file: File, title?: string, author?: string): Promise<Book> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  form.append("author", author ?? "");
  const r = await req("/books", { method: "POST", body: form });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Upload failed");
  return r.json();
}

export async function deleteBook(id: number): Promise<void> {
  const r = await req(`/books/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error("Delete failed");
}

export async function getChapters(bookId: number): Promise<Chapter[]> {
  const r = await req(`/books/${bookId}/chapters`);
  return r.json();
}

export async function createChapter(
  bookId: number, body: { title: string; start_page: number; end_page?: number }
): Promise<Chapter> {
  const r = await req(`/books/${bookId}/chapters`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Create failed");
  return r.json();
}

export async function deleteChapter(bookId: number, chapterId: number): Promise<void> {
  const r = await req(`/books/${bookId}/chapters/${chapterId}`, { method: "DELETE" });
  if (!r.ok && r.status !== 204) throw new Error("Delete failed");
}

export async function saveOutlineToPdf(bookId: number): Promise<string> {
  const r = await req(`/books/${bookId}/outline/save-to-pdf`, { method: "POST" });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Save failed");
  return (await r.json()).detail;
}

export async function summarizeChapter(bookId: number, chapterId: number): Promise<void> {
  const r = await req(`/books/${bookId}/chapters/${chapterId}/summarize`, { method: "POST" });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Summarization failed to start");
}

export function pdfUrl(bookId: number): string {
  return `${API}/books/${bookId}/file`;
}

export function coverUrl(bookId: number): string {
  return `${API}/books/${bookId}/cover`;
}

// ---- shelves ----
export async function listShelves(): Promise<Shelf[]> {
  const r = await req("/shelves");
  return r.json();
}

export async function createShelf(name: string): Promise<Shelf> {
  const r = await req("/shelves", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return r.json();
}

export async function deleteShelf(id: number): Promise<void> {
  await req(`/shelves/${id}`, { method: "DELETE" });
}

export async function addToShelf(shelfId: number, bookId: number): Promise<Shelf> {
  const r = await req(`/shelves/${shelfId}/books`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ book_id: bookId }),
  });
  return r.json();
}

export async function removeFromShelf(shelfId: number, bookId: number): Promise<void> {
  await req(`/shelves/${shelfId}/books/${bookId}`, { method: "DELETE" });
}

// ---- progress ----
export async function setProgress(bookId: number, lastPage: number): Promise<void> {
  await req(`/books/${bookId}/progress`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ last_page: lastPage }),
  });
}

export async function getProgress(bookId: number): Promise<{ last_page: number; percent: number }> {
  const r = await req(`/books/${bookId}/progress`);
  return r.json();
}

export async function getAllProgress(): Promise<Record<string, { last_page: number; percent: number }>> {
  const r = await req("/progress");
  return r.json();
}
