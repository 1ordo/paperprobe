"use client";

import { useState } from "react";
import type { StandardRating, CosminStandard, Rating } from "@/types";
import { RATING_COLORS, RATING_LABELS } from "@/types";
import { updateRating } from "@/lib/api";
import { Check, Loader2 } from "lucide-react";

interface RatingEditorProps {
  rating: StandardRating;
  standard: CosminStandard;
  onSave: () => void;
}

const RATINGS: Rating[] = ["very_good", "adequate", "doubtful", "inadequate", "na"];
const REVIEWER_LABELS = {
  reviewer1: "Reviewer 1",
  reviewer2: "Reviewer 2",
  final: "Consensus",
} as const;

export function RatingEditor({ rating, standard, onSave }: RatingEditorProps) {
  const [reviewer, setReviewer] = useState<"reviewer1" | "reviewer2" | "final">("reviewer1");
  const [selectedRating, setSelectedRating] = useState<Rating | null>(
    rating[`${reviewer}_rating` as keyof StandardRating] as Rating | null
  );
  const [notes, setNotes] = useState(
    (rating[`${reviewer}_notes` as keyof StandardRating] as string) || ""
  );
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const payload: any = {};
      payload[`${reviewer}_rating`] = selectedRating;
      payload[`${reviewer}_notes`] = notes || null;
      await updateRating(rating.id, payload);
      onSave();
    } catch (e) {
      console.error("Save failed:", e);
    } finally {
      setSaving(false);
    }
  }

  function handleReviewerChange(r: "reviewer1" | "reviewer2" | "final") {
    setReviewer(r);
    setSelectedRating(rating[`${r}_rating` as keyof StandardRating] as Rating | null);
    setNotes((rating[`${r}_notes` as keyof StandardRating] as string) || "");
  }

  const availableRatings = standard.na_allowed ? RATINGS : RATINGS.filter((r) => r !== "na");

  const criteriaItems = [
    { label: "Very Good", color: RATING_COLORS.very_good, text: standard.rating_very_good },
    { label: "Adequate", color: RATING_COLORS.adequate, text: standard.rating_adequate },
    { label: "Doubtful", color: RATING_COLORS.doubtful, text: standard.rating_doubtful },
    { label: "Inadequate", color: RATING_COLORS.inadequate, text: standard.rating_inadequate },
  ];

  return (
    <div className="mt-3 pt-3 border-t border-border space-y-3 animate-fade-in">
      {/* Reviewer tabs */}
      <div className="flex gap-1 bg-surface-3 rounded-lg p-0.5">
        {(["reviewer1", "reviewer2", "final"] as const).map((r) => (
          <button
            key={r}
            onClick={() => handleReviewerChange(r)}
            className={`flex-1 text-[11px] px-3 py-1.5 rounded-md font-medium transition-all ${
              reviewer === r
                ? "bg-accent text-white shadow-sm"
                : "text-text-tertiary hover:text-text-secondary"
            }`}
          >
            {REVIEWER_LABELS[r]}
          </button>
        ))}
      </div>

      {/* Rating criteria reference */}
      <div className="bg-surface-0 rounded-lg border border-border p-2.5 space-y-1.5">
        <div className="text-[10px] font-mono text-text-tertiary uppercase tracking-wider mb-1">
          Rating Criteria
        </div>
        {criteriaItems.map((item) => (
          <div key={item.label} className="flex gap-2 text-xs">
            <span
              className="shrink-0 w-1 rounded-full mt-1"
              style={{ backgroundColor: item.color, height: "calc(100% - 4px)" }}
            />
            <div>
              <span className="font-medium text-text-secondary" style={{ color: item.color }}>
                {item.label}:
              </span>{" "}
              <span className="text-text-tertiary">{item.text}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Rating buttons */}
      <div className="flex gap-1.5">
        {availableRatings.map((r) => {
          const isSelected = selectedRating === r;
          const color = RATING_COLORS[r];
          return (
            <button
              key={r}
              onClick={() => setSelectedRating(r)}
              className={`flex-1 text-[11px] py-2 rounded-lg font-semibold uppercase tracking-wide transition-all border-2 ${
                isSelected
                  ? "text-white scale-[1.02]"
                  : "hover:scale-[1.01]"
              }`}
              style={{
                backgroundColor: isSelected ? color : `${color}15`,
                borderColor: isSelected ? color : "transparent",
                color: isSelected ? (r === "na" ? "#0c0d10" : "white") : color,
              }}
            >
              {RATING_LABELS[r]}
            </button>
          );
        })}
      </div>

      {/* Notes */}
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Review notes (optional)..."
        className="w-full text-xs bg-surface-0 border border-border rounded-lg p-2.5 text-text-primary placeholder:text-text-tertiary focus:border-accent resize-none transition-colors"
        rows={2}
      />

      {/* Save */}
      <button
        onClick={handleSave}
        disabled={saving || !selectedRating}
        className="flex items-center justify-center gap-1.5 w-full text-xs bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:hover:bg-accent text-white py-2 rounded-lg font-medium transition-all"
      >
        {saving ? (
          <Loader2 className="w-3 h-3 animate-spin" />
        ) : (
          <Check className="w-3 h-3" />
        )}
        {saving ? "Saving..." : "Save Rating"}
      </button>
    </div>
  );
}
