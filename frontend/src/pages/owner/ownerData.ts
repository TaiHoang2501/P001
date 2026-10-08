import { useQuery } from "@tanstack/react-query";

import { api, call } from "../../api/client";
import type { Booking, OwnershipVerification } from "../../api/types";

/** Requests the seller still has to answer (a new request or a new time for a confirmed one). */
export const WAITING = new Set<Booking["status"]>(["REQUESTED", "RESCHEDULE_REQUESTED"]);

/** A request the seller can still answer: waiting for them, and the viewing time has not passed. */
export function needsAnswer(b: Booking, now = Date.now()): boolean {
  return WAITING.has(b.status) && new Date(b.proposed_start_at ?? b.start_at).getTime() > now;
}

/** All the seller's viewing requests; refreshed so new ones show up without reloading. */
export function useOwnerBookings() {
  return useQuery({
    queryKey: ["owner-bookings", "ALL"],
    queryFn: () => call(api.GET("/api/v1/owner/bookings")),
    refetchInterval: 30_000,
  });
}

export function useOwnerProperties() {
  return useQuery({ queryKey: ["owner-properties"], queryFn: () => call(api.GET("/api/v1/owner/properties")) });
}

/** Per-listing numbers (requests, AI suggestions) and how long the seller has to answer a request. */
export function useOwnerOverview() {
  return useQuery({
    queryKey: ["owner-overview"],
    queryFn: () => call(api.GET("/api/v1/owner/overview")),
    refetchInterval: 60_000,
  });
}

/** Calendar day in Vietnam time, "YYYY-MM-DD". */
export function vnDay(iso: string | Date): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(new Date(iso));
}

/** Red books the seller has verified; each one can back one listing. */
export function useRedBooks() {
  return useQuery({ queryKey: ["owner-ownership"], queryFn: () => call(api.GET("/api/v1/owner/ownership")) });
}

/** Unused verified red books, i.e. homes the seller may list now. */
export function usableRedBooks(books: OwnershipVerification[] | undefined): OwnershipVerification[] {
  return (books ?? []).filter((b) => b.status === "VERIFIED" && b.property_id == null);
}
