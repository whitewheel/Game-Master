-- ============================================================
--  ENABLE REALTIME — biar create/edit langsung muncul di semua
--  tab (GM & player) tanpa perlu refresh manual.
--  Penyebab umum "harus refresh dulu": tabel belum masuk ke
--  publication supabase_realtime, jadi .subscribe() di web jalan
--  tapi tidak pernah menerima event.
--
--  Jalankan SEKALI di Supabase -> SQL Editor.
--  Aman diulang: kalau tabel sudah ada di publication, Postgres
--  akan error "already member" untuk baris itu saja — abaikan,
--  atau jalankan baris per baris.
-- ============================================================

-- Pastikan publication ada (Supabase biasanya sudah otomatis):
-- CREATE PUBLICATION supabase_realtime;   -- uncomment kalau belum ada

ALTER PUBLICATION supabase_realtime ADD TABLE characters;
ALTER PUBLICATION supabase_realtime ADD TABLE enemies;
ALTER PUBLICATION supabase_realtime ADD TABLE quests;
ALTER PUBLICATION supabase_realtime ADD TABLE initiative;
ALTER PUBLICATION supabase_realtime ADD TABLE npc;
ALTER PUBLICATION supabase_realtime ADD TABLE npc_shop;
ALTER PUBLICATION supabase_realtime ADD TABLE items;
ALTER PUBLICATION supabase_realtime ADD TABLE inventory;
ALTER PUBLICATION supabase_realtime ADD TABLE companions;
ALTER PUBLICATION supabase_realtime ADD TABLE factions;
ALTER PUBLICATION supabase_realtime ADD TABLE favors;
ALTER PUBLICATION supabase_realtime ADD TABLE hollow_nodes;
ALTER PUBLICATION supabase_realtime ADD TABLE map_markers;
ALTER PUBLICATION supabase_realtime ADD TABLE battle_grid;
ALTER PUBLICATION supabase_realtime ADD TABLE battle_tokens;
ALTER PUBLICATION supabase_realtime ADD TABLE battle_obstacles;
ALTER PUBLICATION supabase_realtime ADD TABLE effects;
ALTER PUBLICATION supabase_realtime ADD TABLE battle_log;
ALTER PUBLICATION supabase_realtime ADD TABLE history;
ALTER PUBLICATION supabase_realtime ADD TABLE skill_library;
ALTER PUBLICATION supabase_realtime ADD TABLE enemy_templates;

-- VERIFIKASI tabel apa saja yg sudah realtime:
-- SELECT tablename FROM pg_publication_tables WHERE pubname='supabase_realtime' ORDER BY tablename;
