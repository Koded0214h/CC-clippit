import Link from "next/link";

export default function NotFound() {
  return (
    <main className="not-found">
      <p>That page missed the brief.</p>
      <h1>Nothing to clip here.</h1>
      <Link className="button" href="/">
        Back to Clippit
      </Link>
    </main>
  );
}
