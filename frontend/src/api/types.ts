export interface HealthResponse {
  status: string;
  device: string;
  checkpoint_loaded: boolean;
  classes: string[];
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
