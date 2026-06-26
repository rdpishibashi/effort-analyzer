# Effort-analyzer 技術文書

## 1. システム概要

ULVAC電設管理向けの**月次工数データ統合・分析ツール**。  
2つの機能を1つのStreamlitアプリに統合している。

| 機能 | 役割 |
|------|------|
| **Job Organizer** | 月次工数Excelを既存の統合ファイルに追記し、業務内容を分割整理する |
| **Analysis Viewer** | 統合済みデータをフィルタリング・集計・グラフ表示する |

---

## 2. ファイル構成

```
Effort-analyzer/
├── app.py               エントリポイント。ページ設定とメイン呼び出し
├── web_interface.py     Streamlit UI全体（タブ・フィルター・グラフ）
├── analysis_viewer.py   分析ロジック（フィルター適用・集計・グラフ生成）
├── data_merger.py       マージロジック（月次データ変換・重複チェック・保存）
├── data_processor.py    業務内容分割ロジック・データ読み込み
├── job_organizer.py     CLIエントリポイント（コマンドライン実行用）
├── requirements.txt     依存パッケージ
├── spec-*.txt           要求仕様書（原典）
└── TECHNICAL.md         本文書
```

### 依存関係

```
app.py
  └── web_interface.py
        ├── analysis_viewer.py   （分析・集計・グラフ）
        ├── data_merger.py       （統合ワークフロー）
        └── data_processor.py   （データ読み込み）

data_merger.py
  └── data_processor.py         （業務内容分割）
```

---

## 3. データフロー

### 3-1. Job Organizer フロー

```
[既存統合ファイル]  [新規月次ファイル]
        ↓                  ↓
   merge_effort_data ← process_monthly_data
   （重複チェック・concat）  （日報データシート読込・
                              分単位→時間変換・
                              年月抽出）
        ↓
   split_business_content
   （業務内容 → 業務内容1〜N に展開）
        ↓
   save_merged_data
   （既存ファイルをタイムスタンプ付きバックアップ後に上書き）
        ↓
   [統合済みExcelファイル]
```

### 3-2. Analysis Viewer フロー

```
[Excelファイルアップロード]
        ↓
   load_data_from_source
   （全シート結合）
        ↓
   apply_filters（日付範囲 + カスケードフィルター + WBS要素フィルター）
        ↓
   get_nonempty_business_columns
   （全空白の業務内容Xカラムを除外）
        ↓
   aggregate_data
   （group_cols × 作業時間(h) の合計）
        ↓
   [集計テーブル表示 + 棒グラフ]
```

---

## 4. モジュール詳細

### 4-1. `analysis_viewer.py`

#### 定数

| 定数 | 値 | 用途 |
|------|----|------|
| `BLANK_STR` | `"[空白]"` | フィルター選択肢の空白値表示 |
| `BASE_COLUMN_ORDER` | USER_FIELD_01〜03, 業務内容1〜5 | フィルター・グループ化の基本列順序 |
| `UNIT_COL` | `"WBS要素(代入)"` | WBS要素カラムの列名 |
| `EFFORT_COL` | `"作業時間(h)"` | 集計対象カラムの列名 |

#### 主要関数

**`get_available_columns(df)`**  
`BASE_COLUMN_ORDER` に含まれる列をdfから抽出し、さらにdf中に存在する `業務内容6` 以降のカラムを番号順に追加して返す。フィルター・グループ化に使用する列リストの基本形。

**`get_nonempty_business_columns(df, columns)`**  
`columns` のうち `業務内容X` カラムについて、`df` 内にNaN・空文字以外の値が1件でもあるもののみを残す。全空白カラムを表示から除外する目的で使用。

**`apply_filters(df, filters, date_range)`**  
- `date_range`: `{'start': (year, month), 'end': (year, month)}` 形式の辞書  
- `filters`: `{列名: [選択値, ...]}` の辞書。`BLANK_STR` はNaNとして扱う  
- 日付範囲 → 通常フィルターの順で適用する

**`get_grouping_columns(available_columns, applied_filters)`**  
「最後にフィルターが設定された列」の**次の列以降**をグループ化列として返す（カスケード集計の実装）。フィルターが何もなければ `available_columns` 全体を返す。

**`aggregate_data(df, group_cols, effort_col)`**  
`groupby(group_cols, dropna=False)` で集計。空白値は `BLANK_STR` で表示。

**`create_plot_data(df, group_cols, effort_col, num_items, ...)`**  
グループ化列を ` / ` で結合した「項目」列を追加し、表示件数で切り捨てる。タイトルは「上位N件の作業時間」または「すべての作業時間」。

---

### 4-2. `data_processor.py`

#### 業務内容分割ロジック（`split_tasks`）

分割は以下の順で実施する。

