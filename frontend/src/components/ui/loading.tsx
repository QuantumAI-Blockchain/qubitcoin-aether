export function PhiSpinner({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div className="phi-spin h-8 w-8 rounded-full border-2 border-quantum-violet/30 border-t-glow-cyan" />
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-border-subtle ${className}`}
    />
  );
}
