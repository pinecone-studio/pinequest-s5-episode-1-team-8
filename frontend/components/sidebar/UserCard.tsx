import { ROLE_LABEL, type User } from "@/lib/types";
import { LogoutButton } from "./LogoutButton";

export function UserCard({ user }: { user: User }) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-panel px-3.5 py-3">
      <div className="grid size-[38px] shrink-0 place-items-center rounded-full border-[1.5px] border-line-2 text-[13px] font-bold">
        {user.email.slice(0, 2).toUpperCase()}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-bold" title={user.email}>
          {user.email}
        </div>
        <div className="font-mono text-xs font-medium text-brand">{ROLE_LABEL[user.role]}</div>
      </div>
      <LogoutButton />
    </div>
  );
}
