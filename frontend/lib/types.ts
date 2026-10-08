export type Role = "admin" | "owner";

// backend/app.py · public_user()
export type Plan = "trial" | "active" | "suspended";

export type User = {
  email: string;
  role: Role;
  tenant: string; // байгууллагын slug
  tenant_name: string;
  extension: string | null; // дотуур дугаар (Zoiper-оос залгах)
  plan: Plan;
  expires: number; // session дуусах хугацаа (unix секунд)
  own_tenant?: boolean; // false: admin өөр байгууллагыг сольж харж байна
};

export const PLAN_LABEL: Record<Plan, string> = { trial: "Туршилт", active: "Идэвхтэй", suspended: "Түдгэлзсэн" };

export const ROLE_LABEL: Record<Role, string> = { admin: "ADMIN", owner: "ЭЗЭМШИГЧ" };

// backend/routes/org.py · org_info()
export type Org = {
  name: string;
  phone: string;
  email: string;
  address: string;
  hours: string;
  slug: string;
  extension: string | null;
  plan: Plan;
  documents: number;
  users: { id: number; email: string; role: Role; created_at: number }[];
};

// backend/routes/settings.py · get_settings()
export type Settings = {
  telegram_token_set: boolean;
  telegram_token_hint: string;
  telegram_bot: string | null;
  telegram_chat_id: number | string | null;
  telegram_chat_title: string | null;
  auto_build: boolean; // нэмэлт: мэдээлэл өөрчлөгдөхөд автоматаар бэлдэх
};

// backend/routes/knowledge.py · build_estimate — бэлдэхэд ElevenLabs-аар шинээр үүсэх
export type BuildEstimate = { total: number; recorded: number; cached: number; new: number; chars: number; texts: string[] };

// backend/routes/calls.py
export type Call = {
  uuid: string;
  caller: string | null;
  started_at: number;
  ended_at: number | null;
  duration: number | null;
  questions: number;
  unanswered: number;
};

export type Message = {
  id: number;
  call_uuid: string;
  ts: number;
  role: "user" | "assistant";
  text: string;
  route: string | null;
  score: number | null;
  stt_sec: number | null;
  latency: number | null;
};

export type CallDetail = { call: Omit<Call, "questions" | "unanswered">; messages: Message[] };

// backend/routes/stats.py
export type Stats = {
  calls: number;
  questions: number;
  answered: number;
  unanswered: number;
  routes: Record<string, number>;
  avg_latency: number | null;
  avg_stt: number | null;
  new_leads: number;
  days: { date: string; calls: number }[]; // сүүлийн 5 өдөр, хуучнаас шинэ рүү
};

// backend/routes/unanswered.py
export type Unanswered = {
  id: number;
  call_uuid: string;
  ts: number;
  question: string;
  route: string;
  score: number | null;
};

export type UnansweredSuggestion = {
  kind: "faq" | "fact";
  id?: string;
  text: string;
  score: number;
  value: string;
};

export type UnansweredReviewNow = {
  q: string;
  text: string;
  fixed?: string | null;
  noise?: boolean;
  route?: string | null;
  reply?: string;
  faq_id?: string | null;
  suggest?: UnansweredSuggestion[];
};

export type UnansweredReviewItem = {
  q: string;
  ts: number;
  call_uuid: string;
  route: string;
  now?: UnansweredReviewNow;
};

export type UnansweredReview = {
  items: UnansweredReviewItem[];
  live: boolean;
  pending: string[];
};

// backend/routes/leads.py
export type LeadStatus = "new" | "contacted" | "done" | "canceled";

export type Lead = {
  id: number;
  call_uuid: string;
  created_at: number;
  name: string | null;
  phone: string | null; // баталгаажсан дугаар (AI таахгүй)
  phone_raw: string | null; // STT-ийн сонссон бичвэр
  caller: string | null; // Caller ID
  course: string | null; // бүртгүүлсэн хөтөлбөр / эвент
  reason: "lead" | "handoff";
  question: string | null;
  status: LeadStatus;
  notes: string | null;
};

export const LEAD_STATUS: Record<LeadStatus, string> = { new: "Шинэ", contacted: "Холбогдсон", done: "Дууссан", canceled: "Цуцалсан" };

export type KnowledgeFile = { name: string; size: number; mtime: number; editable: boolean };
export type KnowledgeFact = { text: string; source: string | null; hash: string; has_audio: boolean; recorded: boolean };
export type KnowledgeResponse = { files: KnowledgeFile[]; facts: KnowledgeFact[]; indexed_at?: number | string | null };
export type JobStatus = {
  state: "idle" | "queued" | "running" | "done" | "error";
  task?: "build" | "train" | "english" | "regen" | "answers";
  running: boolean;
  ahead: number;
  log: string[];
  code?: number | null;
  finished?: number | null;
};
export type BuildStatus = JobStatus;

