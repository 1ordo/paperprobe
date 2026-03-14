export type Rating = "very_good" | "adequate" | "doubtful" | "inadequate" | "na";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  paper_count: number;
  created_at: string;
  updated_at: string;
}

export interface Paper {
  id: string;
  project_id: string;
  title: string | null;
  authors: string | null;
  year: number | null;
  doi: string | null;
  filename: string;
  file_path: string;
  file_type: string;
  status: string;
  page_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface CosminStandard {
  id: number;
  standard_number: number;
  question_text: string;
  section_group: string | null;
  rating_very_good: string | null;
  rating_adequate: string | null;
  rating_doubtful: string | null;
  rating_inadequate: string | null;
  na_allowed: boolean;
  sort_order: number;
}

export interface CosminSubBox {
  id: number;
  sub_box_code: string;
  name: string;
  section_group: string | null;
  sort_order: number;
  standards: CosminStandard[];
}

export interface CosminBox {
  id: number;
  box_number: number;
  name: string;
  description: string | null;
  prerequisite: string | null;
  sub_boxes: CosminSubBox[];
}

export interface Evidence {
  id: string;
  evidence_text: string;
  page_number: number | null;
  char_start: number | null;
  char_end: number | null;
  source: string;
}

export interface StandardRating {
  id: string;
  standard_id: number;
  ai_rating: Rating | null;
  ai_confidence: number | null;
  ai_reasoning: string | null;
  reviewer1_rating: Rating | null;
  reviewer1_notes: string | null;
  reviewer2_rating: Rating | null;
  reviewer2_notes: string | null;
  final_rating: Rating | null;
  final_notes: string | null;
  is_skipped: boolean;
  evidence: Evidence[];
}

export interface BoxRating {
  id: string;
  box_id: number;
  sub_box_id: number | null;
  ai_worst_score: Rating | null;
  final_worst_score: Rating | null;
}

export interface Assessment {
  id: string;
  paper_id: string;
  status: string;
  relevant_boxes: Record<string, any> | null;
  standard_ratings: StandardRating[];
  box_ratings: BoxRating[];
  ai_started_at: string | null;
  ai_completed_at: string | null;
}

export interface BackgroundTask {
  id: string;
  paper_id: string | null;
  task_type: string;
  status: string;
  progress: number;
  error_message: string | null;
  created_at: string;
}

export const RATING_COLORS: Record<Rating, string> = {
  very_good: "#92D050",
  adequate: "#00B0F0",
  doubtful: "#FFC000",
  inadequate: "#FF0000",
  na: "#D9D9D9",
};

export const RATING_LABELS: Record<Rating, string> = {
  very_good: "Very Good",
  adequate: "Adequate",
  doubtful: "Doubtful",
  inadequate: "Inadequate",
  na: "N/A",
};
