# jp-med-dict 設計書 (v0.1 draft)

本書は `CLAUDE.md`(プロジェクト憲法)と `context/log.md`(履歴)を前提とする設計書である。MVP (v0.1) のスキーマ・ETL・配布・CI の設計確定版として扱い、実装はこれを唯一の根拠として Codex CLI に委譲する。

---

## 1. プロジェクト概要と非スコープ

### 1.1 目的

日本語の医療辞書(薬剤成分・商品名・病名・主要 ICD-10)を、**無料でアクセス可能な公的/オープンデータのみ**から自動構築し、**単一 SQLite ファイル**として GitHub Releases に配布する。消費側(DICTATION 等)は manifest を見て差分 DL し、ローカル SQLite をアトミック置換する。

### 1.2 MVP スコープ(5 ソース)

- 薬系 3: PMDA 添付文書 XML / 薬価基準収載品目 / 一般名処方マスタ
- 病名系 2: 万病辞書 MANBYO / DPC 傷病名マスター(ICD-10 紐付き)

### 1.3 非スコープ(v0.1 で扱わない)

- 臓器・解剖・生理学用語(既存辞書で十分、成長が遅い)
- 手技(K コード)※ v0.2 で追加予定
- ICD-10 単独辞書の完全版(DPC 経由の紐付き分のみ v0.1 に含める)
- MEDIS 標準病名マスター(再配布条件のため恒久除外、プラグイン化は将来検討)
- KEGG DRUG / MedDRA / JAPIC / UMLS / RxNorm / SNOMED CT(商用制限・有償・英語)
- 消費側クライアント SDK(Phase 2)

### 1.4 成果物

- `dist/jp-med-dict-vX.Y.Z.sqlite.zst` (本体)
- `dist/jp-med-dict-vX.Y.Z.manifest.json` (version / sha256 / row counts / source versions)

---

## 2. データソース詳細

各ソースについて、**URL・取得方法・更新頻度・ライセンス・既知の表記ゆれ対策**を示す。MVP では各 `sources/*.py` のモジュール冒頭に `SOURCE_URL` 定数としてこの表の URL を置く。URL が将来変わる可能性があるため、CI の 404 検知で自動アラートを出す。

### 2.1 PMDA 添付文書 XML

- **ソース**: PMDA 医薬品医療機器情報提供ホームページ「添付文書等情報」
- **URL (トップ)**: `https://www.pmda.go.jp/PmdaSearch/iyakuSearch/`
- **一括 DL**: PMDA が提供する一括 ZIP(添付文書 XML)を想定。最新の URL は PMDA の「ダウンロードセンター」経由(構造変化するため `SOURCE_URL` は暫定、CI で追従)。
- **形式**: 各医薬品ごとの XML。承認番号・販売名・一般名・成分名・剤形・規格等。
- **更新頻度**: 随時(新規承認・改訂のたび)
- **ライセンス**: 公的公開。PMDA 利用規約に従い再配布時出典明記。
- **表記ゆれ対策**:
  - 販売名末尾の「錠」「顆粒」「注射液」「カプセル」等の剤形名
  - 全角/半角の数字・スペース・括弧(例: `「日医工」` のメーカー商標の扱い)
  - カタカナ長音記号(`ー` / `-`)のゆれ
  - 販売名と一般名で同じカナ表記が異なるケース

### 2.2 厚労省 薬価基準収載品目

- **ソース**: 厚労省「薬価基準収載品目リスト」
- **URL (トップ)**: `https://www.mhlw.go.jp/topics/2024/04/tp20240401-01.html` (年度別、毎 4/1 改定 + 5/6/8/11 月追加収載)
- **形式**: Excel / CSV。薬価基準コード(YJ コード)、品名、規格、薬価。
- **更新頻度**: 毎月(追加収載)+ 年 1 回の全面改定(4/1)
- **ライセンス**: 公的公開。
- **表記ゆれ対策**:
  - YJ コード(12 桁)を一意キーとして扱い、品名のゆれを吸収
  - 品名の「」付きメーカー名除去正規形を別カラムに保持

### 2.3 厚労省 一般名処方マスタ

- **ソース**: 厚労省「処方箋に記載する一般名処方の標準的な記載」
- **URL (トップ)**: `https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000066545.html`
- **形式**: Excel。一般名処方コード・一般名・対応商品名群。
- **更新頻度**: 四半期(薬価改定に同期)
- **ライセンス**: 公的公開。
- **表記ゆれ対策**: 一般名の「【一般名処方加算】」等の接頭辞除去。

