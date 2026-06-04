-- ============================================================
-- NARATOR BOT - Supabase PostgreSQL Schema
-- Project: Homebrew (teobiexkuvlmgolgvzwa.supabase.co)
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- CORE TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS characters (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    class TEXT,
    race TEXT,
    level INTEGER DEFAULT 1,
    hp INTEGER DEFAULT 0,
    hp_max INTEGER DEFAULT 0,
    energy INTEGER DEFAULT 0,
    energy_max INTEGER DEFAULT 0,
    stamina INTEGER DEFAULT 0,
    stamina_max INTEGER DEFAULT 0,
    str_stat INTEGER DEFAULT 0,
    dex_stat INTEGER DEFAULT 0,
    con_stat INTEGER DEFAULT 0,
    int_stat INTEGER DEFAULT 0,
    wis INTEGER DEFAULT 0,
    cha INTEGER DEFAULT 0,
    ac INTEGER DEFAULT 10,
    init_mod INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    gold INTEGER DEFAULT 0,
    speed INTEGER DEFAULT 30,
    carry_capacity INTEGER DEFAULT 0,
    carry_used REAL DEFAULT 0,
    buffs JSONB DEFAULT '[]',
    debuffs JSONB DEFAULT '[]',
    effects JSONB DEFAULT '[]',
    equipment JSONB DEFAULT '{}',
    companions JSONB DEFAULT '[]',
    inventory JSONB DEFAULT '[]',
    discord_user_id TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS enemies (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    hp INTEGER DEFAULT 0,
    hp_max INTEGER DEFAULT 0,
    energy INTEGER DEFAULT 0,
    energy_max INTEGER DEFAULT 0,
    stamina INTEGER DEFAULT 0,
    stamina_max INTEGER DEFAULT 0,
    ac INTEGER DEFAULT 10,
    effects JSONB DEFAULT '[]',
    xp_reward INTEGER DEFAULT 0,
    gold_reward INTEGER DEFAULT 0,
    loot JSONB DEFAULT '[]',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS allies (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    hp INTEGER DEFAULT 0,
    hp_max INTEGER DEFAULT 0,
    energy INTEGER DEFAULT 0,
    energy_max INTEGER DEFAULT 0,
    stamina INTEGER DEFAULT 0,
    stamina_max INTEGER DEFAULT 0,
    ac INTEGER DEFAULT 10,
    effects JSONB DEFAULT '[]',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS companions (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    owner TEXT,
    hp INTEGER DEFAULT 0,
    hp_max INTEGER DEFAULT 0,
    energy INTEGER DEFAULT 0,
    energy_max INTEGER DEFAULT 0,
    stamina INTEGER DEFAULT 0,
    stamina_max INTEGER DEFAULT 0,
    ac INTEGER DEFAULT 10,
    effects JSONB DEFAULT '[]',
    modules JSONB DEFAULT '[]',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, name)
);

-- ============================================================
-- WORLD TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS quests (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',
    assigned_to JSONB DEFAULT '[]',
    rewards JSONB DEFAULT '{}',
    rewards_visible INTEGER DEFAULT 1,
    favor JSONB DEFAULT '{}',
    tags JSONB DEFAULT '{}',
    archived INTEGER DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS npc (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    role TEXT,
    favor INTEGER DEFAULT 0,
    traits JSONB DEFAULT '{}',
    info JSONB DEFAULT '{"value": "", "visible": 1}',
    status TEXT DEFAULT 'Alive',
    affiliation TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS npc_shop (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    npc_name TEXT NOT NULL,
    item TEXT NOT NULL,
    price INTEGER DEFAULT 0,
    stock INTEGER DEFAULT -1,
    favor_req JSONB DEFAULT '{}',
    quest_req JSONB DEFAULT '[]',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, npc_name, item)
);

CREATE TABLE IF NOT EXISTS factions (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    faction_type TEXT DEFAULT 'general',
    hidden INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS favors (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    char_name TEXT,
    faction TEXT NOT NULL,
    favor INTEGER DEFAULT 0,
    notes TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, char_name, faction)
);

CREATE TABLE IF NOT EXISTS items (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    item_type TEXT,
    effect TEXT,
    rarity TEXT DEFAULT 'Common',
    item_value INTEGER DEFAULT 0,
    weight REAL DEFAULT 0.1,
    slot TEXT,
    notes TEXT,
    rules TEXT,
    requirement TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS inventory (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    owner TEXT,
    item TEXT,
    qty INTEGER DEFAULT 1,
    metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- SKILL & EFFECT TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS skill_library (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT,
    category TEXT,
    effect TEXT,
    drawback TEXT,
    cost TEXT
);

CREATE TABLE IF NOT EXISTS skills (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    char_name TEXT,
    skill_id INTEGER,
    category TEXT,
    name TEXT,
    level INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS effects (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    type TEXT,
    target_stat TEXT,
    formula TEXT,
    duration INTEGER DEFAULT 0,
    stack_mode TEXT DEFAULT 'add',
    description TEXT,
    max_stack INTEGER DEFAULT 3,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, name)
);

-- ============================================================
-- CRAFTING TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS blueprints (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    req JSONB DEFAULT '{}',
    result TEXT,
    target_progress INTEGER DEFAULT 100,
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS crafting (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    player TEXT NOT NULL,
    blueprint TEXT,
    progress INTEGER DEFAULT 0,
    UNIQUE(guild_id, player)
);

CREATE TABLE IF NOT EXISTS known_blueprints (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    player TEXT,
    blueprint TEXT,
    UNIQUE(guild_id, player, blueprint)
);

-- ============================================================
-- HOLLOW / LOCATION TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS hollow_nodes (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    zone TEXT,
    type TEXT,
    traits JSONB DEFAULT '[]',
    types JSONB DEFAULT '[]',
    npcs JSONB DEFAULT '[]',
    visitors JSONB DEFAULT '[]',
    events JSONB DEFAULT '[]',
    vendors_today JSONB DEFAULT '[]',
    event_today JSONB DEFAULT '{}',
    visitors_today JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS hollow_log (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    node TEXT,
    vendors JSONB DEFAULT '[]',
    visitors JSONB DEFAULT '[]',
    event TEXT,
    time_slot TEXT DEFAULT 'day',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hollow_visitors (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    rarity TEXT DEFAULT 'common',
    chance INTEGER DEFAULT 50,
    description TEXT DEFAULT '',
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS hollow_events (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    rarity TEXT DEFAULT 'common',
    chance INTEGER DEFAULT 10,
    description TEXT DEFAULT '',
    effect TEXT DEFAULT '',
    effect_formula TEXT DEFAULT '',
    UNIQUE(guild_id, name)
);

-- ============================================================
-- SYSTEM TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS history (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    action TEXT,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS timeline (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    event TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS initiative (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    order_json JSONB DEFAULT '[]',
    ptr INTEGER DEFAULT 0,
    round INTEGER DEFAULT 1,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memories (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id TEXT,
    type TEXT,
    value TEXT,
    meta JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- MAP TABLE (baru - untuk website)
-- ============================================================

CREATE TABLE IF NOT EXISTS map_markers (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    label TEXT,
    type TEXT DEFAULT 'location',
    x REAL NOT NULL,
    y REAL NOT NULL,
    color TEXT DEFAULT '#00d4ff',
    visible_to JSONB DEFAULT '[]',
    data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS map_fog (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    revealed BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, grid_x, grid_y)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_characters_guild ON characters(guild_id);
CREATE INDEX IF NOT EXISTS idx_characters_discord ON characters(discord_user_id);
CREATE INDEX IF NOT EXISTS idx_enemies_guild ON enemies(guild_id);
CREATE INDEX IF NOT EXISTS idx_quests_guild ON quests(guild_id);
CREATE INDEX IF NOT EXISTS idx_npc_guild ON npc(guild_id);
CREATE INDEX IF NOT EXISTS idx_inventory_owner ON inventory(guild_id, owner);
CREATE INDEX IF NOT EXISTS idx_factions_guild ON factions(guild_id);
CREATE INDEX IF NOT EXISTS idx_favors_guild ON favors(guild_id);
CREATE INDEX IF NOT EXISTS idx_timeline_guild ON timeline(guild_id);
CREATE INDEX IF NOT EXISTS idx_history_guild ON history(guild_id);
CREATE INDEX IF NOT EXISTS idx_hollow_nodes_guild ON hollow_nodes(guild_id);
CREATE INDEX IF NOT EXISTS idx_map_markers_guild ON map_markers(guild_id);
CREATE INDEX IF NOT EXISTS idx_map_fog_guild ON map_fog(guild_id);

-- ============================================================
-- REALTIME (enable untuk tabel yang perlu live update di website)
-- ============================================================

ALTER PUBLICATION supabase_realtime ADD TABLE characters;
ALTER PUBLICATION supabase_realtime ADD TABLE enemies;
ALTER PUBLICATION supabase_realtime ADD TABLE quests;
ALTER PUBLICATION supabase_realtime ADD TABLE timeline;
ALTER PUBLICATION supabase_realtime ADD TABLE map_markers;
ALTER PUBLICATION supabase_realtime ADD TABLE map_fog;
ALTER PUBLICATION supabase_realtime ADD TABLE initiative;