export type FaqItem = {
  id: string;
  questions: string[];
  answer: string;
  topic?: string | null;
  auto?: boolean;
  source?: string | null;
  created_at?: number | null;
};
export type FaqData = { greeting: string; fillers: string[]; topics: Record<string, unknown>; faq: FaqItem[] };

export type VoiceItem = {
  kind: string;
  text: string;
  hash: string;
  recorded: boolean;
  flags: string[];
  cer?: number | null;
  hyp?: string | null;
  seed: number;
  plays: number;
};
export type VoiceData = {
  items: VoiceItem[];
  qa_at?: number | null;
  voice: { name: string | null; id: string | null; model: string; has_key: boolean }; // ElevenLabs (анхдагч Уянга)
  settings: { lexicon: { word: string; say: string }[]; speed: number; pause_ms: number };
};

// backend/routes/eleven.py — ElevenLabs хоолой сонгох (admin)
export type ElevenVoice = { id: string; name: string; info: string; library?: boolean }; // name: монгол сангийн хоолой "🇲🇳 ..."
export type ElevenItem = { kind: string; text: string; hash: string; recorded: boolean; sample: boolean; eleven: string[]; choice: string };
export type ElevenJob = { running: boolean; done: number; total: number; chars: number; error: string | null };
export type ElevenStatus = {
  has_key: boolean;
  model: string;
  voice: string | null; // байгууллагын одоогийн хоолой
  job: ElevenJob;
  voices: ElevenVoice[];
  items: ElevenItem[];
  error?: string | null;
  oron?: boolean;
};

export type TrainingExample = { i: number; q: string; faq?: string; fact?: string; label?: string };
export type TrainingModel = {
  trained_at?: number | null;
  examples?: number | null;
  rows?: number | null;
  cv_acc?: number | null;
  eval?: { selector: [number, number]; rules: [number, number] } | null;
  enabled?: boolean | null;
  warnings?: string[] | null;
  answers?: number | null;
  labels?: string[] | null;
};
export type TrainingStatus = JobStatus & {
  model: TrainingModel | null;
  seed: number;
  auto: number;
  taught: TrainingExample[];
};
export type TrainingChoice = { value: string; title: string };
export type TrainingAnswers = { faq: TrainingChoice[]; facts: TrainingChoice[]; special: TrainingChoice[] };

// backend/english_core.py (SIM-TRUNK english.py · items)
export type EnglishItem = {
  id: string | null;
  kind: "faq" | "fact";
  mn: string;
  hash: string;
  en: string | null; // орчуулаагүй бол null
  section?: string | null;
  mn_questions: string[];
  standard: boolean;
  questions_en: string[];
  built: boolean;
  flags: string[];
  hyp?: string | null;
};
export type EnglishPhrases = {
  greeting_suffix: string;
  repeat: string;
  error: string;
  mongolian_only: string;
  holds: string[];
  lead: Record<string, string>;
};
export type EnglishData = {
  enabled: boolean;
  items: EnglishItem[];
  phrases: EnglishPhrases;
  stale: { hash: string; mn: string; en: string }[];
  built: boolean;
  built_at?: number | null;
};

// backend/routes/status.py — sidebar, самбар, Тохируулах (10с тутам)
export type Status = {
  ai_server: boolean;
  sip: boolean;
  documents: number;
  facts: number;
  faq: number;
  indexed_at?: string | null;
  ready: boolean; // мэдээлэл + FAQ-ийн индекс бэлдсэн (SIM-TRUNK шиг)
  recorded?: number; // өөрийн хоолойгоор бичсэн өгүүлбэр
  voice_total?: number; // тоглогдох бүх өгүүлбэр
  build_running: boolean;
  selector: { enabled: boolean | null; eval: { selector?: [number, number]; rules?: [number, number] } | null } | null;
  new_leads: number;
  unanswered: number;
};

// backend/routes/admin.py · list_tenants()
export type AdminTenant = {
  slug: string;
  name: string;
  address?: string | null;
  email?: string | null;
  extension: string | null;
  plan: Plan;
  created_at: number | null;
  calls: number;
  ready: boolean;
  users: string[];
  job: string; // idle | queued | running | done | error
};