### 2.4 万病辞書 MANBYO

- **ソース**: NAIST 荒牧研究室「万病辞書」
- **URL**: `https://sociocom.naist.jp/manbyo-dic/`
- **形式**: TSV / CSV(出現形・標準形・ICD-10・信頼度など)
- **規模**: 12 万語超
- **更新頻度**: 不定期(プロジェクトが継続している限り)
- **ライセンス**: **CC BY-SA 4.0** (コピーレフト伝播; 本辞書全体のデータは CC BY-SA 4.0 になる)
- **表記ゆれ対策**: 万病辞書自体が表記ゆれ辞書なので、これを正規形 → 別名マッピングの基盤とする。

### 2.5 DPC 傷病名マスター

- **ソース**: 厚労省「DPC 関連告示・通知」/「DPC/PDPS 傷病名マスター」
- **URL (トップ)**: `https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000049343.html`
- **形式**: CSV。DPC コード・傷病名・ICD-10 コード。
- **更新頻度**: 年 1 回(4/1 改定)+ 中間改定。
- **ライセンス**: 公的公開。
- **表記ゆれ対策**: ICD-10 紐付きのため、病名 ↔ ICD-10 のクロスウォークとして使用。

### 2.6 既知の共通リスク

- サイト構造変化で直リンクが切れやすい(特に PMDA 一括 DL)→ CI で `HEAD` チェック、失敗時は Slack 通知(v0.2)。
- 薬価改定(4/1)直後は一時的に旧 URL と新 URL が混在するため、手動トリガ用 `workflow_dispatch` を用意。

---

## 3. SQLite スキーマ設計

MVP の `schema.sql` は以下を正とする。全テーブルに `UNIQUE` を付け、冪等 INSERT(`INSERT OR REPLACE`)が可能な形にする。

```sql
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
```

### 3.1 正規化カラムの役割

- `*_kana`: カタカナ長音統一・全半角統一・空白除去の正規形。検索の第一キー。
- `*_hira`: ひらがな化。IME 候補やあいまい検索向け。
- 原表記は改変せず保持する。

---

## 4. ETL パイプライン構成

```
[fetch]        [parse]              [normalize]         [link]                [build]
sources/*.py → DataFrame (per src) → normalizer/kana → normalizer/link    → build/build_sqlite.py
                                      normalizer/dedupe                     → dist/*.sqlite.zst
                                                                            → build/manifest.py → manifest.json
```

- `sources/<src>.py` は **「取得 + パース」** までを担当し、統一された DataFrame を返す(列名はソース別に定義、詳細は各モジュール docstring)。
- `normalizer/` はソース非依存。`kana.py`(表記正規化) / `dedupe.py`(重複解決) / `link.py`(drugs ↔ ingredients, diseases ↔ aliases の関連付け)。
- `build/build_sqlite.py` は `schema.sql` を流し、正規化済み DataFrame を `to_sql` で書き込む。最後に `source_meta` を埋める。
- `build/manifest.py` は完成 SQLite の `sha256` と各テーブルの `COUNT(*)` を書き出し、`.manifest.json` を吐く。

### 4.1 失敗時の挙動

- 個別ソースの取得失敗は「ソース単位でスキップ + `source_meta.row_count=0`」。ただし CI ジョブは**失敗扱い**にし、Release は発行しない(古いビルドがそのまま残る)。
- スキーマ検証(`tests/test_schema.py`)・行数閾値(`tests/test_row_counts.py`)が落ちた場合も Release しない。

---

## 5. 正規化ロジック

### 5.1 カタカナ正規化 (`normalizer/kana.py`)

- `jaconv.z2h(..., kana=False, digit=True, ascii=True)` で数字・ASCII を半角化。
- `jaconv.h2z(..., kana=True, digit=False, ascii=False)` でカタカナを全角化。
- `jaconv.hira2kata` / `kata2hira` で仮名変換。
- 長音記号 `ー` を統一(`-` や `‐` を `ー` に)。
- 不可視文字(`\u200b`, `\u3000` の末尾スペース)を除去。

### 5.2 旧漢字・異体字

- MVP では **NFKC 正規化**までを行う(`unicodedata.normalize("NFKC", ...)`)。
- 本格的な旧字体 ⇄ 新字体マッピングは v0.2 で辞書導入予定。

### 5.3 ヨミガナ生成方針

- **原則ソース由来のカナを採用**(PMDA・一般名処方マスタには「カナ」列が存在する)。
- ソース欠落時のみフォールバックで `pykakasi` を呼ぶ(MVP では **呼ばない**。精度が担保できないため空に留める)。

