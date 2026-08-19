interface UoLLogoProps {
  size?: "sm" | "md" | "lg";
  inverse?: boolean;
}

const DIMENSIONS: Record<NonNullable<UoLLogoProps["size"]>, { mark: number; font: number }> = {
  sm: { mark: 22, font: 13 },
  md: { mark: 30, font: 16 },
  lg: { mark: 40, font: 20 },
};

/** Crest + wordmark matching the University of Liverpool navy/red brand shown on liverpool.ac.uk. */
export default function UoLLogo({ size = "md", inverse = false }: UoLLogoProps) {
  const { mark, font } = DIMENSIONS[size];
  const markColor = inverse ? "#FFFFFF" : "var(--uol-navy)";
  const textColor = inverse ? "#FFFFFF" : "var(--uol-navy)";

  return (
    <div className="flex items-center gap-2.5">
      <svg width={mark} height={mark} viewBox="0 0 40 40" fill="none" aria-hidden="true">
        <path
          d="M20 2L4 8v10c0 10 7 17 16 20 9-3 16-10 16-20V8L20 2z"
          stroke={markColor}
          strokeWidth="1.6"
          fill="none"
        />
        <path d="M13 14h14M13 20h14M13 26h9" stroke={markColor} strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      <div className="flex flex-col leading-none">
        <span
          className="font-serif font-semibold tracking-tight"
          style={{ color: textColor, fontSize: font }}
        >
          University of Liverpool
        </span>
        <span
          className="text-xs"
          style={{ color: inverse ? "rgba(255,255,255,0.7)" : "var(--muted-foreground)", fontSize: Math.max(10, font - 5) }}
        >
          Admissions Assistant
        </span>
      </div>
    </div>
  );
}
