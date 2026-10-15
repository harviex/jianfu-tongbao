-- PostgreSQL 初始化脚本
-- 运行: psql -h <host> -U <user> -d <db> -f db_init.sql

-- 启用中文全文搜索扩展
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- CREATE EXTENSION IF NOT EXISTS zhparser;  -- 需要额外安装，暂时注释

-- 1. 原始数据表 (分区表，按登记日期分区)
CREATE TABLE IF NOT EXISTS raw_appeals (
    id BIGSERIAL,
    appeal_id VARCHAR(128) NOT NULL,
    source VARCHAR(128),
    source_sub VARCHAR(128),
    appeal_type VARCHAR(128),
    event_type VARCHAR(128),
    category_l1 VARCHAR(256),
    category_l2 VARCHAR(256),
    category_l3 VARCHAR(256),
    appeal_category VARCHAR(256),
    title TEXT,
    content TEXT,
    nature VARCHAR(128),
    register_time TIMESTAMP NOT NULL,
    seal_time TIMESTAMP,
    status VARCHAR(128),
    city VARCHAR(128),
    district VARCHAR(256),
    street VARCHAR(256),
    incident_area VARCHAR(512),
    address TEXT,
    handle_depts TEXT,
    handle_desc TEXT,
    transfer_unit TEXT,
    return_dept TEXT,
    return_reason TEXT,
    tags TEXT,
    incident_time TIMESTAMP,
    reply_content TEXT,
    satisfaction VARCHAR(128),
    evaluation TEXT,
    dept_deadline TIMESTAMP,
    rumor_type VARCHAR(128),
    handle_end_time TIMESTAMP,
    full_text TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (appeal_id, register_time)
) PARTITION BY RANGE (register_time);

-- 索引
CREATE INDEX IF NOT EXISTS idx_raw_appeals_fulltext ON raw_appeals USING GIN (to_tsvector('simple', full_text));
CREATE INDEX IF NOT EXISTS idx_raw_appeals_city ON raw_appeals (city);
CREATE INDEX IF NOT EXISTS idx_raw_appeals_category_l3 ON raw_appeals (category_l3);
CREATE INDEX IF NOT EXISTS idx_raw_appeals_register_time ON raw_appeals (register_time);
CREATE INDEX IF NOT EXISTS idx_raw_appeals_appeal_id ON raw_appeals (appeal_id);
-- 唯一约束（分区表不支持全局唯一，用排除约束或应用层保证）
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_appeals_appeal_id ON raw_appeals (appeal_id);

-- 为当天创建分区（示例，实际由脚本动态创建）
-- CREATE TABLE IF NOT EXISTS raw_appeals_20260804 PARTITION OF raw_appeals
--     FOR VALUES FROM ('2026-08-04') TO ('2026-08-05');

-- 2. 候选池表 (每日重建或增量)
CREATE TABLE IF NOT EXISTS daily_candidates (
    id BIGSERIAL PRIMARY KEY,
    appeal_id VARCHAR(32) NOT NULL,
    route VARCHAR(16) NOT NULL,          -- 'full', 'sample', 'skip', 'excluded'
    priority VARCHAR(8) NOT NULL,        -- 'HIGH', 'LOW', 'NONE'
    matched_keywords TEXT[],             -- 命中的白名单/灰度词
    matched_blacklist TEXT[],            -- 命中的黑名单
    process_date DATE NOT NULL,          -- 处理日期
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (appeal_id, process_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_candidates_route ON daily_candidates (route, priority);
CREATE INDEX IF NOT EXISTS idx_daily_candidates_process_date ON daily_candidates (process_date);
CREATE INDEX IF NOT EXISTS idx_daily_candidates_appeal_id ON daily_candidates (appeal_id);

-- 3. 线索结果表 (核心业务表)
CREATE TABLE IF NOT EXISTS clues (
    id BIGSERIAL PRIMARY KEY,
    appeal_id VARCHAR(32) UNIQUE NOT NULL,
    -- 基础字段 (来自原始数据)
    title TEXT,
    content TEXT,
    publish_time TIMESTAMP,
    region_city VARCHAR(64),
    region_district VARCHAR(64),
    complained_unit TEXT,
    -- LLM 判读字段
    is_relevant BOOLEAN,
    category VARCHAR(64),
    subcategory VARCHAR(64),
    root_cause VARCHAR(128),
    confidence REAL,
    tags TEXT[],
    qualitative_analysis TEXT,
    evidence_suggestion TEXT,
    llm_reason TEXT,
    llm_model VARCHAR(32),
    route VARCHAR(16),
    priority VARCHAR(8),
    matched_keywords TEXT[],
    is_typical BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_clues_relevant ON clues (is_relevant) WHERE is_relevant = TRUE;
CREATE INDEX IF NOT EXISTS idx_clues_confidence ON clues (confidence DESC) WHERE is_relevant = TRUE;
CREATE INDEX IF NOT EXISTS idx_clues_city ON clues (region_city);
CREATE INDEX IF NOT EXISTS idx_clues_category ON clues (category, subcategory);
CREATE INDEX IF NOT EXISTS idx_clues_publish_time ON clues (publish_time DESC);
CREATE INDEX IF NOT EXISTS idx_clues_fulltext ON clues USING GIN (to_tsvector('simple', title || ' ' || content));
CREATE INDEX IF NOT EXISTS idx_clues_appeal_id ON clues (appeal_id);
CREATE INDEX IF NOT EXISTS idx_clues_created_at ON clues (created_at);

-- 4. 统计表 (每日汇总)
CREATE TABLE IF NOT EXISTS daily_stats (
    id BIGSERIAL PRIMARY KEY,
    process_date DATE UNIQUE NOT NULL,
    total_raw INTEGER,
    blacklist_excluded INTEGER,
    candidate_total INTEGER,
    candidate_high INTEGER,
    candidate_low INTEGER,
    candidate_none INTEGER,
    llm_called INTEGER,
    relevant_found INTEGER,
    high_confidence INTEGER,
    zero_keyword_sampled INTEGER,
    zero_keyword_relevant INTEGER,
    processing_time_seconds REAL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats (process_date);

-- 5. 黑白名单版本记录表
CREATE TABLE IF NOT EXISTS list_versions (
    id BIGSERIAL PRIMARY KEY,
    list_type VARCHAR(16) NOT NULL,     -- 'blacklist', 'whitelist', 'greylist'
    version VARCHAR(32) NOT NULL,
    pattern_count INTEGER,
    changed_by VARCHAR(64),             -- 'auto', 'manual', 'curated'
    change_summary TEXT,
    yaml_content TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (list_type, version)
);

CREATE INDEX IF NOT EXISTS idx_list_versions_type ON list_versions (list_type);

-- 6. 复核记录表
CREATE TABLE IF NOT EXISTS review_records (
    id BIGSERIAL PRIMARY KEY,
    appeal_id VARCHAR(32) NOT NULL,
    process_date DATE NOT NULL,
    original_label BOOLEAN,              -- LLM 判读结果
    review_label VARCHAR(8),             -- 'TP', 'FP', 'UNSURE'
    review_note TEXT,
    reviewer VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (appeal_id, process_date)
);

CREATE INDEX IF NOT EXISTS idx_review_records_date ON review_records (process_date);
CREATE INDEX IF NOT EXISTS idx_review_records_label ON review_records (review_label);