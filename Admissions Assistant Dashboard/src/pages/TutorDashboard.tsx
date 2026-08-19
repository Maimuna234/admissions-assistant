import { useState, useCallback } from "react";
import { useAuth } from "../auth";
import UoLLogo from "../components/UoLLogo";

// ─── Types ────────────────────────────────────────────────────────────────────

type Priority =
  | "entry"
  | "curriculum"
  | "outcomes"
  | "fees"
  | "teaching"
  | "rankings";

type Screen =
  | "empty"
  | "loading"
  | "complete"
  | "limited"
  | "error";

interface Citation {
  id: number;
  category: string;
  university: string;
  snippet: string;
  url: string;
  priority: Priority;
  title: string;
  fullText: string;
}

interface ComparisonSection {
  priority: Priority;
  heading: string;
  winner: "liverpool" | "competitor" | "draw";
  winnerLabel: string;
  reasoning: string;
  liverpoolData: Record<string, string>;
  competitorData: Record<string, string>;
  citationIds: number[];
  hasLimitedData?: boolean;
}

interface ComparisonData {
  sections: ComparisonSection[];
  citations: Citation[];
  recommendation: {
    university: string;
    explanation: string;
    prioritiesSupported: number;
    confidence: "High" | "Moderate" | "Limited";
    note?: string;
  };
}

interface ApiCitation {
  label?: string;
  source?: string;
  url?: string;
  snippet?: string;
  content?: string;
}

