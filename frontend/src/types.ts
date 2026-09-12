export type {
  Catalog, DocumentContent, DocumentType, RequisiteField, Template,
  ProcessRequest, ProcessResult, DownloadRequest, ErrorResponse,
} from './generated/api';

export interface DraftState {
  draft: string;
  docType: string;
  templateId: string;
  requisitesByType: Record<string, Record<string, string>>;
}
