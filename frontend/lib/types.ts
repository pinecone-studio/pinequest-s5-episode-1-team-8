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
};

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

// backend/routes/leads.py
export type LeadStatus = "new" | "contacted" | "done";

export type Lead = {
  id: number;
  call_uuid: string;
  created_at: number;
  name: string | null;
  phone: string | null; // баталгаажсан дугаар (AI таахгүй)
  phone_raw: string | null; // STT-ийн сонссон бичвэр
  caller: string | null; // Caller ID
  reason: "lead" | "handoff";
  question: string | null;
  status: LeadStatus;
  notes: string | null;
};

export const LEAD_STATUS: Record<LeadStatus, string> = { new: "Шинэ", contacted: "Холбогдсон", done: "Дууссан" };

export type KnowledgeFile = { name: string; size: number; mtime: number; editable: boolean };
export type KnowledgeResponse = { files: KnowledgeFile[] };

export type FaqItem = { id: string; questions: string[]; answer: string; topic?: string | null };
export type FaqData = { greeting: string; fillers: string[]; topics: Record<string, unknown>; faq: FaqItem[] };

export type VoiceData = {
  items: { kind: string; text: string; hash: string }[];
  settings: { lexicon: { word: string; say: string }[]; speed: number; pause_ms: number };
};

export type TrainingExample = { i: number; q: string; faq?: string; fact?: string; label?: string };
export type TrainingStatus = { model: Record<string, unknown> | null; seed: number; taught: TrainingExample[] };
export type TrainingChoice = { value: string; title: string };
export type TrainingAnswers = { faq: TrainingChoice[]; facts: TrainingChoice[]; special: TrainingChoice[] };

export type EnglishItem = { id: string | null; kind: "faq" | "knowledge"; mn: string; hash: string; en: string; questions: string[]; questions_en: string[] };
export type EnglishData = { enabled: boolean; items: EnglishItem[]; phrases: Record<string, string> };