### 5.4 重複解決 (`normalizer/dedupe.py`)

- 薬: `(yj_code)` が一致すれば同一。`yj_code` が NULL なら `(brand_name_kana, manufacturer)` で同一判定。
- 成分: `(ippanmei_code)` 一致で同一。NULL なら `(generic_kana)` で同一判定。
- 病名: `(dpc_code)` 一致で同一。NULL なら `(standard_name)` で同一判定。
- ソース優先順位: 薬は `yakkakijun > pmda > ippanmei`(薬価情報が最信頼)、病名は `dpc > manbyo`(ICD-10 紐付きが最信頼)。

### 5.5 関連付け (`normalizer/link.py`)

- 薬 → 成分: PMDA XML から `商品名 ↔ 一般名` を抽出し、`drug_ingredients` を組む。一般名処方マスタ側からも逆引き補強。
- 病名 → 別名: 万病辞書の「出現形 → 標準形」マッピングから `disease_aliases` を組む。

---

## 6. バージョニングと配布

### 6.1 semver 運用

- **MAJOR**: スキーマ破壊的変更(カラム削除・型変更)
- **MINOR**: テーブル/カラム追加、ソース追加・削除
- **PATCH**: データ更新のみ(スキーマ不変)

月次 cron は原則 PATCH を繰り上げる。スキーマ差分があれば MINOR、破壊的なら MAJOR(手動レビュー)。

### 6.2 GitHub Releases

- タグ名: `vX.Y.Z`
- 添付: `jp-med-dict-vX.Y.Z.sqlite.zst`, `jp-med-dict-vX.Y.Z.manifest.json`
- リリースノート: `source_meta` の diff(前回 Release との行数差)を自動生成。

### 6.3 manifest.json 仕様例

```json
{
  "version": "0.1.0",
  "built_at": "2026-04-21T03:00:00Z",
  "sqlite_file": "jp-med-dict-v0.1.0.sqlite.zst",
  "sqlite_sha256": "<64-hex>",
  "sqlite_size_bytes": 12345678,
  "uncompressed_sha256": "<64-hex>",
  "uncompressed_size_bytes": 98765432,
  "schema_version": 1,
  "row_counts": {
    "drugs": 18234,
    "ingredients": 4120,
    "drug_ingredients": 19876,
    "diseases": 24500,
    "disease_aliases": 125300,
    "icd10": 9800
  },
  "sources": [
    { "name": "pmda",       "version": "2026-04-15", "url": "https://www.pmda.go.jp/...", "license": "Public" },
    { "name": "yakkakijun", "version": "2026-04-01", "url": "https://www.mhlw.go.jp/...", "license": "Public" },
    { "name": "ippanmei",   "version": "2026-04-01", "url": "https://www.mhlw.go.jp/...", "license": "Public" },
    { "name": "manbyo",     "version": "2024-09-30", "url": "https://sociocom.naist.jp/manbyo-dic/", "license": "CC BY-SA 4.0" },
    { "name": "dpc",        "version": "2024-04-01", "url": "https://www.mhlw.go.jp/...", "license": "Public" }
  ],
  "license": {
    "code": "MIT",
    "data": "CC BY-SA 4.0"
  }
}
```

---

## 7. GitHub Actions ワークフロー設計

`.github/workflows/monthly-update.yml`:

- **トリガ**:
  - `schedule: cron "0 3 1 * *"` (毎月 1 日 03:00 UTC = JST 12:00)
  - `workflow_dispatch:` (薬価改定直後の手動実行用、`inputs.force_version` で semver 強制指定可)
- **ジョブ**:
  1. `setup`: Python 3.11 + 依存インストール(`pip install -e .[dev]`)
  2. `fetch`: 各 source の ETL を並列実行(matrix: pmda/yakkakijun/ippanmei/manbyo/dpc)。artifact に DataFrame pickle を保存。
  3. `build`: 全 artifact をダウンロード → `build/build_sqlite.py` で統合 → zstd 圧縮 → `build/manifest.py`
  4. `test`: `pytest tests/` でスキーマ・正規化・行数閾値
  5. `release`:
     - 前回 Release の `manifest.json` と diff を取る
     - 差分に応じて semver 繰上げ(PATCH / MINOR / MAJOR は初期は PATCH 固定、MINOR/MAJOR は手動レビュー)
     - `softprops/action-gh-release@v2` で `dist/*.sqlite.zst` と `*.manifest.json` をアップロード

