type Props = {
  confidence: number | null;
};

export function ConfidenceMeter({ confidence }: Props) {
  const value = confidence ?? 0;

  const color =
    value > 0.8
      ? "text-green-600"
      : value > 0.5
        ? "text-yellow-600"
        : "text-red-600";

  return (
    <div className="rounded border p-4">
      <h2 className="mb-2 font-semibold">Confidence</h2>
      <p className={`text-lg font-bold ${color}`}>
        {(value * 100).toFixed(1)}%
      </p>
    </div>
  );
}
