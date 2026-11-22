export type ConsentPurpose = "data_processing";

export interface ConsentDocument {
  purpose: ConsentPurpose;
  version: string;
  title: string;
  paragraphs: string[];
  declaration: string;
  review_status: string;
}

export interface ConsentRecord {
  id: string;
  purpose: ConsentPurpose;
  version: string;
  accepted_by: string;
  accepted_at: string;
  revoked_at: string | null;
}

export interface ConsentStatus {
  purpose: ConsentPurpose;
  required_version: string;
  valid: boolean;
  current: ConsentRecord | null;
}
