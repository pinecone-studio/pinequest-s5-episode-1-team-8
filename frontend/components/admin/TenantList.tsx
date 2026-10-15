"use client";

import { useState, useMemo } from "react";
import { TenantRow } from "@/components/admin/TenantRow";
import { EmptyState } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { Table } from "@/components/ui/Table";
import type { AdminTenant } from "@/lib/types";

interface TenantListProps {
  tenants: AdminTenant[];
}

export function TenantList({ tenants }: TenantListProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  // Хайлт болон төлөвийн шүүлтүүрийн логик
  const filteredTenants = useMemo(() => {
    const query = searchQuery.toLowerCase().trim();

    return tenants.filter((t) => {
      // Төлөвийн шүүлтүүр
      if (statusFilter !== "ALL") {
        // AdminTenant-д status талбар байхгүй: ready (бэлэн эсэх), job (idle|queued|running|done|error)
        if (statusFilter === "READY" && !t.ready) return false;
        if (statusFilter === "NOT_READY" && t.ready) return false;
        if (statusFilter === "ACTIVE" && t.job !== "running" && t.job !== "queued") return false;
        if (statusFilter === "ERROR" && t.job !== "error") return false;
      }

      if (!query) return true;

      const nameMatch = t.name?.toLowerCase().includes(query) ?? false;
      const slugMatch = t.slug?.toLowerCase().includes(query) ?? false;
      const orgEmailMatch = t.email?.toLowerCase().includes(query) ?? false;
      const userEmailMatch = t.users.some((u) => u.toLowerCase().includes(query));

      return nameMatch || slugMatch || orgEmailMatch || userEmailMatch;
    });
  }, [tenants, searchQuery, statusFilter]);

  const clearFilters = () => {
    setSearchQuery("");
    setStatusFilter("ALL");
  };

  return (
    <div className="space-y-4">
      {/* Хайлт болон шүүлтүүр хэсэг */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <input
          type="text"
          placeholder="Нэр, slug, байгууллага эсвэл хэрэглэгчийн и-мэйлээр хайх..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full sm:w-[320px] rounded-[10px] border border-line-2 bg-bg px-3 py-2 text-sm outline-none focus:border-brand"
        />

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full sm:w-auto rounded-[10px] border border-line-2 bg-bg px-3 py-2 text-sm outline-none focus:border-brand"
          >
            <option value="ALL">Бүгд</option>
            <option value="READY">Бэлэн</option>
            <option value="NOT_READY">Бэлдээгүй</option>
            <option value="ACTIVE">Ажил ажиллаж байгаа</option>
            <option value="ERROR">Алдаатай</option>
          </select>

          {(searchQuery || statusFilter !== "ALL") && (
            <button
              onClick={clearFilters}
              className="text-sm text-brand hover:underline whitespace-nowrap"
            >
              Цэвэрлэх
            </button>
          )}
        </div>
      </div>

      {/* Харагдаж буй болон нийт тоо */}
      <div className="text-sm text-muted">
        Харагдаж буй {filteredTenants.length} / Нийт {tenants.length} байгууллага
      </div>

      {/* Хүснэгт эсвэл Empty state */}
      <Card>
        {filteredTenants.length ? (
          <Table head={["Байгууллага", "Дугаар", "Хэрэглэгч", "Дуудлага", "Төлөв", "Эрх", ""]}>
            {filteredTenants.map((t) => (
              <TenantRow key={t.slug} t={t} />
            ))}
          </Table>
        ) : tenants.length === 0 ? (
          <EmptyState>Байгууллага алга</EmptyState>
        ) : (
          <div className="py-8 text-center text-sm text-muted">
            Тохирох байгууллага олдсонгүй
          </div>
        )}
      </Card>
    </div>
  );
}