export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      className="min-h-[100dvh] flex items-center justify-center px-4"
      style={{ backgroundColor: "var(--pq-ink)", color: "var(--pq-ivory)" }}
    >
      <div className="w-full max-w-sm">{children}</div>
    </div>
  );
}
