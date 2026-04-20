-- schema.sql (v0.1)
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- 薬: 商品名(販売名)
CREATE TABLE IF NOT EXISTS drugs (
    drug_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    yj_code          TEXT UNIQUE,                    -- 薬価基準コード(12 桁, NULL 可: 薬価未収載品)
    brand_name       TEXT NOT NULL,                  -- 販売名(原表記)
    brand_name_kana  TEXT,                           -- カタカナ正規形
    brand_name_hira  TEXT,                           -- ひらがな
    dosage_form      TEXT,                           -- 剤形(錠/カプセル/注射液 等)
    strength         TEXT,                           -- 規格
    manufacturer     TEXT,                           -- 製造販売元
    approval_no      TEXT,                           -- 承認番号(PMDA)
    price_yen        REAL,                           -- 薬価(円)
    source           TEXT NOT NULL,                  -- 'pmda' | 'yakkakijun' | 'ippanmei'
    source_version   TEXT NOT NULL                   -- 例: 2026-04-01
);
CREATE INDEX IF NOT EXISTS idx_drugs_brand      ON drugs(brand_name);
CREATE INDEX IF NOT EXISTS idx_drugs_brand_kana ON drugs(brand_name_kana);
CREATE INDEX IF NOT EXISTS idx_drugs_yj         ON drugs(yj_code);

-- 薬: 一般名(成分名)
CREATE TABLE IF NOT EXISTS ingredients (
    ingredient_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    ippanmei_code    TEXT UNIQUE,                    -- 一般名処方マスタコード(NULL 可)
    generic_name     TEXT NOT NULL UNIQUE,           -- 一般名(原表記)
    generic_kana     TEXT,                           -- カタカナ正規形
    generic_hira     TEXT,                           -- ひらがな
    source           TEXT NOT NULL,
    source_version   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ingredients_name  ON ingredients(generic_name);
CREATE INDEX IF NOT EXISTS idx_ingredients_kana  ON ingredients(generic_kana);

-- 薬: 商品名 ↔ 成分 多対多
CREATE TABLE IF NOT EXISTS drug_ingredients (
    drug_id          INTEGER NOT NULL REFERENCES drugs(drug_id) ON DELETE CASCADE,
    ingredient_id    INTEGER NOT NULL REFERENCES ingredients(ingredient_id) ON DELETE CASCADE,
    amount           TEXT,                           -- 1 錠中の含量等(自由表記)
    PRIMARY KEY (drug_id, ingredient_id)
);
CREATE INDEX IF NOT EXISTS idx_di_drug        ON drug_ingredients(drug_id);
CREATE INDEX IF NOT EXISTS idx_di_ingredient  ON drug_ingredients(ingredient_id);

-- 病名: 標準形
CREATE TABLE IF NOT EXISTS diseases (
    disease_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_name    TEXT NOT NULL UNIQUE,           -- 標準形(DPC or 万病辞書 standard)
    standard_kana    TEXT,                           -- カタカナ正規形
    standard_hira    TEXT,                           -- ひらがな
    icd10_code       TEXT,                           -- ICD-10(NULL 可)
    dpc_code         TEXT UNIQUE,                    -- DPC 傷病名コード(NULL 可)
    source           TEXT NOT NULL,                  -- 'dpc' | 'manbyo'
    source_version   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_diseases_name  ON diseases(standard_name);
CREATE INDEX IF NOT EXISTS idx_diseases_kana  ON diseases(standard_kana);
CREATE INDEX IF NOT EXISTS idx_diseases_icd10 ON diseases(icd10_code);

-- 病名: 表記ゆれ(万病辞書 + DPC 旧表記等)
CREATE TABLE IF NOT EXISTS disease_aliases (
    alias_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    disease_id       INTEGER NOT NULL REFERENCES diseases(disease_id) ON DELETE CASCADE,
    alias            TEXT NOT NULL,                  -- 出現形(原表記)
    alias_kana       TEXT,
    alias_hira       TEXT,
    confidence       REAL,                           -- 万病辞書の信頼度(0-1)
    source           TEXT NOT NULL,
    UNIQUE (disease_id, alias)
);
CREATE INDEX IF NOT EXISTS idx_aliases_alias      ON disease_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_aliases_alias_kana ON disease_aliases(alias_kana);
CREATE INDEX IF NOT EXISTS idx_aliases_disease    ON disease_aliases(disease_id);

-- ICD-10 コードマスター(DPC 経由で v0.1 は部分セット)
CREATE TABLE IF NOT EXISTS icd10 (
    icd10_code       TEXT PRIMARY KEY,               -- 例: 'E11.9'
    jp_label         TEXT,                           -- 日本語ラベル(DPC 由来)
    source           TEXT NOT NULL,
    source_version   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_icd10_label ON icd10(jp_label);

-- ソースメタ(ビルド時の各ソースのバージョン/取得日時)
CREATE TABLE IF NOT EXISTS source_meta (
    source           TEXT PRIMARY KEY,               -- 'pmda' | 'yakkakijun' | 'ippanmei' | 'manbyo' | 'dpc'
    source_version   TEXT NOT NULL,
    fetched_at       TEXT NOT NULL,                  -- ISO 8601
    row_count        INTEGER NOT NULL,
    source_url       TEXT NOT NULL,
    license          TEXT NOT NULL                   -- 'Public' | 'CC BY-SA 4.0' 等
);