interface ApiComparisonResult {
  answer?: string;
  citations?: ApiCitation[];
  should_abstain?: boolean;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

function priorityFromHeading(heading: string): Priority | null {
  const value = heading.toLowerCase();
  if (value.includes("entry")) return "entry";
  if (value.includes("curriculum") || value.includes("accredit")) return "curriculum";
  if (value.includes("graduate") || value.includes("salary") || value.includes("outcome")) return "outcomes";
  if (value.includes("fee") || value.includes("cost")) return "fees";
  if (value.includes("teaching") || value.includes("nss") || value.includes("quality")) return "teaching";
  if (value.includes("rank")) return "rankings";
  return null;
}

function splitComparisonAnswer(answer: string, selected: Set<Priority>, competitor: string): ComparisonSection[] {
  const withoutRecommendation = answer.split(/Overall recommendation:/i)[0].replace(/^Decision summary:\s*/i, "");
  return withoutRecommendation.split(/\s*\|\s*/).flatMap((rawSection) => {
    const match = rawSection.match(/^([^:]+):\s*(.*)$/s);
    if (!match) return [];
    const heading = match[1].trim();
    const priority = priorityFromHeading(heading);
    if (!priority || !selected.has(priority)) return [];
    const detail = match[2].trim();
    const winnerMatch = detail.match(/Winner:\s*([^.]*)/i);
    const winnerText = winnerMatch?.[1]?.trim() ?? "";
    const winner = winnerText.toLowerCase().includes("unavailable")
      ? "draw"
      : winnerText.toLowerCase().includes("liverpool")
        ? "liverpool"
        : winnerText.toLowerCase().includes(competitor.toLowerCase())
          ? "competitor"
          : "draw";
    const cleanDetail = detail.replace(/\s*Winner:.*$/i, "").trim();
    return [{
      priority,
      heading,
      winner,
      winnerLabel: winner === "liverpool" ? "University of Liverpool" : winner === "competitor" ? competitor : "Draw",
      reasoning: cleanDetail,
      liverpoolData: { "Evidence": cleanDetail },
      competitorData: { "Evidence": cleanDetail },
      citationIds: [],
      hasLimitedData: winner === "draw" && /unavailable|not available|limited/i.test(detail),
    }];
  });
}

function mapApiResult(result: ApiComparisonResult, selected: Set<Priority>, competitor: string): ComparisonData {
  const answer = result.answer ?? "Insufficient information in the provided context.";
  const sections = splitComparisonAnswer(answer, selected, competitor);
  const citations: Citation[] = (result.citations ?? []).map((citation, index) => {
    const text = `${citation.label ?? ""} ${citation.snippet ?? ""} ${citation.content ?? ""}`;
    const priority = priorityFromHeading(text) ?? [...selected][index % Math.max(selected.size, 1)] ?? "entry";
    return {
      id: index + 1,
      category: citation.label ?? "Verified evidence",
      university: text.match(/University of [A-Za-z ]+/)?.[0]?.trim() ?? "University evidence",
      snippet: citation.snippet ?? citation.content?.slice(0, 220) ?? "Verified source evidence",
      url: citation.url ?? citation.source ?? "",
      priority,
      title: citation.label ?? "Verified source evidence",
      fullText: citation.content ?? citation.snippet ?? "No evidence text available.",
    };
  });
  const recommendationMatch = answer.match(/Overall recommendation:\s*(.*?)(?:\s*\[\d+\]|$)/i);
  const recommendationText = recommendationMatch?.[1]?.trim() ?? "Review the evidence across the selected priorities.";
  const recommendationUniversity = recommendationText.match(/(University of [A-Za-z ]+|Lancaster University|Queen Mary University London)/)?.[1] ?? "Evidence comparison";
  sections.forEach((section) => {
    section.citationIds = citations.filter((citation) => citation.priority === section.priority).map((citation) => citation.id);
  });
  return {
    sections,
    citations,
    recommendation: {
      university: recommendationUniversity,
      explanation: recommendationText,
      prioritiesSupported: sections.filter((section) => !section.hasLimitedData).length,
      confidence: result.should_abstain ? "Limited" : sections.some((section) => section.hasLimitedData) ? "Moderate" : "High",
      note: sections.some((section) => section.hasLimitedData) ? "Some selected priorities have limited comparable evidence." : undefined,
    },
  };
}

// ─── Data ─────────────────────────────────────────────────────────────────────

const COMPETITORS = [
  "University of Leeds",
  "University of Sheffield",
  "University of Manchester",
  "Lancaster University",
  "University of Nottingham",
  "University of Birmingham",
  "Newcastle University",
  "Liverpool John Moores University",
  "Manchester Metropolitan University",
  "Queen Mary University London",
];

const PRIORITY_LABELS: Record<Priority, string> = {
  entry: "Entry Requirements",
  curriculum: "Curriculum & Accreditation",
  outcomes: "Graduate Outcomes & Salary",
  fees: "Fees & Cost",
  teaching: "Teaching Quality & NSS",
  rankings: "University Rankings",
};

// ─── Mock comparison data per competitor ─────────────────────────────────────

function getMockData(competitor: string): {
  sections: ComparisonSection[];
  citations: Citation[];
  recommendation: {
    university: string;
    explanation: string;
    prioritiesSupported: number;
    confidence: "High" | "Moderate" | "Limited";
    note?: string;
  };
} {
  const isLeeds = competitor === "University of Leeds";
  const isManchester = competitor === "University of Manchester";
  const isSheffield = competitor === "University of Sheffield";

  const compShort = competitor.replace("University of ", "").replace(" University", "");

  const sections: ComparisonSection[] = [
    {
      priority: "entry",
      heading: "Entry Requirements",
      winner: isLeeds ? "competitor" : "draw",
      winnerLabel: isLeeds ? competitor : "Draw",
      reasoning: isLeeds
        ? `${competitor} has slightly lower typical offers, broadening access.`
        : "Both universities set equivalent competitive entry standards.",
      liverpoolData: {
        "A-level typical": "ABB–AAB",
        "IB Diploma": "33–35 points",
        "GCSE Maths": "Grade B / 5 required",
        "English Language": "IELTS 6.5 overall",
        "UCAS tariff": "Not published as primary metric",
      },
      competitorData: {
        "A-level typical": isLeeds ? "AAB" : isManchester ? "AAA" : "ABB–AAB",
        "IB Diploma": isManchester ? "37 points" : "33 points",
        "GCSE Maths": "Grade B / 5 required",
        "English Language": "IELTS 6.5 overall",
        "UCAS tariff": "Not published as primary metric",
      },
      citationIds: [1, 2],
    },
    {
      priority: "curriculum",
      heading: "Curriculum & Accreditation",
      winner: "liverpool",
      winnerLabel: "University of Liverpool",
      reasoning:
        "Liverpool holds full BCS accreditation with an integrated placement year and broader module choice in AI.",
      liverpoolData: {
        "BCS accreditation": "Full accreditation (2023–2027)",
        "Core modules": "Algorithms, Software Engineering, AI, Networks",
        "Final-year project": "Individual dissertation (30 credits)",
        "Placement year": "Available (Year in Industry)",
        "Study abroad": "Available (selected partners)",
      },
      competitorData: {
        "BCS accreditation": isSheffield
          ? "Full accreditation"
          : "Partial / not listed",
        "Core modules": "Algorithms, Software Engineering, Databases",
        "Final-year project": "Individual project (30 credits)",
        "Placement year": "Available",
        "Study abroad": isManchester ? "Available" : "Not available",
      },
      citationIds: [3, 4],
    },
    {
      priority: "outcomes",
      heading: "Graduate Outcomes & Salary",
      winner: isManchester ? "competitor" : "liverpool",
      winnerLabel: isManchester ? competitor : "University of Liverpool",
      reasoning: isManchester
        ? `${competitor} graduates report marginally higher median salaries at 3 years.`
        : "Liverpool graduates show strong professional employment rates at 3 years.",
      liverpoolData: {
        "Median salary (3yr)": "£31,500",
        "Median salary (5yr)": "£38,200",
        "Employment rate": "92%",
        "Professional employment": "78%",
      },
      competitorData: {
        "Median salary (3yr)": isManchester ? "£33,100" : isLeeds ? "£30,800" : "£31,000",
        "Median salary (5yr)": isManchester ? "£40,500" : "£37,000",
        "Employment rate": "91%",
        "Professional employment": isManchester ? "81%" : "75%",
      },
      citationIds: [5, 6],
    },
    {
      priority: "fees",
      heading: "Fees & Cost",
      winner: "draw",
      winnerLabel: "Draw",
      reasoning: "Both universities charge equivalent home tuition fees; international fees are comparable.",
      liverpoolData: {
        "Home tuition fee": "£9,535 (2025/26)",
        "International fee": "£22,300 per year",
        "Placement year fee": "£1,000 (reduced)",
        "Study abroad fee": "£1,385 (reduced)",
      },
      competitorData: {
        "Home tuition fee": "£9,535 (2025/26)",
        "International fee": isManchester ? "£26,500 per year" : "£21,000–£23,000",
        "Placement year fee": "£1,000–£1,500",
        "Study abroad fee": "Not available",
      },
      citationIds: [7, 8],
    },
    {
      priority: "teaching",
      heading: "Teaching Quality & NSS",
      winner: isLeeds ? "competitor" : "liverpool",
      winnerLabel: isLeeds ? competitor : "University of Liverpool",
      reasoning: isLeeds
        ? `${competitor} scores marginally higher on NSS teaching satisfaction for CS.`
        : "Liverpool achieves strong NSS scores and holds a TEF Silver rating.",
      liverpoolData: {
        "NSS teaching satisfaction": "82%",
        "Facilities score": "79%",
        "Mental wellbeing score": "71%",
        "TEF rating": "Silver",
      },
      competitorData: {
        "NSS teaching satisfaction": isLeeds ? "85%" : isManchester ? "80%" : "81%",
        "Facilities score": isLeeds ? "83%" : "77%",
        "Mental wellbeing score": "70%",
        "TEF rating": isManchester ? "Gold" : "Silver",
      },
      citationIds: [9, 10],
      hasLimitedData: isSheffield,
    },
    {
      priority: "rankings",
      heading: "University Rankings",
      winner: isManchester ? "competitor" : "liverpool",
      winnerLabel: isManchester ? competitor : "University of Liverpool",
      reasoning: isManchester
        ? `${competitor} ranks higher in both CUG and QS World rankings.`
        : "Liverpool ranks competitively for Computer Science in the UK.",
      liverpoolData: {
        "CUG CS ranking": "26th (UK)",
        "CUG overall UK": "38th",
        "QS World Ranking": "201–250",
        "Ranking source": "CUG 2025, QS World 2025",
      },
      competitorData: {
        "CUG CS ranking": isManchester ? "5th (UK)" : isLeeds ? "22nd (UK)" : "30th (UK)",
        "CUG overall UK": isManchester ? "12th" : isLeeds ? "28th" : "42nd",
        "QS World Ranking": isManchester ? "32" : isLeeds ? "101–150" : "151–200",
        "Ranking source": "CUG 2025, QS World 2025",
      },
      citationIds: [11, 12],
    },
  ];

  const citations: Citation[] = [
    {
      id: 1,
      category: "Official course page",
      university: "University of Liverpool",
      snippet: "A-level offer: ABB–AAB including Mathematics. IB: 33–35 points.",
      url: "https://www.liverpool.ac.uk/study/undergraduate/courses/computer-science-bsc-hons/entry/",
      priority: "entry",
      title: "Computer Science BSc — Entry Requirements",
      fullText:
        "Typical offer: ABB–AAB including Mathematics at grade B or above. International Baccalaureate: 33–35 points overall. GCSE: Mathematics grade B (5). English Language: IELTS 6.5 with no component below 6.0.",
    },
    {
      id: 2,
      category: "Entry requirements",
      university: competitor,
      snippet: `A-level offer: ${isManchester ? "AAA" : "AAB"} including Mathematics.`,
      url: `https://www.${compShort.toLowerCase().replace(/ /g, "")}.ac.uk/cs/entry-requirements`,
      priority: "entry",
      title: `Computer Science BSc — Entry Requirements — ${competitor}`,
      fullText: `Typical offer: ${isManchester ? "AAA" : "AAB"} including Mathematics. The university considers contextual offers in certain circumstances. UCAS tariff is not the primary metric used in selection.`,
    },
    {
      id: 3,
      category: "Official course page",
      university: "University of Liverpool",
      snippet: "BCS accredited 2023–2027. Placement year available.",
      url: "https://www.liverpool.ac.uk/study/undergraduate/courses/computer-science-bsc-hons/",
      priority: "curriculum",
      title: "Computer Science BSc — Course Overview — Liverpool",
      fullText:
        "The programme is fully accredited by the British Computer Society (BCS) for the period 2023–2027. Students may opt for an integrated placement year in industry. Final-year dissertation is 30 credits. Specialist AI and machine learning modules available from Year 2.",
    },
    {
      id: 4,
      category: "Official course page",
      university: competitor,
      snippet: `${isSheffield ? "Full BCS accreditation." : "Accreditation status: partial or not listed."}`,
      url: `https://www.${compShort.toLowerCase().replace(/ /g, "")}.ac.uk/courses/computer-science`,
      priority: "curriculum",
      title: `Computer Science BSc — Curriculum — ${competitor}`,
      fullText: `${isSheffield ? "The programme holds full BCS accreditation." : "Accreditation status is not explicitly stated on the course page; prospective students are advised to contact the department."} Core modules include Algorithms, Software Engineering, and Databases. A final-year project worth 30 credits is required.`,
    },
    {
      id: 5,
      category: "Structured admissions database",
      university: "University of Liverpool",
      snippet: "Median salary 3yr: £31,500. Employment rate: 92%.",
      url: "https://www.hesa.ac.uk/graduate-outcomes",
      priority: "outcomes",
      title: "HESA Graduate Outcomes — Liverpool CS",
      fullText:
        "Source: HESA Graduate Outcomes Survey 2023. University of Liverpool Computer Science graduates: median salary at 3 years post-graduation £31,500; at 5 years £38,200. Employment rate 92%. Professional or managerial employment 78%.",
    },
    {
      id: 6,
      category: "Structured admissions database",
      university: competitor,
      snippet: `Median salary 3yr: ${isManchester ? "£33,100" : "£30,800"}. Employment rate: 91%.`,
      url: "https://www.hesa.ac.uk/graduate-outcomes",
      priority: "outcomes",
      title: `HESA Graduate Outcomes — ${compShort} CS`,
      fullText: `Source: HESA Graduate Outcomes Survey 2023. ${competitor} Computer Science graduates: median salary at 3 years post-graduation ${isManchester ? "£33,100" : "£30,800"}; at 5 years ${isManchester ? "£40,500" : "£37,000"}. Employment rate 91%.`,
    },
    {
      id: 7,
      category: "Fee information",
      university: "University of Liverpool",
      snippet: "Home fee: £9,535. International fee: £22,300 (2025/26).",
      url: "https://www.liverpool.ac.uk/study/undergraduate/fees-and-funding/",
      priority: "fees",
      title: "Undergraduate Fees — University of Liverpool",
      fullText:
        "Home/UK students: £9,535 per year for 2025/26 entry. International students: £22,300 per year. Placement year fee: £1,000 (reduced). Study abroad year fee: £1,385 (reduced). Figures subject to annual review.",
    },
    {
      id: 8,
      category: "Fee information",
      university: competitor,
      snippet: `Home fee: £9,535. International fee: ${isManchester ? "£26,500" : "£21,000–£23,000"}.`,
      url: `https://www.${compShort.toLowerCase().replace(/ /g, "")}.ac.uk/fees`,
      priority: "fees",
      title: `Undergraduate Fees — ${competitor}`,
      fullText: `Home/UK students: £9,535 per year for 2025/26 entry. International students: ${isManchester ? "£26,500" : "£21,000–£23,000"} per year. Figures are subject to annual review.`,
    },
    {
      id: 9,
      category: "Ranking verification page",
      university: "University of Liverpool",
      snippet: "NSS teaching: 82%. TEF: Silver.",
      url: "https://www.thecompleteuniversityguide.co.uk/universities/university-of-liverpool",
      priority: "teaching",
      title: "CUG Profile — University of Liverpool",
      fullText:
        "NSS teaching satisfaction (Computer Science): 82%. NSS facilities: 79%. Mental wellbeing score: 71%. TEF rating: Silver (2023). Source: Complete University Guide 2025.",
    },
    {
      id: 10,
      category: "Ranking verification page",
      university: competitor,
      snippet: `NSS teaching: ${isLeeds ? "85%" : "81%"}. TEF: ${isManchester ? "Gold" : "Silver"}.`,
      url: `https://www.thecompleteuniversityguide.co.uk/universities/${compShort.toLowerCase().replace(/ /g, "-")}`,
      priority: "teaching",
      title: `CUG Profile — ${competitor}`,
      fullText: `NSS teaching satisfaction (Computer Science): ${isLeeds ? "85%" : "81%"}. NSS facilities: ${isLeeds ? "83%" : "77%"}. Mental wellbeing score: 70%. TEF rating: ${isManchester ? "Gold (2023)" : "Silver (2023)"}. Source: Complete University Guide 2025.`,
    },
    {
      id: 11,
      category: "Ranking verification page",
      university: "University of Liverpool",
      snippet: "CUG CS rank: 26th. QS World: 201–250.",
      url: "https://www.thecompleteuniversityguide.co.uk/league-tables/rankings/computer-science",
      priority: "rankings",
      title: "CUG CS Rankings 2025 — University of Liverpool",
      fullText:
        "Complete University Guide 2025: University of Liverpool ranked 26th in the UK for Computer Science. Overall UK ranking: 38th. QS World University Rankings 2025: 201–250 globally.",
    },
    {
      id: 12,
      category: "Ranking verification page",
      university: competitor,
      snippet: `CUG CS rank: ${isManchester ? "5th" : isLeeds ? "22nd" : "30th"}. QS World: ${isManchester ? "32" : isLeeds ? "101–150" : "151–200"}.`,
      url: "https://www.thecompleteuniversityguide.co.uk/league-tables/rankings/computer-science",
      priority: "rankings",
      title: `CUG CS Rankings 2025 — ${competitor}`,
      fullText: `Complete University Guide 2025: ${competitor} ranked ${isManchester ? "5th" : isLeeds ? "22nd" : "30th"} in the UK for Computer Science. Overall UK ranking: ${isManchester ? "12th" : isLeeds ? "28th" : "42nd"}. QS World University Rankings 2025: ${isManchester ? "32" : isLeeds ? "101–150" : "151–200"} globally.`,
    },
  ];

  const liverpoolWins = sections.filter((s) => s.winner === "liverpool").length;
  const compWins = sections.filter((s) => s.winner === "competitor").length;
  const recUniversity = liverpoolWins >= compWins ? "University of Liverpool" : competitor;
  const prioritiesSupported = Math.max(liverpoolWins, compWins);

  return {
    sections,
    citations,
    recommendation: {
      university: recUniversity,
      explanation:
        recUniversity === "University of Liverpool"
          ? `Liverpool offers stronger overall performance across your selected priorities, particularly in curriculum accreditation and graduate outcomes.`
          : `${competitor} demonstrates stronger performance in the priorities you have selected, particularly in rankings and entry competitiveness.`,
      prioritiesSupported,
      confidence: isManchester ? "High" : liverpoolWins === compWins ? "Moderate" : "High",
      note:
        liverpoolWins === compWins
          ? "Evidence is closely matched across priorities — consider institutional fit and geography."
          : undefined,
    },
  };
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatusBadge({ label, dot = true }: { label: string; dot?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-sm"
      style={{ background: "rgba(255,255,255,0.12)", color: "rgba(255,255,255,0.85)" }}>
      {dot && <span className="w-1.5 h-1.5 rounded-full" style={{ background: "rgba(255,255,255,0.7)" }} />}
      {label}
    </span>
  );
}

function WinnerBadge({ label, variant }: { label: string; variant: "win" | "draw" }) {
  if (variant === "draw") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-sm"
        style={{ background: "var(--muted)", color: "var(--muted-foreground)" }}>
        Draw
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-sm"
      style={{ background: "rgba(0,48,135,0.1)", color: "var(--uol-navy)" }}>
      <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
      {label}
    </span>
  );
}

function DataRow({ label, liverValue, compValue, highlight }: {
  label: string;
  liverValue: string;
  compValue: string;
  highlight?: boolean;
}) {
  return (
    <div className="grid gap-2 py-1.5 border-b last:border-0 text-xs"
      style={{ gridTemplateColumns: "1fr 1fr 1fr", borderColor: "var(--border)" }}>
      <span style={{ color: "var(--muted-foreground)" }}>{label}</span>
      <span className={highlight ? "font-semibold" : ""} style={{ color: "var(--foreground)" }}>{liverValue}</span>
      <span className={highlight ? "font-semibold" : ""} style={{ color: "var(--foreground)" }}>{compValue}</span>
    </div>
  );
}


function VerifiedDot() {
  return (
    <span title="Verified data source" className="inline-block w-1.5 h-1.5 rounded-full ml-1 align-middle"
      style={{ background: "var(--uol-navy)" }} />
  );
}

function ComparisonSectionCard({
  section,
  competitor,
  onCitationClick,
}: {
  section: ComparisonSection;
  competitor: string;
  onCitationClick: (id: number) => void;
}) {
  const compShort = competitor.replace("University of ", "Univ. of ");

  return (
    <div className="border rounded-sm overflow-hidden" style={{ borderColor: "var(--border)" }}>
      <div className="flex items-center justify-between px-3 py-2 border-b"
        style={{ background: "var(--muted)", borderColor: "var(--border)" }}>
        <h3 className="font-serif text-sm font-semibold" style={{ color: "var(--foreground)" }}>
          {section.heading}
          {!section.hasLimitedData && <VerifiedDot />}
        </h3>
        <div className="flex items-center gap-2">
          {section.hasLimitedData && (
            <span className="text-xs px-1.5 py-0.5 rounded-sm"
              style={{ background: "#FEF3C7", color: "#92400E" }}>
              Limited data
            </span>
          )}
          <WinnerBadge
            label={section.winner === "draw" ? "Draw" : section.winner === "liverpool" ? "Liverpool" : compShort}
            variant={section.winner === "draw" ? "draw" : "win"}
          />
        </div>
      </div>

      <div className="px-3 py-2">
        {/* Column headers */}
        <div className="grid gap-2 pb-1.5 border-b mb-1" style={{ gridTemplateColumns: "1fr 1fr 1fr", borderColor: "var(--border)" }}>
          <span className="text-xs font-medium" style={{ color: "var(--muted-foreground)" }}>Criterion</span>
          <span className="text-xs font-medium" style={{ color: "var(--foreground)" }}>Liverpool</span>
          <span className="text-xs font-medium" style={{ color: "var(--foreground)" }}>{compShort}</span>
        </div>

        {Object.entries(section.liverpoolData).map(([key, val]) => (
          <DataRow
            key={key}
            label={key}
            liverValue={val || ""}
            compValue={section.competitorData[key] || ""}
            highlight={key.includes("salary") || key.includes("rank") || key.includes("fee")}
          />
        ))}

        <div className="mt-2 pt-2 border-t" style={{ borderColor: "var(--border)" }}>
          <p className="text-xs italic" style={{ color: "var(--muted-foreground)" }}>
            {section.reasoning}
          </p>
          <div className="flex items-center gap-2 mt-1.5">
            {section.citationIds.map((id) => (
              <button
                key={id}
                onClick={() => onCitationClick(id)}
                className="text-xs font-medium underline underline-offset-2 hover:no-underline"
                style={{ color: "var(--uol-navy)" }}
                aria-label={`View citation ${id}`}
              >
                [{id}]
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function SkeletonSection() {
  return (
    <div className="border rounded-sm overflow-hidden" style={{ borderColor: "var(--border)" }}>
      <div className="px-3 py-2 border-b" style={{ background: "var(--muted)", borderColor: "var(--border)" }}>
        <div className="skeleton h-4 w-40 rounded" />
      </div>
      <div className="px-3 py-3 space-y-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="grid gap-2" style={{ gridTemplateColumns: "1fr 1fr 1fr" }}>
            <div className="skeleton h-3 rounded" style={{ width: `${60 + i * 10}%` }} />
            <div className="skeleton h-3 rounded" style={{ width: "70%" }} />
            <div className="skeleton h-3 rounded" style={{ width: "65%" }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function CitationModal({
  citation,
  onClose,
}: {
  citation: Citation;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(42,42,39,0.5)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
      role="dialog"
      aria-modal="true"
      aria-label={`Citation ${citation.id} detail`}
    >
      <div
        className="relative w-full max-w-lg rounded-sm border shadow-lg"
        style={{ background: "var(--card)", borderColor: "var(--border)" }}
      >
        <div className="flex items-start justify-between px-5 py-4 border-b" style={{ borderColor: "var(--border)" }}>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono font-semibold px-1.5 py-0.5 rounded-sm"
                style={{ background: "var(--muted)", color: "var(--foreground)" }}>
                [{citation.id}]
              </span>
              <span className="text-xs px-2 py-0.5 rounded-sm"
                style={{ background: "rgba(0,48,135,0.08)", color: "var(--uol-navy)" }}>
                {citation.category}
              </span>
            </div>
            <h3 className="font-serif text-base font-semibold" style={{ color: "var(--foreground)" }}>
              {citation.title}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="ml-4 flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-sm hover:bg-muted"
            style={{ background: "var(--muted)" }}
            aria-label="Close citation"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="px-5 py-4 space-y-3">
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="block mb-0.5 font-medium" style={{ color: "var(--muted-foreground)" }}>University</span>
              <span style={{ color: "var(--foreground)" }}>{citation.university}</span>
            </div>
            <div>
              <span className="block mb-0.5 font-medium" style={{ color: "var(--muted-foreground)" }}>Data category</span>
              <span style={{ color: "var(--foreground)" }}>{citation.category}</span>
            </div>
          </div>

          <div className="p-3 rounded-sm text-xs leading-relaxed"
            style={{ background: "var(--muted)", color: "var(--foreground)" }}>
            {citation.fullText}
          </div>

          <div className="flex items-center gap-2">
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-medium underline underline-offset-2 hover:no-underline"
              style={{ color: "var(--uol-navy)" }}
            >
              Open source page
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </a>
            <span className="text-xs" style={{ color: "var(--muted-foreground)" }}>
              — {citation.url.replace("https://", "")}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Tutor Dashboard ──────────────────────────────────────────────────────────

export default function TutorDashboard() {
  const { user, logout } = useAuth();
  const [competitor, setCompetitor] = useState<string>(COMPETITORS[0]);
  const [priorities, setPriorities] = useState<Set<Priority>>(
    new Set(["entry", "curriculum", "outcomes"])
  );
  const [prompt, setPrompt] = useState(
    "Compare the target programme against the selected competitor university using the selected priorities and return a short decision summary."
  );
  const [screen, setScreen] = useState<Screen>("empty");
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [comparisonData, setComparisonData] = useState<ComparisonData | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const togglePriority = useCallback((p: Priority) => {
    setPriorities((prev) => {
      const next = new Set(prev);
      if (next.has(p)) next.delete(p);
      else next.add(p);
      return next;
    });
  }, []);

  const handleCompare = useCallback(async () => {
    if (priorities.size === 0) {
      setValidationError("Please select at least one priority before comparing.");
      return;
    }
    setValidationError(null);
    setScreen("loading");
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: {
          Authorization: "Bearer openwebui-local-key",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: prompt,
          target_programme: "Computer Science BSc",
          baseline_university: "University of Liverpool",
          competitor_university: competitor,
          priorities: [...priorities].map((priority) => PRIORITY_LABELS[priority]),
        }),
      });
      if (!response.ok) throw new Error(`Comparison request failed (${response.status})`);
      const result = (await response.json()) as ApiComparisonResult;
      const data = mapApiResult(result, priorities, competitor);
      setComparisonData(data);
      setScreen(data.sections.some((section) => section.hasLimitedData) ? "limited" : "complete");
    } catch (error) {
      setValidationError(error instanceof Error ? error.message : "Unable to load the comparison.");
      setComparisonData(null);
      setScreen("error");
    }
  }, [competitor, priorities, prompt]);

  const handleReset = useCallback(() => {
    setScreen("empty");
    setComparisonData(null);
    setValidationError(null);
    setCompetitor(COMPETITORS[0]);
    setPriorities(new Set(["entry", "curriculum", "outcomes"]));
    setPrompt("Compare the target programme against the selected competitor university using the selected priorities and return a short decision summary.");
  }, []);

  const filteredSections = comparisonData?.sections ?? [];
  const filteredCitations = comparisonData?.citations ?? [];

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--background)" }}>

      {/* UoL red stripe */}
      <div className="h-1 flex-shrink-0" style={{ background: "var(--uol-red)" }} />

      {/* Header — UoL navy */}
      <header className="border-b flex-shrink-0" style={{ borderColor: "rgba(255,255,255,0.1)", background: "var(--uol-navy)" }}>
        <div className="max-w-screen-xl mx-auto px-4 sm:px-6 h-12 flex items-center justify-between">
          <UoLLogo size="sm" inverse />

          <div className="flex items-center gap-2">
            <StatusBadge label="Verified data" />
            <button onClick={handleReset} title="Reset comparison"
              className="w-7 h-7 flex items-center justify-center rounded-sm"
              style={{ color: "rgba(255,255,255,0.7)" }} aria-label="Reset">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 12a9 9 0 109-9 9.75 9.75 0 00-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
              </svg>
            </button>
            <span className="hidden sm:flex items-center gap-1.5 px-2 py-1 rounded-sm text-xs"
              style={{ background: "rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.85)" }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>
              </svg>
              {user?.name?.split(" ").slice(-1)[0]}
            </span>
            <button onClick={logout} title="Sign out"
              className="w-7 h-7 flex items-center justify-center rounded-sm"
              style={{ color: "rgba(255,255,255,0.7)" }} aria-label="Sign out">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-screen-xl mx-auto w-full px-4 sm:px-6 py-4">
            <div className="dashboard-grid grid gap-4">

              {/* ── Left Panel: Input ─────────────────────────────── */}
              <div className="border rounded-sm overflow-hidden" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
                <div className="px-4 py-3 border-b" style={{ borderColor: "var(--border)", background: "var(--muted)" }}>
                  <h2 className="font-serif font-semibold text-sm" style={{ color: "var(--foreground)" }}>
                    Admissions Tutor Input
                  </h2>
                </div>

                <div className="px-4 py-4 space-y-4">
                  {/* Target programme */}
                  <div>
                    <label className="block text-xs font-medium mb-1" style={{ color: "var(--foreground)" }}>
                      Target programme
                    </label>
                    <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-sm border text-xs"
                      style={{ borderColor: "var(--border)", background: "var(--muted)", color: "var(--foreground)" }}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: "var(--muted-foreground)", flexShrink: 0 }}>
                        <path d="M12 14l9-5-9-5-9 5 9 5z" />
                      </svg>
                      Computer Science BSc
                    </div>
                    <p className="text-xs mt-1" style={{ color: "var(--muted-foreground)" }}>
                      Baseline: University of Liverpool
                    </p>
                  </div>

                  {/* Competitor */}
                  <div>
                    <label htmlFor="competitor-select" className="block text-xs font-medium mb-1" style={{ color: "var(--foreground)" }}>
                      Competitor university
                    </label>
                    <select
                      id="competitor-select"
                      value={competitor}
                      onChange={(e) => { setCompetitor(e.target.value); setScreen("empty"); }}
                      className="w-full px-2.5 py-1.5 rounded-sm border text-xs"
                      style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--foreground)" }}
                    >
                      {COMPETITORS.map((u) => (
                        <option key={u} value={u}>{u}</option>
                      ))}
                    </select>
                  </div>

                  {/* Priorities */}
                  <div>
                    <fieldset>
                      <legend className="text-xs font-medium mb-2" style={{ color: "var(--foreground)" }}>
                        Student priorities
                      </legend>
                      <div className="space-y-1.5">
                        {(Object.entries(PRIORITY_LABELS) as [Priority, string][]).map(([key, label]) => (
                          <label key={key} className="flex items-center gap-2 cursor-pointer group">
                            <input
                              type="checkbox"
                              checked={priorities.has(key)}
                              onChange={() => togglePriority(key)}
                              aria-label={label}
                            />
                            <span className="text-xs group-hover:underline" style={{ color: "var(--foreground)" }}>
                              {label}
                            </span>
                          </label>
                        ))}
                      </div>
                    </fieldset>
                    {validationError && (
                      <p className="text-xs mt-2 font-medium" style={{ color: "#B91C1C" }} role="alert">
                        {validationError}
                      </p>
                    )}
                  </div>

                  {/* Prompt textarea */}
                  <div>
                    <label htmlFor="tutor-prompt" className="block text-xs font-medium mb-1" style={{ color: "var(--foreground)" }}>
                      Comparison instruction
                    </label>
                    <textarea
                      id="tutor-prompt"
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      rows={4}
                      className="w-full px-2.5 py-2 rounded-sm border text-xs leading-relaxed resize-y"
                      style={{
                        borderColor: "var(--border)",
                        background: "var(--card)",
                        color: "var(--foreground)",
                        minHeight: "80px",
                      }}
                    />
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2">
                    <button
                      onClick={handleCompare}
                      disabled={screen === "loading"}
                      className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-sm text-xs font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                      style={{
                        background: screen === "loading" ? "var(--muted-foreground)" : "var(--primary)",
                        color: "var(--primary-foreground)",
                      }}
                      aria-label="Run comparison"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                      </svg>
                      {screen === "loading" ? "Comparing…" : "Compare"}
                    </button>
                    <button
                      onClick={handleReset}
                      className="px-3 py-2 rounded-sm border text-xs font-medium flex items-center gap-1.5 hover:bg-muted"
                      style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
                      aria-label="Reset form"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M3 12a9 9 0 109-9 9.75 9.75 0 00-6.74 2.74L3 8" /><path d="M3 3v5h5" />
                      </svg>
                      Reset
                    </button>
                  </div>
                </div>
              </div>

              {/* ── Centre Panel: Summary ─────────────────────────── */}
              <div className="border rounded-sm overflow-hidden" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
                <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: "var(--border)", background: "var(--muted)" }}>
                  <h2 className="font-serif font-semibold text-sm" style={{ color: "var(--foreground)" }}>
                    Comparison Summary
                  </h2>
                  {(screen === "complete" || screen === "limited") && (
                    <span className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                      Liverpool vs {competitor.replace("University of ", "Univ. of ")}
                    </span>
                  )}
                </div>

                <div className="px-4 py-4">
                  {/* Empty state */}
                  {screen === "empty" && (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                      <div className="w-10 h-10 rounded-full flex items-center justify-center mb-3"
                        style={{ background: "var(--muted)" }}>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: "var(--muted-foreground)" }}>
                          <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
                          <rect x="9" y="3" width="6" height="4" rx="1" ry="1" />
                        </svg>
                      </div>
                      <p className="text-sm font-medium mb-1" style={{ color: "var(--foreground)" }}>
                        Your verified comparison will appear here.
                      </p>
                      <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                        Select a competitor, choose priorities, and click Compare.
                      </p>
                    </div>
                  )}

