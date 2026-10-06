/** Лого: ногоон хаалт + "AI РЕСЕПШН" */
export function Brand() {
  return (
    <span className="flex items-center gap-3">
      <svg viewBox="0 0 38 34" fill="none" stroke="currentColor" strokeWidth={5.5} strokeLinecap="round"
        strokeLinejoin="round" className="h-[34px] w-[38px] shrink-0 text-brand" aria-hidden>
        <path d="M13 4 L4 17 L13 30" />
        <path d="M25 4 L34 17 L25 30" />
      </svg>
      <b className="text-[15px] leading-[1.1] font-extrabold tracking-[.06em] text-fg">
        AI
        <br />
        РЕСЕПШН
      </b>
    </span>
  );
}
