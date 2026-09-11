export interface RequisiteField {
  id: string;
  label: string;
  required: boolean;
}

export interface DocumentType {
  id: string;
  name: string;
  description: string;
  title: string;
  fields: RequisiteField[];
  blocks: string[];
}

export interface Template {
  id: string;
  name: string;
  description: string;
  font: string;
  font_size: number;
}

export interface Catalog {
  doc_types: DocumentType[];
  templates: Template[];
  processor_mode: string;
}

export interface DocumentContent {
  doc_type: string;
  requisites: Record<string, string>;
  body: string[];
}

export interface ProcessResult {
  document: DocumentContent;
  missing_fields: RequisiteField[];
  changes: string[];
  warnings: string[];
  processor_mode: string;
}

export interface DraftState {
  draft: string;
  docType: string;
  templateId: string;
  requisitesByType: Record<string, Record<string, string>>;
}
