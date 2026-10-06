export type Role = "admin" | "owner";

// backend/app.py · public_user()
export type User = {
  email: string;
  role: Role;
  tenant: string;
  expires: number; // session дуусах хугацаа (unix секунд)
};

export const ROLE_LABEL: Record<Role, string> = { admin: "ADMIN", owner: "ЭЗЭМШИГЧ" };
