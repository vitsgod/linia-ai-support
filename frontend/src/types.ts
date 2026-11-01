export type TicketInput = {
  name: string;
  subject: string;
  description: string;
};

export type Ticket = TicketInput & {
  id: number;
  status: 'Новая';
  created_at: string;
};

export type DiagnosticSource = { id: string; title: string; section: string; url: string; excerpt: string };
export type DiagnosticResult = {
  model: string | null;
  answer: string;
  mode: 'answer' | 'clarify';
  sources: DiagnosticSource[];
};

export type AreaCode = 'demo-north' | 'demo-center' | 'demo-south';
export type OutageResult = {
  area_code: AreaCode;
  area_name: string;
  status: 'active' | 'clear' | 'unknown';
  incident: { id: string; title: string } | null;
  message: string;
  checked_at: string;
  demo: true;
};

export type OutageAssistantResult = {
  mode: 'tool_result' | 'clarify';
  answer: string;
  model: string | null;
  tool_name: 'check_outage_status' | null;
  tool_result: OutageResult | null;
};

export type TicketDraft = Pick<TicketInput, 'subject' | 'description'>;
export type DraftResult = {
  mode: 'draft' | 'clarify';
  draft: TicketDraft | null;
  model: string | null;
  saved: false;
  message: string;
};

export type HistoryRun = {
  id: string;
  kind: 'diagnostics' | 'outage' | 'outage_assistant' | 'ticket_draft';
  status: 'started' | 'completed' | 'failed';
  request_data: Record<string, unknown>;
  response_data: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
};
