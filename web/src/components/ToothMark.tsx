export function ToothMark({ className = "", pulse = false }: { className?: string; pulse?: boolean }) {
  return (
    <span
      aria-hidden
      className={`relative inline-flex shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-accent to-accent-strong text-on-accent shadow-card ${className}`}
    >
      {pulse && <span className="absolute inset-0 animate-ping rounded-xl bg-accent/25" />}
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="relative h-[58%] w-[58%]"
      >
        <path d="M8 3C5.5 3 4 4.8 4 7.3c0 2 .7 3.3 1.2 5 .5 1.8.6 4.2 1.3 6.2.4 1.1 1.8 1.2 2.2.1.6-1.7.9-4.1 3.3-4.1s2.7 2.4 3.3 4.1c.4 1.1 1.8 1 2.2-.1.7-2 .8-4.4 1.3-6.2.5-1.7 1.2-3 1.2-5C20 4.8 18.5 3 16 3c-1.6 0-2.6.8-4 .8S9.6 3 8 3Z" />
      </svg>
    </span>
  );
}
