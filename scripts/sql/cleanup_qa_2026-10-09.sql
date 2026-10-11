-- Clean up the test data left on the demo database by the QA run of 09/10/2026 ("Báo cáo kiểm thử BookingBot MVP").
--
-- Removes:
--   * the test buyers 0987650001 (Nguoi Mua Test A) and 0987650002 (Nguoi Mua Test B), with their deals
--     (VH-2026-00019 .. VH-2026-00023), viewing requests, holds, chats with the assistant and notifications
--   * the listing marked "[QA TEST]" (S7.02-1608, waiting for review); its red book stays verified, so the
--     showcase seed can list it again on the next deploy
--   * support request #6 (only if a test buyer raised it)
-- Restores:
--   * the demo request of Trần Quốc Bảo (0938100101, VH-2026-00015 on the demo site), closed when test buyer A was confirmed at the same time,
--     back to "waiting for the seller" (only if its viewing time is still more than 2 hours ahead)
--
-- Run with psql against the demo database. It ends with ROLLBACK: read the counts first, then change the last line
-- to COMMIT and run it again.
--   psql "$DATABASE_URL" -f scripts/sql/cleanup_qa_2026-10-09.sql

BEGIN;

CREATE TEMP TABLE qa_users ON COMMIT DROP AS
    SELECT id FROM users WHERE phone IN ('0987650001', '0987650002') AND role = 'CUSTOMER';
-- Only deals of the test buyers (deal codes are numbered per database: never delete by code alone)
CREATE TEMP TABLE qa_deals ON COMMIT DROP AS
    SELECT id, code FROM deals WHERE buyer_id IN (SELECT id FROM qa_users);
CREATE TEMP TABLE qa_bookings ON COMMIT DROP AS
    SELECT id FROM bookings WHERE deal_id IN (SELECT id FROM qa_deals) OR customer_id IN (SELECT id FROM qa_users);
CREATE TEMP TABLE qa_listings ON COMMIT DROP AS
    SELECT id FROM properties
    WHERE description LIKE '%[QA TEST]%' AND status IN ('PENDING_REVIEW', 'REJECTED', 'DRAFT', 'WITHDRAWN')
      AND NOT EXISTS (SELECT 1 FROM deals d WHERE d.property_id = properties.id);

SELECT 'test buyers' AS what, count(*) FROM qa_users
UNION ALL SELECT 'deals', count(*) FROM qa_deals
UNION ALL SELECT 'viewing requests', count(*) FROM qa_bookings
UNION ALL SELECT '[QA TEST] listings', count(*) FROM qa_listings
UNION ALL SELECT 'support request #6 of a test buyer', count(*)
    FROM escalations WHERE id = 6 AND requester_id IN (SELECT id FROM qa_users);
-- Expected: VH-2026-00019 .. VH-2026-00023
SELECT string_agg(code, ', ' ORDER BY code) AS deals_to_delete FROM qa_deals;

-- Support request #6 (raised by a test buyer)
DELETE FROM escalations WHERE id = 6 AND requester_id IN (SELECT id FROM qa_users);

-- Viewing requests and deals of the test buyers (holds first: they point at bookings and deals)
DELETE FROM property_holds WHERE booking_id IN (SELECT id FROM qa_bookings) OR deal_id IN (SELECT id FROM qa_deals);
DELETE FROM notifications WHERE booking_id IN (SELECT id FROM qa_bookings) OR deal_id IN (SELECT id FROM qa_deals);
DELETE FROM escalations WHERE booking_id IN (SELECT id FROM qa_bookings) OR deal_id IN (SELECT id FROM qa_deals);
DELETE FROM bookings WHERE id IN (SELECT id FROM qa_bookings);
DELETE FROM deals WHERE id IN (SELECT id FROM qa_deals);

-- The test buyers themselves (profile, chats, notifications, recommendations go with them)
DELETE FROM escalations WHERE requester_id IN (SELECT id FROM qa_users);
DELETE FROM audit_logs WHERE actor_id IN (SELECT id FROM qa_users);
DELETE FROM otp_codes WHERE target IN ('0987650001', '0987650002');
DELETE FROM users WHERE id IN (SELECT id FROM qa_users);

-- The [QA TEST] listing (photos and viewing slots go with it)
DELETE FROM properties WHERE id IN (SELECT id FROM qa_listings);

-- Trần Quốc Bảo's demo request (found by his demo phone, not by deal code): waiting for the seller again
UPDATE bookings b
SET status = 'REQUESTED', responded_at = NULL, rejection_reason = NULL
FROM users u
WHERE b.customer_id = u.id AND u.phone = '0938100101'
  AND b.status = 'REJECTED' AND b.rejection_reason = 'Chủ căn đã nhận một lịch xem khác vào giờ này'
  AND b.start_at > now() + interval '2 hours';
UPDATE deals d SET status = 'VIEWING_REQUESTED'
FROM users u
WHERE d.buyer_id = u.id AND u.phone = '0938100101'
  AND EXISTS (SELECT 1 FROM bookings b WHERE b.deal_id = d.id AND b.status = 'REQUESTED');

SELECT d.code, d.status FROM deals d JOIN users u ON u.id = d.buyer_id WHERE u.phone = '0938100101';

ROLLBACK;  -- change to COMMIT once the counts above look right
