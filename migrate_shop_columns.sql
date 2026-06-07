-- ============================================================
--  PENGAMAN KOLOM SHOP/NPC — selaraskan schema dgn yang dipakai web
--  Aman dijalankan kapan saja: IF NOT EXISTS -> skip kalau sudah ada.
--  Jalankan di Supabase SQL Editor.
-- ============================================================

-- Kolom yang dibaca/ditulis web GM & shop player tapi belum di schema.sql:
ALTER TABLE npc ADD COLUMN IF NOT EXISTS can_shop    BOOLEAN DEFAULT false;
ALTER TABLE npc ADD COLUMN IF NOT EXISTS met_by      JSONB   DEFAULT '[]'::jsonb;
ALTER TABLE npc ADD COLUMN IF NOT EXISTS shop_access JSONB   DEFAULT '[]'::jsonb;
ALTER TABLE npc ADD COLUMN IF NOT EXISTS location    TEXT;  -- masih dipakai GM utk info, gate-nya sudah dihapus

-- npc_shop: diskon per-item (web pakai s.discount)
ALTER TABLE npc_shop ADD COLUMN IF NOT EXISTS discount INTEGER DEFAULT 0;

-- items: harga jual eksplisit (kalau null, web fallback ke item_value*0.5)
ALTER TABLE items ADD COLUMN IF NOT EXISTS sell_value INTEGER;

-- characters: kolom location pernah dirujuk (gate sudah dihapus, tapi aman ada utk masa depan)
ALTER TABLE characters ADD COLUMN IF NOT EXISTS location TEXT;

-- VERIFIKASI (jalankan utk cek kolom sekarang ada):
-- SELECT column_name FROM information_schema.columns WHERE table_name='npc' ORDER BY column_name;