// backend/routes/reminders.py — AI-аас гарах сануулгын дуудлага
export type ReminderStatus = "scheduled" | "calling" | "confirmed" | "declined" | "unconfirmed" | "no_answer" | "busy" | "failed" | "canceled";
export type Reminder = {
  lead_id: number;
  appointment: string; // "2026-10-15T10:00" (Улаанбаатар)
  call_at: number;
  status: ReminderStatus;
  attempts: number;
  text: string;
  last_outcome?: string;
  history: { ts: number; outcome: string; pressed: string[]; detail: string }[];
  new_chars?: number;
};
export type RemindersData = {
  items: Record<string, Reminder>;
  template: string;
  default_template: string;
  dialer: { mode: "off" | "sip" | "mac" };
  hours: [number, number];
};
export type OutboundConfig = {
  mode: "off" | "sip" | "mac";
  host?: string;
  port?: number;
  user?: string;
  prefix?: string;
  local_ip?: string;
  ring_timeout?: number;
  password_set: boolean;
};

export const REMINDER_STATUS: Record<ReminderStatus, [string, "ok" | "warn" | "bad" | "gray"]> = {
  scheduled: ["Товлосон", "gray"], calling: ["Залгаж байна…", "warn"], confirmed: ["✅ Баталгаажсан", "ok"],
  declined: ["❌ Цуцалсан", "bad"], unconfirmed: ["Хариу өгөөгүй", "warn"], no_answer: ["📵 Утсаа аваагүй", "warn"],
  busy: ["📵 Завгүй", "warn"], failed: ["⚠️ Залгаж чадсангүй", "bad"], canceled: ["❌ Утсаар цуцалсан", "bad"],
};

// backend/routes/people.py — хувийн RAG: бүртгэлийн код, утасны AI-ийн өөрчлөлт
export type LeadChange = {
  id: number;
  lead_id: number;
  ts: number;
  field: "phone" | "appointment" | "status" | "attendance";
  old: string | null;
  new: string | null;
  source: "ai" | "staff" | "web" | "call"; // ai — залгагч өөрөө, staff — ажилтан, call — AI сануулгын дуудлага
  call_uuid: string | null;
};
export type PeopleData = {
  codes: Record<string, string>;
  changes: LeadChange[];
  booking: { days: number[]; start: number; end: number; capacity: number; horizon: number };
  staff_pin: string;
  events: EventItem[];
};
export type EventItem = { name: string; at: string }; // "2026-10-18T10:00" (Улаанбаатар)

// backend/routes/assistant.py — AI туслах (хувийн RAG)
export type PersonDoc = { field: string; text: string; vector: boolean };
export type Person = {
  id: number;
  name: string | null;
  phone: string | null;
  course: string | null;
  status: LeadStatus;
  code: string;
  appointment: string | null;
  docs: PersonDoc[];
};
export type RagHit = { kind: string; key: string; text: string; score: number };
export type AssistantReply = {
  session: string;
  replies: string[];
  state: string;
  trace: RagHit[];
  person: Person | null;
  changes: LeadChange[];
  dtmf_len: number;
  staff: boolean;
};

// backend/routes/database.py — өгөгдлийн сан (зөвхөн унших)
export type DbTable = { name: string; rows: number; columns: string[]; about: string };
export type DbOverview = { file: string; bytes: number; tables: DbTable[] };
export type DbVector = { dims: number; preview: number[] };
export type DbCell = string | number | null | DbVector;
export type DataInfo = {
  location: { server: string; file: string; bytes: number; separate: boolean };
  stored: { what: string; detail: string; count: number }[];
  not_stored: string[];
  external: { to: string; what: string; active: boolean }[];
  local: string[];
  access: string[];
  retention: string;
  backup: { count: number; keep_days: number; last: number | null; last_bytes: number };
};
export type DbRows = { table: string; columns: string[]; rows: DbCell[][]; total: number; offset: number; page: number; about: string };

// backend/routes/rag.py — нэг өгөгдлийн сан (receptionist.db): байгууллагын RAG + хувийн RAG + дуудлага
export type RagStats = {
  facts: number;
  chunks: number;
  faq_questions: number;
  person_docs: number;
  people: number;
  calls: number;
  messages: number;
  leads: number;
  changes: number;
  embed_model: string | null;
  dim: number;
  built_at: number | null;
  db_bytes: number;
};

// backend/routes/report.py — долоо хоногийн тайлан
export type WeeklyReport = {
  days: number;
  calls: number;
  questions: number;
  answered: number;
  unanswered: number;
  rate: number | null;
  topics: [string, number][];
  unanswered_top: { q: string; count: number }[];
  new_leads: number;
  reminders: Record<string, number>;
  peak_hour: number | null;
  text: string;
  enabled: boolean;
  telegram: boolean;
  last_sent?: number | null;
};
