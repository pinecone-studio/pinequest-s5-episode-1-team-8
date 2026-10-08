"use client";

import { useEffect, useState, type MouseEvent, type ReactNode } from "react";

/** Утсан дээр (md-ээс нарийн) цэсийг ☰ товчоор нээж хаана. Компьютер дээр үргэлж харагдана.
 *  header — лого (үргэлж харагдана), children — цэс, хэрэглэгчийн карт */
export function MobileMenu({ header, children }: { header: ReactNode; children: ReactNode }) {
  const [open, setOpen] = useState(false);

  // Escape товчоор цэсийг хаах логик
  useEffect(() => {
    if (!open) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  // Цэсний холбоос дарахад утсан дээр цэс хаагдана (шинэ хуудас харагдана)
  function closeOnLink(e: MouseEvent) {
    if ((e.target as HTMLElement).closest("a")) setOpen(false);
  }

  return (
    <>
      <div className="flex items-center justify-between gap-3 px-3 pb-[30px] max-md:pb-0">
        {header}
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls="sidebar-menu"
          aria-label={open ? "Цэс хаах" : "Цэс нээх"}
          className="grid size-10 shrink-0 cursor-pointer place-items-center rounded-[10px] border-[1.5px] border-line-2 text-fg hover:border-brand md:hidden"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" className="size-5" aria-hidden>
            {open ? <path d="M6 6l12 12M18 6 6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
        </button>
      </div>
      <div id="sidebar-menu" onClickCapture={closeOnLink} className={`flex flex-1 flex-col max-md:mt-4 ${open ? "" : "max-md:hidden"}`}>
        {children}
      </div>
    </>
  );
}