1. **全角→半角正規化** (`normalize_text`): `unicodedata.normalize('NFKC', ...)`
2. **括弧抽出** (`extract_parentheses_content`):  
   - `(`, `（`, `【` を開き括弧として認識（入れ子対応）  
   - 最外括弧の**内容**を別リストに抽出し、括弧ごと本文から除去  
   - 括弧内は内容全体を1トークンとして扱う（内部の空白・カンマで分割しない）
3. **アンダースコア・空白分割**: `re.split(r'[_ 　]+', main_text)`
4. **英日混在チェック** (`split_english_japanese`):  
   - 接続記号（`-/→・.` 等）で繋がる文字列は分割しない  
   - 英字と日本語が隣接している特殊パターンも分割しない
5. **後処理フィルター**:  
   - `USER_FIELD_01〜03` と同一の単語を除去  
   - 「会議 + Non-Essential/Essential」の組み合わせを除去  
   - 重複排除  
   - 先頭・末尾の記号・括弧の片割れを除去

#### `split_business_content(df)`

行ごとに `split_tasks` を呼び出し、結果を `業務内容1`, `業務内容2`, ... に格納。10件を超えた場合は列を動的追加。処理後にカラム順序を整理して返す。

> **注意**: 現在の `split_business_content` は `COMPANY_NAMES` / `BUSINESS_TERMS` 定数（`data_merger.py` で定義）を直接参照していない。これらの定数は将来の会社名・業務語分割機能の拡張用として保持されているが、現バージョンでは分割ロジックに未統合。

---

### 4-3. `data_merger.py`

**`process_monthly_data(monthly_file_input)`**  
- シート名 `日報データ` を読み込む  
- `作業時間` (分) → `作業時間(h)` (時間) に変換（÷60）  
- `作業日` から年・月を抽出（`%Y/%m/%d`, `%Y-%m-%d`, `%Y年%m月%d日` 形式に対応）  
- 作業時間0以下・年月不明の行を除外

**`merge_effort_data(existing_file_input, new_data_df)`**  
- 既存ファイルの年・月の重複チェック  
- **Web（Streamlit）実行時は重複があった場合にエラー終了**（上書きしない仕様）  
- CLI実行時は重複年月のデータを既存側から削除してマージ

**`process_integrated_workflow(..., progress_callback)`**  
Job Organizer の全処理をまとめたオーケストレーター関数。進捗コールバックで0〜1.0の進捗を通知。

---

### 4-4. `web_interface.py`

#### フィルター実装の詳細

サイドバーで以下の順序でフィルターを構築する。

```
1. 日付範囲スライダー（st.select_slider）
   └─ デフォルト: 直近6ヶ月（末尾インデックスから -5）
   └─ セッション状態の値がデータの選択肢にない場合は自動クリア

2. カスケードフィルター（available_columnsの順で）
   └─ 各列: get_unique_values_with_blank(filtered_df, col)
   └─ 選択肢が[空白]のみの業務内容Xはスキップ
   └─ フィルター選択のたびに filtered_df を更新（カスケード効果）

3. WBS要素フィルター（非カスケード・AND条件）
   └─ 全データ(df)から選択肢を生成（カスケードに影響しない）
```

#### カスケード集計の仕組み

| 状況 | グループ化列 |
|------|-------------|
| フィルター未選択 | available_columns 全体 |
| USER_FIELD_01 を選択 | USER_FIELD_02 以降 |
| USER_FIELD_02 を選択 | USER_FIELD_03 以降 |
| 業務内容2 まで選択 | 業務内容3 以降 |

---

## 5. 入力ファイル仕様

### 統合済みファイル（既存ファイル）

| カラム名 | 型 | 備考 |
|----------|----|------|
| 年 | 整数 | 数値型に変換される |
| 月 | 整数 | 数値型に変換される |
| 従業員名 | 文字列 | |
| 作業時間(h) | 浮動小数点 | 0以下は除外 |
| USER_FIELD_01〜05 | 文字列 | |
| 第1〜3分類 | 文字列 | |
| UNIT | 文字列 | ※入力ファイルのカラム名は UNIT のまま |
| MODULE | 文字列 | |
| 業務内容 | 文字列 | 分割前の原文 |
| 業務内容1〜N | 文字列 | 分割済み |

### 月次ファイル（新規追加ファイル）

- シート名: `日報データ`
- `作業時間` カラムは**分単位**（時間変換は処理内で実施）
- `作業日` カラムから年・月を自動抽出

> **注意**: 入力ファイルの `UNIT` カラムは、Analysis Viewer では `WBS要素(代入)` という列名で参照される（`UNIT_COL = "WBS要素(代入)"`）。入力データのカラム名と定数値が一致しないと WBS要素フィルターが機能しない。入力ファイルのカラム名変更が必要な場合は `analysis_viewer.py` の `UNIT_COL` を変更するか、`data_merger.py` の `process_monthly_data` でカラムをリネームする。

---

## 6. セッション状態の管理

