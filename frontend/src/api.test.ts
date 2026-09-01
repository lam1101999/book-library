import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  login, register, listBooks, uploadBook, setProgress, getProgress,
  addToShelf, createShelf,
} from "./api";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

function jsonRes(data: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => data } as Response;
}

beforeEach(() => fetchMock.mockReset());

describe("auth api", () => {
  it("register posts JSON body and returns user", async () => {
    fetchMock.mockResolvedValueOnce(jsonRes({ id: 1, email: "a@b.com", name: "" }));
    const user = await register("a@b.com", "password123", "A");
    expect(user.id).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/register", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ email: "a@b.com", password: "password123", name: "A" }),
    }));
  });

  it("register throws with server detail on 409", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes({ detail: "An account with this email already exists" }, false, 409));
    await expect(register("a@b.com", "password123", "")).rejects.toThrow("already exists");
  });

  it("login throws on bad credentials", async () => {
    fetchMock.mockResolvedValueOnce(jsonRes({ detail: "Invalid email or password" }, false, 401));
    await expect(login("a@b.com", "wrong")).rejects.toThrow("Invalid email or password");
  });
});

describe("books api", () => {
  it("listBooks GETs /api/books", async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(
      [{ id: 1, title: "T", author: "", num_pages: 0, status: "ready", error: "" }]));
    const books = await listBooks();
    expect(books[0].title).toBe("T");
    expect(fetchMock).toHaveBeenCalledWith("/api/books",
      expect.objectContaining({ credentials: "include" }));
  });

  it("uploadBook sends FormData with file/title/author", async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(
      { id: 2, title: "B", author: "X", num_pages: 0, status: "uploaded", error: "" }));
    const file = new File(["%PDF-1.4"], "b.pdf", { type: "application/pdf" });
    const book = await uploadBook(file, "B", "X");
    expect(book.id).toBe(2);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });
});

describe("progress api", () => {
  it("setProgress PUTs last_page", async () => {
    fetchMock.mockResolvedValueOnce(jsonRes({ last_page: 5, percent: 10 }));
    await setProgress(1, 5);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("PUT");
    expect(init.body).toBe(JSON.stringify({ last_page: 5 }));
  });

  it("getProgress returns parsed progress", async () => {
    fetchMock.mockResolvedValueOnce(jsonRes({ last_page: 12, percent: 24 }));
    const p = await getProgress(1);
    expect(p.last_page).toBe(12);
  });
});

describe("shelves api", () => {
  it("createShelf posts name", async () => {
    fetchMock.mockResolvedValueOnce(jsonRes({ id: 3, name: "Fav", book_ids: [] }));
    const shelf = await createShelf("Fav");
    expect(shelf.name).toBe("Fav");
    const [, init] = fetchMock.mock.calls[0];
    expect(init.body).toBe(JSON.stringify({ name: "Fav" }));
  });

  it("addToShelf posts book_id", async () => {
    fetchMock.mockResolvedValueOnce(jsonRes({ id: 3, name: "Fav", book_ids: [7] }));
    const shelf = await addToShelf(3, 7);
    expect(shelf.book_ids).toContain(7);
  });
});
