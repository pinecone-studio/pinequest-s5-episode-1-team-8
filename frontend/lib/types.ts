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
