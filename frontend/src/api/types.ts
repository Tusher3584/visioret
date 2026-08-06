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
  model_version_label: string;
}
