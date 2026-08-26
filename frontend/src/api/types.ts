export interface User {
  id: number;
  name: string;
  email: string;
  role: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface HealthResponse {
  status: string;
  device: string;
  checkpoint_loaded: boolean;
  classes: string[];
  /** Whether the out-of-distribution gate is loaded and screening uploads. */
  ood_gate_active: boolean;
}

export interface PredictionResponse {
  scan_id: number;
  predicted_class: string;
  confidence: number;
  probabilities: Record<string, number>;
  original_image_url: string;
  gradcam_overlay_url: string;
  explanation: string;
}

export interface ScanSummary {
  scan_id: number;
  uploaded_at: string;
  predicted_class: string;
  confidence: number;
  original_image_url: string;
  owner_name: string | null;
}

export interface Feedback {
  is_correct: boolean;
  corrected_class: string | null;
  comment: string | null;
  reviewed_at: string;
  reviewer_name: string | null;
}

export interface FeedbackCreate {
  is_correct: boolean;
  corrected_class?: string | null;
  comment?: string | null;
}

export interface ScanDetail {
  scan_id: number;
  uploaded_at: string;
  predicted_class: string;
  confidence: number;
  probabilities: Record<string, number>;
  original_image_url: string;
  gradcam_overlay_url: string;
  explanation: string;
  model_version_label: string;
  feedback: Feedback | null;
  owner_name: string | null;
  /** Whether the current caller may record a correction on this scan. */
  can_review: boolean;
}

export interface PerClassMetric {
  precision: number;
  recall: number;
  f1_score: number;
  support: number;
}

export interface ConfusionMatrix {
  labels: string[];
  matrix: number[][];
}

export interface EvaluationMetric {
  dataset_split: string;
  dataset_split_label: string;
  accuracy: number;
  precision_macro: number;
  recall_macro: number;
  f1_macro: number;
  per_class_metrics: Record<string, PerClassMetric>;
  confusion_matrix: ConfusionMatrix;
  evaluated_at: string;
  model_version_label: string;
}
