/**
 * useWarehouseDashboard Hook
 * Fetches warehouse-specific data for the operations dashboard
 */

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

export interface ResourceData {
  resource_type: string;
  available_count: number;
  total_count: number;
  assigned_count?: number;
  in_transit_count?: number;
}

export interface TruckState {
  truck_id: string;
  state: string;
  state_timestamp: string;
  gate_id?: string;
  facility_id: string;
}

export interface ArrivingTruck {
  truck_id: string;
  shipment_id: string;
  eta_ts: string;
  status: string;
}

export interface SlotData {
  slot_id: string;
  facility_id: string;
  gate_id: string;
  slot_start_ts: string;
  slot_end_ts: string;
  status: string;
  shipment_id?: string;
}

export interface Escalation {
  escalation_id: string;
  shipment_id?: string;
  driver_id?: string;
  exception_type?: string;
  urgency: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  reason: string;
  reported_at: string;
  status?: string;
}

export interface WarehouseDashboardData {
  resources: ResourceData[];
  trucksInYard: TruckState[];
  arrivingTrucks: ArrivingTruck[];
  slots: SlotData[];
  escalations: Escalation[];
  loading: boolean;
  error: string | null;
}

export function useWarehouseDashboard(
  warehouseId: string
): WarehouseDashboardData {
  const [data, setData] = useState<Omit<WarehouseDashboardData, "loading" | "error">>({
    resources: [],
    trucksInYard: [],
    arrivingTrucks: [],
    slots: [],
    escalations: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        // Fetch all data in parallel
        const [resourcesRes, yardRes, slotsRes, escalationsRes] = await Promise.all([
          fetch(`${API_BASE}/warehouse/${warehouseId}/resources`),
          fetch(`${API_BASE}/warehouse/${warehouseId}/yard`),
          fetch(`${API_BASE}/warehouse/${warehouseId}/slots`),
          fetch(`${API_BASE}/warehouse/${warehouseId}/escalations`),
        ]);

        const resourcesData = await resourcesRes.json();
        const yardData = await yardRes.json();
        const slotsData = await slotsRes.json();
        const escalationsData = await escalationsRes.json();

        setData({
          resources: resourcesData.resources || [],
          trucksInYard: yardData.trucks_in_yard || [],
          arrivingTrucks: yardData.arriving_trucks || [],
          slots: slotsData.slots || [],
          escalations: escalationsData.escalations || [],
        });
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to fetch warehouse dashboard data"
        );
      } finally {
        setLoading(false);
      }
    };

    if (warehouseId) {
      fetchData();
      
      // Refresh every 30 seconds
      const interval = setInterval(fetchData, 30000);
      return () => clearInterval(interval);
    }
  }, [warehouseId]);

  return { ...data, loading, error };
}