| キー | 格納内容 | 設定タイミング |
|------|----------|----------------|
| `latest_processed_data` | Job Organizer処理後のDataFrame | 処理完了時 |
| `show_analysis` | 分析ビューアへの切り替えフラグ | 処理完了時 |
| `current_tab` | 現在のタブ（`"organizer"` / `"analysis"`） | タブ切り替え時 |
| `date_range_slider` | スライダーの選択値タプル | スライダー操作時 |
| `filter_{col}` | 各フィルターの選択値リスト | フィルター操作時 |

`date_range_slider` はデータファイルが変わった際に選択肢が変わるため、セッション状態の値が現在の選択肢に存在しない場合は `web_interface.py` の `show_analysis_filters_and_charts` 内で自動的に削除される。

---

## 7. 既知の制約・注意事項

### 重複年月の扱い
Streamlit（Web）実行では、追加しようとする月次データの年月が既存データに含まれている場合、**エラーで処理を中断**する。上書きが必要な場合はCLI実行（`job_organizer.py`）を使用する。

### 業務内容分割の上限
`split_business_content` は10件を超えた場合に列を動的追加するが、`BASE_COLUMN_ORDER` には `業務内容5` までしか含まれていない。`get_available_columns` で動的に追加される仕組みにより、実データに `業務内容6` 以降が存在すれば自動的にフィルター・集計対象に含まれる。

### 集計エクスポートのカラム
`aggregate_by_year_month_person` は `'UNIT'` というカラム名をハードコードで参照している（`UNIT_COL` 定数を使用していない）。分析用の `UNIT_COL` が変更になった場合はこの関数も合わせて修正が必要。

### `COMPANY_NAMES` / `BUSINESS_TERMS` 定数
`data_merger.py` に定義されているが、現バージョンの `split_tasks` では参照されていない。将来の分割ロジック拡張のためのリスト。

---

## 8. 機能拡張ガイド

### 業務内容の分割ルールを変更したい場合

`data_processor.py` の `split_tasks` 関数を変更する。  
主な変更ポイント:
- **デリミター追加**: `re.split(r'[_ 　]+', ...)` のパターンを拡張
- **除外語追加**: `data_merger.py` の `BUSINESS_TERMS` に追加し、`split_tasks` 内で参照するロジックを追加
- **会社名リスト更新**: `data_merger.py` の `COMPANY_NAMES` を編集し、`split_tasks` 内で参照

### フィルター対象カラムを追加したい場合

`analysis_viewer.py` の `BASE_COLUMN_ORDER` に追加する。  
ただし `業務内容X` は動的に自動追加されるため変更不要。

```python
BASE_COLUMN_ORDER = [
    "USER_FIELD_01", "USER_FIELD_02", "USER_FIELD_03",
    "業務内容1", "業務内容2", "業務内容3", "業務内容4", "業務内容5",
    # 追加したいカラムをここに追記
]
```

### 月次ファイルのシート名・カラム名が変わった場合

`data_merger.py` の `process_monthly_data` 内の `column_mapping` と `sheet_name` 引数を変更する。

### WBS要素カラムの名称が変わった場合

`analysis_viewer.py` の `UNIT_COL` 定数を変更する。合わせて `aggregate_by_year_month_person` 内のハードコード `'UNIT'` も修正が必要。

```python
# analysis_viewer.py
UNIT_COL = "WBS要素(代入)"  # ← ここを変更

# aggregate_by_year_month_person 内（別途修正が必要）
for col in [UNIT_COL, 'MODULE']:   # UNIT_COL を参照しているが...
    ...
# ※ aggregate_by_year_month_person の group_cols 構築部分は
#    現状 UNIT_COL を参照済み。ただし他の文字列参照が残っていないか確認すること。
```

### 作業時間以外の指標を集計したい場合

`analysis_viewer.py` の `EFFORT_COL` 定数を変更するか、`aggregate_data` の呼び出し時に引数で指定する。

### 集計エクスポートに列を追加したい場合

`analysis_viewer.py` の `aggregate_by_year_month_person` の `group_cols` リストを編集する。

---

## 9. 実行方法

```bash
# Streamlit起動
cd Effort-analyzer/
streamlit run app.py

# CLI実行（Job Organizerのみ）
python job_organizer.py --help
python job_organizer.py <既存統合ファイル.xlsx> <新規月次ファイル.xlsx> <出力ファイル.xlsx>
```

---

## 10. 改訂履歴

| 日付 | 変更内容 |
|------|----------|
| 2026-05-19 | `UNIT` フィルターを `WBS要素(代入)` に変更 |
| 2026-05-19 | `use_container_width` を `width='stretch'` に置換（Streamlit警告対応） |
| 2026-05-19 | 日付範囲フィルターをセレクトボックスからスライダーに変更（デフォルト直近6ヶ月） |
| 2026-05-19 | フィルター後に全空白の業務内容Xカラムを表示・集計から除外 |
| 2026-05-19 | `get_available_columns` で業務内容6以降を動的に追加するよう拡張 |
| 2026-05-19 | グラフタイトルからカラム名列挙の括弧部分を削除 |
