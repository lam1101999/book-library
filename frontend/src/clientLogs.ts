/**
 * Client error reporting: every uncaught error, rejected promise, and
 * console.error is POSTed to /api/client-logs so it lands in the backend
 * logs (visible in `docker compose logs backend` and the morning bug scan).
 */
import { API } from "./config";

let queue: Promise<void> = Promise.resolve();

function send(level: string, args: unknown[]) {
  const message = args
    .map((a) => {
      if (a instanceof Error) return `${a.name}: ${a.message}`;
      if (typeof a === "object" && a !== null) {
        try { return JSON.stringify(a); } catch { return String(a); }
      }
      return String(a);
    })
    .join(" ")
    .slice(0, 2000);
  const first = args.find((a) => a instanceof Error) as Error | undefined;
  const entry = {
    level,
    message,
    stack: first?.stack?.slice(0, 4000) ?? "",
    url: window.location.href,
    user_agent: navigator.userAgent,
  };
  // fire-and-forget, serialized so bursts don't flood; never rethrow
  queue = queue
    .then(async () => {
      try {
        await fetch(`${API}/client-logs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(entry),
          keepalive: true,
        });
      } catch { /* logging must never break the app */ }
    });
}

export function installErrorReporting() {
  window.addEventListener("error", (e) => {
    send("error", [e.error ?? e.message]);
  });
  window.addEventListener("unhandledrejection", (e) => {
    send("error", [`Unhandled promise rejection: ${e.reason}`]);
  });
  const origError = console.error.bind(console);
  console.error = (...args: unknown[]) => {
    send("error", args);
    origError(...args);
  };
}
