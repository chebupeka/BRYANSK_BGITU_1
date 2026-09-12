// Contracts of the backend. The union covers every branch of the project: fields that only
// exist on an unmerged branch are optional here, so one build talks to any of them.

export type Alignment = 'left' | 'center' | 'right' | 'justify';

/** Where a requisite goes on the page. Only feature/docx-configs sends it. */
export type Placement =
  | 'labeled'
  | 'letterhead'
  | 'addressee'
  | 'registration'
  | 'headline'
  | 'salutation'
  | 'paragraph'
  | 'signature'
  | 'executor';

export interface RequisiteField {
  id: string;
  label: string;
  required: boolean;
  /** feature/docx-configs: position of the requisite in the DOCX. */
  placement?: Placement;
  /** feature/docx-configs: static text before the value, e.g. «№ ». */
  prefix?: string;
  /** feature/ollama-text-processor: the processor writes this field itself. */
  summary?: boolean;
}

export interface DocumentType {
  id: string;
  name: string;
  description: string;
  title: string;
  /** feature/docx-configs: whether «СЛУЖЕБНАЯ ЗАПИСКА» is printed on the page. */
  show_title?: boolean;
  fields: RequisiteField[];
  blocks: string[];
}

export interface Template {
  id: string;
  name: string;
  description: string;
  font: string;
  font_size: number;
  margins_mm?: { top: number; right: number; bottom: number; left: number };
  line_spacing?: number;
  paragraph_space_after_pt?: number;
  first_line_indent_mm?: number;
  title_alignment?: Alignment;
  recipient_alignment?: Alignment;
  body_alignment?: Alignment;
  /** feature/docx-configs adds the block below. */
  signature_alignment?: Alignment;
  recipient_layout?: 'block' | 'table';
  header?: 'none' | 'organization';
  footer?: 'none' | 'page_number' | 'title_and_date';
  header_footer_font_size?: number;
  letterhead_alignment?: Alignment;
  headline_alignment?: Alignment;
  headline_bold?: boolean;
  addressee_width_mm?: number;
  small_font_size?: number;
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

/** feat/role-1-backend-integration: GET /api/ready. Older backends answer /api/health only. */
export interface ServiceStatus {
  status: string;
  processor_mode: string;
  checks?: Record<string, boolean>;
}

/** feat/role-1-backend-integration: the single error body. */
export interface ErrorIssue {
  field: string;
  message: string;
  type: string;
}

export interface ErrorInfo {
  code: string;
  message: string;
  retryable: boolean;
  request_id: string;
  details: ErrorIssue[];
}

/** What the API layer hands to the interface for every failure. */
export interface ApiFailure {
  message: string;
  hint: string;
  retryable: boolean;
  code: string;
  requestId: string;
  issues: ErrorIssue[];
}

export interface DraftState {
  draft: string;
  docType: string;
  templateId: string;
  requisitesByType: Record<string, Record<string, string>>;
}

export type ThemeName = 'dark' | 'light';
