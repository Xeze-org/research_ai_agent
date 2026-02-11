import { useState, useEffect, useCallback } from "react";
import { researchApi } from "@/lib/api";
import type { Research, CreateResearchRequest } from "@/types";

export function useResearch() {
  const [items, setItems] = useState<Research[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const list = await researchApi.list();
      setItems(list);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const create = async (data: CreateResearchRequest): Promise<Research> => {
    setCreating(true);
    try {
      const doc = await researchApi.create(data);
      setItems((prev) => [doc, ...prev]);
      return doc;
    } finally {
      setCreating(false);
    }
  };

  const remove = async (id: string) => {
    await researchApi.remove(id);
    setItems((prev) => prev.filter((r) => r.id !== id));
  };

  return { items, loading, creating, create, remove, refetch: fetchList };
}
