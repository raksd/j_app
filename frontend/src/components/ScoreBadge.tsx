export function scoreClass(score: number): string {
  if (score >= 70) return "badge good";
  if (score >= 50) return "badge ok";
  return "badge poor";
}

export default function ScoreBadge({ score }: { score: number }) {
  return (
    <span className={scoreClass(score)} title="ATS score out of 100">
      {score.toFixed(0)}
    </span>
  );
}
