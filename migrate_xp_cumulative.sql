-- ============================================================
--  MIGRASI XP: model lama (xp = sisa-dalam-level) → model baru (xp = TOTAL kumulatif)
--  Jalankan SEKALI saja di Supabase SQL Editor.
--  AMAN untuk dijalankan ulang? TIDAK — hanya sekali. Lihat catatan SAFEGUARD di bawah.
-- ------------------------------------------------------------
--  Rumus ambang (identik dgn lib/xp.ts & status_service.py):
--    xp_required(L) = round(100 * 1.5^(L-1))
--  Total kumulatif untuk berada di awal level L:
--    sum( xp_required(1..L-1) )
--  xp_total_baru = xp_sisa_lama + sum(xp_required(1..level-1))
-- ============================================================

-- 0) SAFEGUARD: backup kolom xp lama dulu (sekali). Kalau kolom sudah ada, abaikan errornya.
ALTER TABLE characters ADD COLUMN IF NOT EXISTS xp_legacy_backup INTEGER;
UPDATE characters SET xp_legacy_backup = xp WHERE xp_legacy_backup IS NULL;

-- 1) Fungsi bantu: total XP kumulatif untuk mencapai AWAL sebuah level.
CREATE OR REPLACE FUNCTION total_xp_for_level(target_level INT)
RETURNS INT AS $$
DECLARE
    s INT := 0;
    l INT;
BEGIN
    IF target_level IS NULL OR target_level < 1 THEN target_level := 1; END IF;
    FOR l IN 1..(target_level - 1) LOOP
        s := s + round(100 * power(1.5, l - 1));
    END LOOP;
    RETURN s;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 2) PREVIEW dulu (jalankan ini sendiri untuk cek hasil sebelum commit):
-- SELECT id, name, level, xp AS xp_lama,
--        xp + total_xp_for_level(level) AS xp_baru_kumulatif
-- FROM characters ORDER BY id;

-- 3) KONVERSI: ubah xp jadi total kumulatif.
UPDATE characters
SET xp = xp + total_xp_for_level(COALESCE(level, 1))
WHERE xp_legacy_backup IS NOT NULL;   -- pastikan hanya baris yg sudah di-backup

-- 4) (opsional) Setelah verifikasi web & bot tampil benar, buang fungsi bantu:
-- DROP FUNCTION IF EXISTS total_xp_for_level(INT);

-- ROLLBACK kalau ada masalah (selama backup masih ada):
-- UPDATE characters SET xp = xp_legacy_backup;
