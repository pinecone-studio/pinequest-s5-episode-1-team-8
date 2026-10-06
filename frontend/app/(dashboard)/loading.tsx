// Хуудас солигдох үед (backend-ээс өгөгдөл уншиж байх зуур): sidebar хэвээр, агуулгын оронд анивчих хүрээ
export default function Loading() {
  return (
    <div role="status" aria-busy="true" className="animate-pulse">
      <span className="sr-only">Ачаалж байна…</span>
      <div className="mb-[34px] border-b border-line pb-[34px]">
        <div className="mb-3 h-4 w-48 rounded bg-panel-2" />
        <div className="h-11 w-72 max-w-full rounded-lg bg-panel-2" />
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3.5">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="h-28 rounded-[14px] bg-panel" />
        ))}
      </div>
      <div className="mt-[34px] h-64 rounded-[14px] bg-panel" />
    </div>
  );
}
