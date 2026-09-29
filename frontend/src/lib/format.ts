import type {
  BookingStatus,
  DealStatus,
  Direction,
  Furnishing,
  LegalStatus,
  PropertyStatus,
  PropertyType,
  Role,
  ViewType,
} from "../api/types";

export const TIMEZONE = "Asia/Ho_Chi_Minh";

export const DIRECTION: Record<Direction, string> = {
  N: "Bắc",
  S: "Nam",
  E: "Đông",
  W: "Tây",
  NE: "Đông Bắc",
  NW: "Tây Bắc",
  SE: "Đông Nam",
  SW: "Tây Nam",
};

export const VIEW: Record<ViewType, string> = {
  LAKE: "Hồ",
  RIVER: "Sông",
  PARK: "Công viên",
  POOL: "Bể bơi",
  CITY: "Thành phố",
  INTERNAL: "Nội khu",
};

export const FURNISHING: Record<Furnishing, string> = {
  NONE: "Bàn giao thô",
  BASIC: "Nội thất cơ bản",
  FULL: "Full nội thất",
};

export const LEGAL: Record<LegalStatus, string> = {
  PINK_BOOK: "Sổ hồng",
  PENDING_BOOK: "Đang làm sổ",
  SALE_CONTRACT: "HĐMB",
};

export const PROPERTY_TYPE: Record<PropertyType, string> = {
  APARTMENT: "Chung cư",
  VILLA: "Biệt thự",
  TOWNHOUSE: "Liền kề",
  SHOPHOUSE: "Shophouse",
};

export const PROPERTY_STATUS: Record<PropertyStatus, string> = {
  DRAFT: "Bản nháp",
  PENDING_REVIEW: "Chờ duyệt",
  AVAILABLE: "Đang bán",
  REJECTED: "Bị từ chối",
  SOLD: "Đã bán",
  WITHDRAWN: "Đã tạm ngừng",
};

export const BOOKING_STATUS: Record<BookingStatus, string> = {
  REQUESTED: "Chờ chủ căn xác nhận",
  CONFIRMED: "Đã xác nhận",
  RESCHEDULE_REQUESTED: "Chờ xác nhận đổi lịch",
  REJECTED: "Bị từ chối",
  CANCELLED: "Đã hủy",
  COMPLETED: "Đã xem",
  NO_SHOW: "Vắng mặt",
};

export const DEAL_STATUS: Record<DealStatus, string> = {
  MATCHED: "Đã kết nối",
  VIEWING_REQUESTED: "Đang chờ lịch xem",
  VIEWING_CONFIRMED: "Đã chốt lịch xem",
  VIEWED: "Đã xem nhà",
  INTERESTED: "Quan tâm",
  NEGOTIATING: "Đang trao đổi",
  TRANSACTION_SUPPORT: "Hỗ trợ giao dịch",
  COMPLETED: "Hoàn tất",
  CLOSED: "Đã đóng",
};

export const ROLE: Record<Role, string> = {
  CUSTOMER: "Người mua",
  OWNER: "Chủ căn",
  INVESTOR_OPERATOR: "Chủ đầu tư",
};

export const CRITERION: Record<string, string> = {
  price: "Giá",
  area: "Diện tích",
  bedrooms: "Số phòng ngủ",
  direction: "Hướng",
  view: "View",
  floor: "Tầng",
  furnishing: "Nội thất",
};

/** 3200000000 -> "3,2 tỷ" ; 850000000 -> "850 triệu" */
export function formatVnd(value: number): string {
  if (value >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} tỷ`;
  }
  return `${Math.round(value / 1_000_000).toLocaleString("vi-VN")} triệu`;
}

export function formatArea(value: string | number): string {
  return `${Number(value).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} m²`;
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", {
    timeZone: TIMEZONE,
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatTimeRange(startIso: string, endIso: string): string {
  const time = (iso: string) =>
    new Date(iso).toLocaleTimeString("vi-VN", { timeZone: TIMEZONE, hour: "2-digit", minute: "2-digit" });
  const day = new Date(startIso).toLocaleDateString("vi-VN", {
    timeZone: TIMEZONE,
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
  });
  return `${day} · ${time(startIso)}–${time(endIso)}`;
}

export function bedroomsLabel(n: number): string {
  return n === 0 ? "Studio" : `${n} PN`;
}

/** "2026-09-30" + "14:00" in Vietnam time -> ISO string with +07:00 */
export function vnIso(date: string, time: string): string {
  return `${date}T${time}:00+07:00`;
}

/** Today's date in Vietnam as YYYY-MM-DD (for date inputs). */
export function vnToday(offsetDays = 0): string {
  const d = new Date(Date.now() + offsetDays * 86_400_000);
  return d.toLocaleDateString("en-CA", { timeZone: TIMEZONE });
}

export function timeOf(iso: string): string {
  return new Date(iso).toLocaleTimeString("vi-VN", { timeZone: TIMEZONE, hour: "2-digit", minute: "2-digit" });
}

export function dateOf(iso: string): string {
  return new Date(iso).toLocaleDateString("vi-VN", { timeZone: TIMEZONE, day: "2-digit", month: "2-digit" });
}