                  {/* Loading state */}
                  {screen === "loading" && (
                    <div className="space-y-4">
                      <div className="flex items-center gap-2 pb-3 border-b" style={{ borderColor: "var(--border)" }}>
                        <div className="w-4 h-4 border-2 rounded-full animate-spin"
                          style={{ borderColor: "var(--border)", borderTopColor: "var(--uol-navy)" }} />
                        <span className="text-xs font-medium" style={{ color: "var(--muted-foreground)" }}>
                          Generating comparison summary…
                        </span>
                      </div>
                      {[1, 2, 3].map((i) => <SkeletonSection key={i} />)}
                    </div>
                  )}

                  {/* Comparison results */}
                  {(screen === "complete" || screen === "limited") && comparisonData && (
                    <div className="space-y-3">
                      {screen === "limited" && (
                        <div className="flex items-start gap-2 p-3 rounded-sm border text-xs mb-2"
                          style={{ borderColor: "#FCD34D", background: "#FFFBEB", color: "#92400E" }}>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mt-0.5 flex-shrink-0">
                            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                            <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
                          </svg>
                          <span>
                            <strong>Limited evidence:</strong> Teaching Quality data for {competitor} could not be fully verified. NSS scores are estimated from partial sources; treat with caution.
                          </span>
                        </div>
                      )}

                      {filteredSections.map((section) => (
                        <ComparisonSectionCard
                          key={section.priority}
                          section={section}
                          competitor={competitor}
                          onCitationClick={(id) => {
                            const c = filteredCitations.find((x) => x.id === id);
                            if (c) setActiveCitation(c);
                          }}
                        />
                      ))}

                      {/* Overall Recommendation */}
                      {comparisonData.recommendation && (
                        <div className="border rounded-sm overflow-hidden mt-2"
                          style={{ borderColor: "var(--uol-navy)", borderWidth: "1px" }}>
                          <div className="px-4 py-2.5 border-b"
                            style={{ borderColor: "var(--uol-navy)", background: "rgba(0,48,135,0.05)" }}>
                            <h3 className="font-serif font-semibold text-sm" style={{ color: "var(--uol-navy)" }}>
                              Overall Recommendation
                            </h3>
                          </div>
                          <div className="px-4 py-3">
                            <div className="flex items-start justify-between gap-3 mb-2">
                              <div>
                                <p className="font-semibold text-sm" style={{ color: "var(--foreground)" }}>
                                  {comparisonData.recommendation.university}
                                </p>
                                <p className="text-xs mt-0.5 leading-relaxed" style={{ color: "var(--foreground)" }}>
                                  {comparisonData.recommendation.explanation}
                                </p>
                              </div>
                              <div className="flex-shrink-0 text-right">
                                <div className="text-xs font-semibold px-2 py-1 rounded-sm"
                                  style={{ background: "rgba(0,48,135,0.08)", color: "var(--uol-navy)" }}>
                                  {comparisonData.recommendation.prioritiesSupported}/{filteredSections.length} priorities
                                </div>
                                <div className="text-xs mt-1" style={{ color: "var(--muted-foreground)" }}>
                                  Confidence: {comparisonData.recommendation.confidence}
                                </div>
                              </div>
                            </div>
                            {comparisonData.recommendation.note && (
                              <p className="text-xs italic pt-2 border-t" style={{ borderColor: "var(--border)", color: "var(--muted-foreground)" }}>
                                {comparisonData.recommendation.note}
                              </p>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* ── Right Panel: Citations ────────────────────────── */}
              <div className="citations-col border rounded-sm overflow-hidden" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
                <div className="px-4 py-3 border-b" style={{ borderColor: "var(--border)", background: "var(--muted)" }}>
                  <h2 className="font-serif font-semibold text-sm" style={{ color: "var(--foreground)" }}>
                    Citations
                  </h2>
                </div>

                <div className="px-4 py-4">
                  {filteredCitations.length === 0 ? (
                    <p className="text-xs text-center py-8" style={{ color: "var(--muted-foreground)" }}>
                      Citations will appear after comparison.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {filteredCitations.map((c) => (
                        <div key={c.id} className="border rounded-sm overflow-hidden" style={{ borderColor: "var(--border)" }}>
                          <div className="px-3 py-2 border-b flex items-center justify-between"
                            style={{ borderColor: "var(--border)", background: "var(--muted)" }}>
                            <div className="flex items-center gap-1.5">
                              <span className="text-xs font-mono font-semibold"
                                style={{ color: "var(--uol-navy)" }}>
                                [{c.id}]
                              </span>
                              <span className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                                {c.category}
                              </span>
                            </div>
                          </div>
                          <div className="px-3 py-2">
                            <p className="text-xs font-medium mb-0.5" style={{ color: "var(--foreground)" }}>
                              {c.university}
                            </p>
                            <p className="text-xs italic leading-relaxed mb-2" style={{ color: "var(--muted-foreground)" }}>
                              "{c.snippet}"
                            </p>
                            <button
                              onClick={() => setActiveCitation(c)}
                              className="inline-flex items-center gap-1 text-xs font-medium underline underline-offset-2 hover:no-underline"
                              style={{ color: "var(--uol-navy)" }}
                              aria-label={`Open citation ${c.id} detail`}
                            >
                              Open source page
                              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
                                <polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

            </div>
      </main>

      {/* Citation modal */}
      {activeCitation && (
        <CitationModal
          citation={activeCitation}
          onClose={() => setActiveCitation(null)}
        />
      )}
    </div>
  );
}