### 7.1 ジョブ間の制約

- `fetch` 失敗 → `build` 以降スキップ、Release なし。
- `test` 失敗 → Release なし、失敗ログ添付。
- 連続 2 ジョブ失敗で Issue 自動起票(v0.2)。

---

## 8. テスト方針

- **`tests/test_schema.py`**: メモリ SQLite に `schema.sql` を流し、期待テーブル・カラム・インデックスが全部揃っているかを検証。
- **`tests/test_normalizer.py`**: `normalizer/kana.py` の代表入出力スナップショット(例: `"ﾛｷｿﾆﾝ"` → `"ロキソニン"`, `"ﾛｷｿﾆﾝ"` → `"ろきそにん"`)。
- **`tests/test_row_counts.py`**: ビルド済み SQLite が存在するときに、各テーブルの行数が閾値以上であることをチェック(例: `drugs >= 10000`, `disease_aliases >= 50000`)。ビルド未実行時は skip。
- **代表ルックアップ**(v0.2 で追加): `"ロキソプロフェンナトリウム"` → 商品名ヒット件数が N 件以上、`"糖尿病"` → ICD-10 が `E10-E14` 範囲にヒット、等のスモーク。

---

## 9. 消費側 API(将来像)

- **v0.1**: SQLite 直接読み取りを前提。`sqlite3 jp-med-dict.sqlite "SELECT ... WHERE brand_name_kana LIKE ?"`
- **v0.2**: Python CLI (`jp-med-dict lookup drug ロキソニン`)。Swift 薄クライアント(DICTATION 側で利用、本リポには含めない)。
- **v0.3**: gRPC/HTTP サーバ(自前ホストしたい人向け、optional)。

消費側がスキーマを直叩きすることを許容する代わりに、スキーマ破壊的変更は semver MAJOR を厳守する。

---

## 10. ライセンス衛生と貢献ガイドライン

- **コード**: MIT。`LICENSE`(MIT 全文)をリポ直下に配置(v0.2 で追加、MVP 時点では README に明記)。
- **データ**: CC BY-SA 4.0(万病辞書伝播)。`LICENSE-DATA` を別ファイルで配置(v0.2)。Release 成果物には同梱。
- **PR**: 新規ソース追加 PR は、**ライセンスを明記した表** を `docs/plan.md` に追加することを必須とする。CC BY-SA 互換(= 同等以上の自由度)でなければマージしない。
- **CLA**: 当面不要(MIT + CC BY-SA 4.0 の混合配布に CLA は慣習上不要)。

---

## 11. リスクと対策

| リスク | 影響 | 対策 |
|---|---|---|
| PMDA 一括 DL URL が変わる | ETL 失敗 | 月次 CI の 404 で気付ける。`SOURCE_URL` を定数化、PR で一発変更。 |
| 厚労省サイトの年度別 URL 構造変化 | ETL 失敗 | 同上。年度切替月(4 月)の手動実行を運用ルール化。 |
| 万病辞書の更新停止 / ライセンス変更 | 病名表記ゆれが古いまま凍結 | 最後の公開版を `manbyo_frozen/` にアーカイブ、v0.1 互換を維持。 |
| データ量増大で SQLite が 100MB 超 | ダウンロード体験悪化 | zstd 圧縮 + テーブル別差分配信(v0.2)を検討。 |
| 万病辞書の CC BY-SA 伝播を消費アプリが誤認 | ライセンス違反 | manifest.json に `license.data: "CC BY-SA 4.0"` を明示、README で強調。 |
| 薬価改定(4/1)と月次 cron(毎月 1 日)の競合 | 4/1 時点で未反映の可能性 | 手動 `workflow_dispatch` を 4/1 午後に運用。 |
| 同姓同名の成分(表記ゆれ同一)の結合ミス | ingredients に重複行 | `generic_name UNIQUE` + `ippanmei_code UNIQUE` でガード、dedupe で統合。 |

---

## 12. 次アクション

- [ ] Codex に MVP スキャフォールド発注(sources / normalizer / build / GH Actions / tests / pyproject / justfile)
- [ ] 初回 fetch を手動実行して、各 `SOURCE_URL` が実在することを確認(本書策定後、別セッションで)
- [ ] v0.1.0 の初回 Release を手動トリガ
- [ ] DICTATION 側の消費コードの設計を別リポで起こす
- [ ] `LICENSE` / `LICENSE-DATA` ファイル設置(v0.2)
- [ ] `docs/plan.md` を MINOR 変更のたび更新(スキーマ変更・ソース追加時)
