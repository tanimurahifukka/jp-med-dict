# jp-med-dict セッション履歴

このファイルは jp-med-dict プロジェクトでの作業履歴・決定事項・未解決事項を追記式で残す。新しい Claude セッションはまず CLAUDE.md → このファイルの順に目を通して文脈を引き継ぐ。

---

## 2026-04-21

### 発端

- DICTATION プロジェクトの議論中、ユーザーから「医療辞書は臓器などは増えない。薬剤成分と病名が肥大化する領域。そこだけに絞って強化するアプローチで OSS 配布したい」との方針提示。
- 無料でアクセスできる日本語リソースを調査した結果、**断片的には存在するが統合辞書は無料では存在しない**ことが判明 → 自作価値高。
- ユーザー指示: 「フォルダごと全部分ける。いつも別プロジェクトとして考える」→ DICTATION から切り離し、独立リポジトリとして立ち上げ。

### 決定

- **独立プロジェクトとして分離**。DICTATION 配下の `future/medical-dictionary/` は削除済み。本プロジェクトは `/Users/tanimura/Desktop/jp-med-dict/` 単独で進める。
- **ライセンス分離が目的**: 万病辞書(CC BY-SA 4.0)取り込みによるコピーレフト伝播を DICTATION 本体(MIT 想定)と混ぜないため、独立リポが必須。
- スコープ: 薬剤成分・商品名・病名・主要手技(K コード)。臓器/解剖/生理学用語は非対象。
- ETL 言語は Python(DICTATION の Swift 縛りは本プロジェクトに適用しない)。成果物は SQLite + zstd 圧縮、GitHub Releases 配布。月次自動更新(GH Actions cron)。
- ライセンス方針: データ CC BY-SA 4.0 / コード MIT。

### データソース確認済み(調査結果)

採用候補(無料・公的):
- PMDA 添付文書 XML(薬・成分)
- 厚労省 薬価基準収載品目(月次更新)
- 厚労省 一般名処方マスタ
- 万病辞書 MANBYO(病名表記ゆれ、CC BY-SA 4.0、12 万語超)
- DPC 傷病名マスター(ICD-10 紐付き)
- ICD-10 日本語版
- MEDIS 標準病名マスター(要登録・再配布条件要確認)
- 診療報酬 K コード(手技)

採用しない: KEGG DRUG(商用制限の可能性)、MedDRA / JAPIC(有償)、UMLS / RxNorm / SNOMED CT(英語/要ライセンス)。

### 2026-04-21 確定事項(4 件)

1. **プロジェクト名**: `jp-med-dict` で確定。
2. **GitHub リポジトリ**: `tanimurahifukka/jp-med-dict`(public)を今作成。
3. **MVP スコープ**: 薬剤成分 + 商品名 + 万病辞書 + DPC 傷病名 の 4 点から開始。
4. **MEDIS 標準病名マスター**: コアから**外す**(再配布条件が厳しいため)。将来プラグイン方式で各自追加する構成なら再検討。

### 未解決 / 次アクション

- [x] プロジェクト名確定
- [x] GitHub リポジトリ作成(public)
- [x] MEDIS の扱い確定(外す)
- [x] MVP スコープ確定
- [ ] 配布フォーマット最終決定(SQLite 単一ファイル + zstd 圧縮で進める前提)
- [ ] 更新頻度確定(月次 cron を基本、薬価改定 4 月や PMDA 随時更新への対応方針)
- [ ] `docs/plan.md` に計画詳細を起こす(本ログは履歴、plan は設計書)
- [ ] スキーマ設計(drugs / ingredients / diseases / aliases のテーブル設計)
- [ ] Codex に ETL スキャフォールド発注(sources/ / normalizer/ / build/ / GH Actions)

### 関連プロジェクト

- **DICTATION** (`/Users/tanimura/Desktop/DICTATION/`): 本プロジェクトの成果物(SQLite)を消費する予定。DICTATION 側の `CLAUDE.md` と `context/log.md` にも本分離の経緯を記録する。
- **TASK** (`/Users/tanimura/Desktop/TASK/`): 谷村の Vault。本プロジェクト発生の経緯は TASK 側の log にも一行記録する。

---

## 2026-04-21(追記: 設計書 + MVP スキャフォールド投入)

バックグラウンドエージェント(Opus)から Codex CLI に委譲して、設計書と MVP スキャフォールドを投入した。

### 作成ファイル一覧

- `docs/plan.md`(設計書、Opus が直接 Write。§1-§12 の章立て)
- `schema.sql`(drugs / ingredients / drug_ingredients / diseases / disease_aliases / icd10 / source_meta)
- `pyproject.toml`(setuptools、Python 3.11+、pandas/requests/lxml/bs4/jaconv/zstandard、dev: pytest)
- `justfile`(build / test / fetch-sources / make-dist / clean)
- `.gitignore`(/build/lib/ 限定で Python パッケージ `build/` を追跡対象に維持)
- `README.md`(簡潔版、詳細は plan.md 参照)
- `sources/{pmda_attachment,yakkakijun,ippanmei,manbyo,dpc_shobyomei}.py` + `__init__.py`(各 fetch/parse/run 実装、SOURCE_URL 定数化)
- `normalizer/{kana,dedupe,link}.py` + `__init__.py`(jaconv ベースの正規化、ソース優先順位付き重複解決、多対多リンク)
- `build/{build_sqlite,manifest}.py` + `__init__.py`(schema 適用 → dedupe/link → to_sql → VACUUM → zstd 圧縮、manifest.json 生成)
- `tests/{test_schema,test_normalizer,test_row_counts}.py` + `__init__.py`(スキーマ存在・正規化スナップショット・行数閾値)
- `.github/workflows/monthly-update.yml`(cron `0 3 1 * *` + workflow_dispatch、setup-python → install → build → test → manifest → softprops/action-gh-release@v2)
- `dist/.gitkeep`

### Codex への指示要旨

- 2 回に分けて発注:
  1. 初回: 全スキャフォールド一括。sources/normalizer/.github/schema.sql/pyproject/justfile/README/.gitignore を生成したところで時間切れに見える。
  2. 追加: build/ と tests/ のみ(既存ファイルを読み込んで整合性を取る前提)。
- 制約: CLAUDE.md / context/log.md / docs/plan.md は不可侵、git・依存解決・DL は一切禁止、`/Users/tanimura/Desktop/jp-med-dict/` 以外に触らない。
- 各 Python モジュールのカラム名・関数シグネチャは docs/plan.md §3〜§5 と整合させる。
- 全 17 Python ファイルが `python3 -c "import ast; ast.parse(...)"` でパースできることを事後検証済み。

### 未解決 / 次アクションの更新

- [x] `docs/plan.md` 起草(v0.1 draft)
- [x] スキーマ設計(schema.sql 確定)
- [x] Codex に ETL スキャフォールド発注(sources / normalizer / build / GH Actions / tests)
- [x] 配布フォーマット: SQLite + zstd + manifest.json(§6.3 仕様)で確定
- [x] 更新頻度: 月次 cron(1 日 03:00 UTC)+ 薬価改定 4/1 は workflow_dispatch 手動
- [ ] 初回 fetch を手動実行して `SOURCE_URL` 実在確認(別セッション)
- [ ] v0.1.0 の初回 Release を手動トリガ
- [ ] `LICENSE`(MIT)と `LICENSE-DATA`(CC BY-SA 4.0)のファイル化(v0.2)
- [ ] DICTATION 側の消費コード設計(別リポ)
- [ ] 手技 K コード・ICD-10 単独辞書・旧字体マッピングの追加(v0.2)
