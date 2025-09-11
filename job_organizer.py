#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
job_organizer.py - 統合工数データ処理ツール
毎月の工数データファイルをmerged_effortsに追加し、業務内容を分割・整理する

Usage:
    streamlit run job_organizer.py  (Streamlitインターフェースで実行)
    python job_organizer.py <existing_merged_file> <new_monthly_file> <output_file>  (コマンドライン実行)
"""

import pandas as pd
import numpy as np
import re
import unicodedata
import os
import sys
import argparse
import traceback
import io
from datetime import datetime
from pathlib import Path

# Try importing streamlit, but don't fail if it's not installed (for CLI mode)
try:
    import streamlit as st
except ImportError:
    st = None


# 業務内容分割用の定数
COMPANY_NAMES = ['アドテック', 'オムロン', 'オンテック', 'キオクシア', 'キューセス', 'コムズ',
                 'ダイトロン', 'マイクロン', 'シマデン', '富士電機']
BUSINESS_TERMS = ['L室電動リフター', 'セミナー', 'その他', '安全規格対応', '機能安全',
                  '検図', '主事補研修', '生産中止', '打合せ', '会議']


def extract_year_month_from_date(date_str):
    """作業日から年と月を抽出する"""
    try:
        if pd.isna(date_str) or date_str == '':
            return None, None
        
        # 日付文字列をパース
        if isinstance(date_str, str):
            # 様々な日付形式に対応
            date_formats = ['%Y/%m/%d', '%Y-%m-%d', '%Y年%m月%d日']
            for fmt in date_formats:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    return int(date_obj.year), int(date_obj.month)
                except ValueError:
                    continue
        elif hasattr(date_str, 'year'):  # datetime object
            return int(date_str.year), int(date_str.month)
        
        return None, None
    except:
        return None, None


def process_monthly_data(monthly_file_input, sheet_name='日報データ'):
    """
    月次工数データファイルの日報データシートを処理してmerged_efforts形式に変換
    monthly_file_input: ファイルパス（文字列）またはBytesIOオブジェクト
    """
    try:
        # ファイル入力の種類を判定して適切に読み込み
        if hasattr(monthly_file_input, 'read'):
            # BytesIOオブジェクトの場合
            df = pd.read_excel(monthly_file_input, sheet_name=sheet_name, engine='openpyxl')
        else:
            # ファイルパスの場合
            df = pd.read_excel(monthly_file_input, sheet_name=sheet_name, engine='openpyxl')
        
        print(f"月次データ読み込み完了: {len(df)}行")
        print(f"元データのカラム: {list(df.columns)}")
        
        # 必要なカラムのマッピング
        column_mapping = {
            '従業員名': '従業員名',
            '作業時間': '作業時間_分',  # 一時的な名前
            'USER_FIELD_01': 'USER_FIELD_01',
            'USER_FIELD_02': 'USER_FIELD_02', 
            'USER_FIELD_03': 'USER_FIELD_03',
            'USER_FIELD_04': 'USER_FIELD_04',
            'USER_FIELD_05': 'USER_FIELD_05',
            '第1分類': '第1分類',
            '第2分類': '第2分類',
            '第3分類': '第3分類',
            'UNIT': 'UNIT',
            'MODULE': 'MODULE',
            '業務内容': '業務内容'
        }
        
        # 新しいデータフレームを作成
        processed_df = pd.DataFrame()
        
        # 作業日から年と月を抽出
        years = []
        months = []
        for date_val in df['作業日']:
            year, month = extract_year_month_from_date(date_val)
            years.append(year)  # 数字として格納
            months.append(month)  # 数字として格納
        
        processed_df['年'] = years
        processed_df['月'] = months
        
        # 他のカラムをマッピング
        for original_col, new_col in column_mapping.items():
            if original_col in df.columns:
                if original_col == '作業時間':
                    # 作業時間を60で割って時間単位に変換
                    processed_df['作業時間(h)'] = pd.to_numeric(df[original_col], errors='coerce') / 60
                else:
                    processed_df[new_col] = df[original_col]
            else:
                # カラムが存在しない場合は空文字で埋める
                if original_col == '作業時間':
                    processed_df['作業時間(h)'] = 0
                else:
                    processed_df[new_col] = ''
        
        # merged_effortsの期待されるカラム順序に合わせる
        expected_columns = [
            '年', '月', '従業員名', '作業時間(h)', 
            'USER_FIELD_01', 'USER_FIELD_02', 'USER_FIELD_03', 'USER_FIELD_04', 'USER_FIELD_05',
            '第1分類', '第2分類', '第3分類', 'UNIT', 'MODULE', '業務内容'
        ]
        
        # 不足しているカラムを空文字で追加
        for col in expected_columns:
            if col not in processed_df.columns:
                processed_df[col] = ''
        
        # カラム順序を合わせる
        processed_df = processed_df[expected_columns]
        
        # 無効なデータを除外
        # 1. 年または月が抽出できなかった行
        # 2. 作業時間(h)が0以下の行
        valid_rows = (processed_df['年'].notna()) & (processed_df['月'].notna()) & \
                    (pd.to_numeric(processed_df['作業時間(h)'], errors='coerce') > 0)
        
        before_filter = len(processed_df)
        processed_df = processed_df[valid_rows]
        after_filter = len(processed_df)
        
        print(f"フィルタリング: {before_filter}行 → {after_filter}行 ({before_filter - after_filter}行除外)")
        print(f"  - 作業時間0以下: {before_filter - after_filter}行除外")
        
        print(f"処理後のデータ: {len(processed_df)}行")
        print(f"年月の範囲: {processed_df['年'].unique()} - {processed_df['月'].unique()}")
        
        return processed_df
        
    except FileNotFoundError as e:
        print(f"月次データ処理エラー - ファイルが見つかりません: {e}")
        return None
    except ValueError as e:
        print(f"月次データ処理エラー - データ値エラー: {e}")
        return None
    except KeyError as e:
        print(f"月次データ処理エラー - 必要なカラムが見つかりません: {e}")
        return None
    except Exception as e:
        print(f"月次データ処理エラー: {e}")
        print(f"エラー詳細: {traceback.format_exc()}")
        return None


def merge_effort_data(existing_file_input, new_data_df):
    """
    既存のmerged_effortsファイルに新しいデータを追加
    existing_file_input: ファイルパス（文字列）またはBytesIOオブジェクト
    """
    try:
        # ファイル入力の種類を判定して適切に読み込み
        if hasattr(existing_file_input, 'read'):
            # BytesIOオブジェクトの場合
            existing_df = pd.read_excel(existing_file_input, engine='openpyxl')
        else:
            # ファイルパスの場合
            existing_df = pd.read_excel(existing_file_input)
        
        print(f"既存データ読み込み完了: {len(existing_df)}行")
        
        # 既存データのクリーニング
        # 1. 年と月を数字に統一
        existing_df['年'] = pd.to_numeric(existing_df['年'], errors='coerce').astype('Int64')
        existing_df['月'] = pd.to_numeric(existing_df['月'], errors='coerce').astype('Int64')
        
        # 2. 作業時間が0以下のデータを除外
        before_existing = len(existing_df)
        existing_df = existing_df[
            (pd.to_numeric(existing_df['作業時間(h)'], errors='coerce') > 0) &
            (existing_df['年'].notna()) & (existing_df['月'].notna())
        ]
        after_existing = len(existing_df)
        
        print(f"既存データクリーニング: {before_existing}行 → {after_existing}行 ({before_existing - after_existing}行除外)")
        
        print(f"既存データの年月範囲:")
        existing_year_months = existing_df.groupby(['年', '月']).size()
        for (year, month), count in existing_year_months.items():
            print(f"  {year}-{month}: {count}行")
        
        # 重複チェック（年月の組み合わせ）
        # 既存データと新しいデータの年月を比較
        new_year_months = set(zip(new_data_df['年'], new_data_df['月']))
        existing_year_months_set = set(zip(existing_df['年'], existing_df['月']))
        
        overlapping = new_year_months.intersection(existing_year_months_set)
        if overlapping:
            print(f"警告: 重複する年月があります: {overlapping}")
            # Streamlit実行時は自動的に上書きしない（エラーで停止）
            if hasattr(existing_file_input, 'read'):
                print("Streamlit実行時は重複データの上書きを行いません")
                return None
            else:
                # CLI実行時のみユーザーに確認
                print("既存データを上書きしますか？")
                response = input("Y/N: ")
                if response.upper() != 'Y':
                    print("処理を中止します")
                    return None
            
            # 重複する年月のデータを既存データから削除
            for year, month in overlapping:
                mask = (existing_df['年'] == year) & (existing_df['月'] == month)
                existing_df = existing_df[~mask]
                print(f"既存データから {year}-{month} のデータを削除しました")
        
        # データを結合
        merged_df = pd.concat([existing_df, new_data_df], ignore_index=True)
        
        # 年月でソート
        merged_df = merged_df.sort_values(['年', '月', '従業員名'])
        
        print(f"マージ完了: {len(merged_df)}行")
        
        return merged_df
        
    except FileNotFoundError as e:
        print(f"データマージエラー - ファイルが見つかりません: {e}")
        return None
    except ValueError as e:
        print(f"データマージエラー - データ値エラー: {e}")
        return None
    except KeyError as e:
        print(f"データマージエラー - 必要なカラムが見つかりません: {e}")
        return None
    except Exception as e:
        print(f"データマージエラー: {e}")
        print(f"エラー詳細: {traceback.format_exc()}")
        return None


# 業務内容分割関連の関数
def normalize_text(s: str) -> str:
    """Convert fullwidth alphanumeric and symbols to halfwidth."""
    if pd.isna(s): return ""
    return unicodedata.normalize('NFKC', str(s))


def extract_parentheses_content(text):
    """
    括弧内の内容を抽出し、括弧外のテキストと分離する（スタックベース実装）。
    入れ子括弧に対応し、最も外側の括弧の内容を1単位として抽出する。
    """
    if not text: return "", []
    stack = []; matches = []
    opening_brackets = {'(': ')', '（': '）', '【': '】'}
    closing_brackets = {')': '(', '）': '（', '】': '【'}
    for i, char in enumerate(text):
        if char in opening_brackets: stack.append((i, char))
        elif char in closing_brackets:
            if stack and stack[-1][1] == closing_brackets[char]:
                start_index, _ = stack.pop(); matches.append((start_index, i))
    if not matches: return text, []
    matches.sort(key=lambda x: (x[0], -x[1]))
    top_level_matches = []; covered_indices = set()
    for start, end in matches:
        current_range_set = set(range(start, end + 1))
        if not current_range_set.intersection(covered_indices):
            top_level_matches.append((start, end))
            covered_indices.update(current_range_set)
    paren_content = [text[start + 1 : end] for start, end in top_level_matches if text[start + 1 : end]]
    indices_to_remove = set().union(*(set(range(start, end + 1)) for start, end in top_level_matches))
    cleaned_buffer = []; space_added = False
    for i, char in enumerate(text):
        if i not in indices_to_remove: cleaned_buffer.append(char); space_added = False
        elif not space_added: cleaned_buffer.append(' '); space_added = True
    cleaned_text = "".join(cleaned_buffer)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    cleaned_text = re.sub(r"^[()\（\）\[\]【】{}<>《》]+|[()\（\）\[\]【】{}<>《》]+$", '', cleaned_text).strip()
    return cleaned_text, paren_content


def is_special_mixed_pattern(text):
    """特殊な日本語と英語の混在パターンをチェック"""
    if not text or len(text) < 2: return False
    jp_chars = re.findall(r'[ぁ-んァ-ヶー一-龠々]', text)
    en_chars = re.findall(r'[A-Za-z]', text)
    if not jp_chars or not en_chars: return False
    if re.match(r'^[A-Za-z][ぁ-んァ-ヶー一-龠々]', text): return True
    if re.match(r'^[ぁ-んァ-ヶー一-龠々]+[A-Za-z]$', text): return True
    return False


def split_english_japanese(text):
    """
    特定の接続記号で繋がっているか、特殊なパターンかをチェックする。
    それ以外の場合、基本的には分割しない。
    """
    if not text: return []
    connectors_pattern = r"[-/\uff0f→・･.\uff0e《》?\uff1f⇔ー]"
    if re.search(connectors_pattern, text): return [text]
    if is_special_mixed_pattern(text): return [text]
    return [text]


def split_tasks(cell_value, user_fields):
    """業務内容セルをタスクに分割"""
    if pd.isna(cell_value): return []
    text = normalize_text(str(cell_value))
    main_text, paren_contents = extract_parentheses_content(text)
    initial_parts = re.split(r'[_ 　]+', main_text)
    main_tasks = []
    for part in initial_parts:
        part = part.strip();
        if not part: continue
        subparts = split_english_japanese(part)
        for subpart in subparts:
            subpart = subpart.strip()
            if subpart and subpart not in user_fields and subpart not in main_tasks:
                 main_tasks.append(subpart)
    paren_tasks = []
    for content in paren_contents:
        content = content.strip()
        if content and content not in paren_tasks: paren_tasks.append(content)
    combined_tasks = main_tasks + paren_tasks
    final_filtered_tasks = []
    i = 0
    while i < len(combined_tasks):
        task = combined_tasks[i]
        if task == '会議' and i + 1 < len(combined_tasks) and combined_tasks[i+1] in ('Non-Essential', 'Essential'): i += 2
        else: final_filtered_tasks.append(task); i += 1
    final_tasks = []; seen_tasks = set()
    punctuation_pattern = r'^[,、.。．:;\'"]+|[,、.。．:;\'"]+$'
    for task in final_filtered_tasks:
        task = re.sub(punctuation_pattern, '', task)
        task = task.strip()
        if task and task not in seen_tasks:
             final_tasks.append(task); seen_tasks.add(task)
    return final_tasks


def split_business_content(df):
    """
    データフレーム内の業務内容を分割して業務内容1〜10のカラムに展開
    """
    print("業務内容分割処理開始...")
    
    # 新しいカラムを準備
    for i in range(1, 11):
        df[f'業務内容{i}'] = ''
    
    total_rows = len(df)
    processed_rows = 0
    
    for index, row in df.iterrows():
        # USER_FIELDから重複除外用のリストを作成
        user_fields = []
        for field in ['USER_FIELD_01', 'USER_FIELD_02', 'USER_FIELD_03']:
            if field in row and not pd.isna(row[field]):
                user_field_value = normalize_text(str(row[field]))
                if user_field_value:
                    user_fields.append(user_field_value)
        
        # 業務内容を分割
        tasks = split_tasks(row['業務内容'], user_fields)
        
        # 業務内容1〜10に割り当て
        for task_index, task in enumerate(tasks[:10], 1):
            df.at[index, f'業務内容{task_index}'] = task
        
        # 10を超える場合は新しいカラムを追加
        if len(tasks) > 10:
            for task_index, task in enumerate(tasks[10:], 11):
                col_name = f'業務内容{task_index}'
                if col_name not in df.columns:
                    df[col_name] = ''
                df.at[index, col_name] = task
        
        processed_rows += 1
        if processed_rows % 1000 == 0:
            print(f"業務内容分割進捗: {processed_rows}/{total_rows}行 ({processed_rows/total_rows*100:.1f}%)")
    
    print(f"業務内容分割完了: {processed_rows}行処理")
    
    # 最終的なカラム順序を整理
    base_columns = [
        '年', '月', '従業員名', '作業時間(h)', 
        'USER_FIELD_01', 'USER_FIELD_02', 'USER_FIELD_03', 'USER_FIELD_04', 'USER_FIELD_05',
        '第1分類', '第2分類', '第3分類', 'UNIT', 'MODULE', '業務内容'
    ]
    
    # 業務内容カラムを追加
    task_columns = [col for col in df.columns if col.startswith('業務内容') and col != '業務内容']
    task_columns.sort(key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0)
    
    final_columns = base_columns + task_columns
    
    # 存在するカラムのみを選択
    existing_columns = [col for col in final_columns if col in df.columns]
    df = df[existing_columns]
    
    return df


def save_merged_data(merged_df, output_file_path):
    """
    マージされたデータをExcelファイルとして保存
    """
    try:
        # バックアップファイル名を生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = output_file_path.replace('.xlsx', f'_backup_{timestamp}.xlsx')
        
        # 元ファイルが存在する場合はバックアップを作成
        if os.path.exists(output_file_path):
            os.rename(output_file_path, backup_path)
            print(f"既存ファイルをバックアップしました: {backup_path}")
        
        # 新しいファイルを保存
        merged_df.to_excel(output_file_path, index=False)
        print(f"最終結果を保存しました: {output_file_path}")
        
        return True
        
    except Exception as e:
        print(f"ファイル保存エラー: {e}")
        return False


def process_integrated_workflow_streamlit(existing_file_obj, new_file_obj, output_file_path, progress_callback=None):
    """
    Streamlit用統合ワークフロー: BytesIOオブジェクトからデータマージから業務内容分割まで一括処理
    """
    try:
        if progress_callback:
            progress_callback(0.1, "月次データ処理中...")
        
        # 1. 月次データ処理（BytesIOオブジェクトを渡す）
        print("\n=== 月次データ処理開始 ===")
        new_data = process_monthly_data(new_file_obj)
        
        if new_data is None:
            print("月次データ処理に失敗しました")
            return None
        
        if progress_callback:
            progress_callback(0.3, "データマージ中...")
        
        # 2. データマージ（BytesIOオブジェクトを渡す）
        print("\n=== データマージ開始 ===")
        merged_data = merge_effort_data(existing_file_obj, new_data)
        
        if merged_data is None:
            print("データマージに失敗しました")
            return None
        
        if progress_callback:
            progress_callback(0.7, "業務内容分割中...")
        
        # 3. 業務内容分割
        print("\n=== 業務内容分割開始 ===")
        final_data = split_business_content(merged_data)
        
        if progress_callback:
            progress_callback(0.9, "ファイル保存中...")
        
        # 4. ファイル保存
        print("\n=== ファイル保存開始 ===")
        if save_merged_data(final_data, output_file_path):
            if progress_callback:
                progress_callback(1.0, "処理完了")
            print("\n✅ 全体処理が正常に完了しました！")
            return final_data
        else:
            print("\n❌ ファイル保存に失敗しました")
            return None
            
    except Exception as e:
        print(f"統合処理エラー: {e}")
        traceback.print_exc()
        return None


def process_integrated_workflow(existing_file_path, new_file_path, output_file_path, progress_callback=None):
    """
    統合ワークフロー: データマージから業務内容分割まで一括処理
    """
    try:
        if progress_callback:
            progress_callback(0.1, "月次データ処理中...")
        
        # 1. 月次データ処理
        print("\n=== 月次データ処理開始 ===")
        new_data = process_monthly_data(new_file_path)
        
        if new_data is None:
            print("月次データ処理に失敗しました")
            return None
        
        if progress_callback:
            progress_callback(0.3, "データマージ中...")
        
        # 2. データマージ
        print("\n=== データマージ開始 ===")
        merged_data = merge_effort_data(existing_file_path, new_data)
        
        if merged_data is None:
            print("データマージに失敗しました")
            return None
        
        if progress_callback:
            progress_callback(0.7, "業務内容分割中...")
        
        # 3. 業務内容分割
        print("\n=== 業務内容分割開始 ===")
        final_data = split_business_content(merged_data)
        
        if progress_callback:
            progress_callback(0.9, "ファイル保存中...")
        
        # 4. ファイル保存
        print("\n=== ファイル保存開始 ===")
        if save_merged_data(final_data, output_file_path):
            if progress_callback:
                progress_callback(1.0, "処理完了")
            print("\n✅ 全体処理が正常に完了しました！")
            return final_data
        else:
            print("\n❌ ファイル保存に失敗しました")
            return None
            
    except Exception as e:
        print(f"統合処理エラー: {e}")
        traceback.print_exc()
        return None


def run_streamlit():
    """Streamlitインターフェースを実行"""
    if not st: 
        print("Streamlit 未インストール"); 
        return

    st.set_page_config(page_title="統合工数データ処理ツール", layout="wide")
    st.title("統合工数データ処理ツール")
    st.write("毎月の工数データファイルをmerged_effortsに追加し、業務内容を分割・整理します。")
    
    # ファイルアップロード
    st.subheader("1. ファイルを選択してください")
    
    existing_file = st.file_uploader(
        "既存のmerged_effortsファイル", 
        type=['xlsx'], 
        key="existing"
    )
    
    new_file = st.file_uploader(
        "新しい月次工数データファイル", 
        type=['xlsx'], 
        key="new"
    )
    
    if existing_file and new_file:
        st.subheader("2. ファイル情報")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**既存ファイル**")
            try:
                existing_df = pd.read_excel(existing_file)
                
                # 既存データのクリーニング
                existing_df['年'] = pd.to_numeric(existing_df['年'], errors='coerce').astype('Int64')
                existing_df['月'] = pd.to_numeric(existing_df['月'], errors='coerce').astype('Int64')
                
                # 作業時間が0以下のデータを除外
                before_count = len(existing_df)
                existing_df = existing_df[
                    (pd.to_numeric(existing_df['作業時間(h)'], errors='coerce') > 0) &
                    (existing_df['年'].notna()) & (existing_df['月'].notna())
                ]
                after_count = len(existing_df)
                
                st.write(f"行数: {after_count:,} (作業時間0除外: {before_count - after_count:,}件)")
                
                # 年月範囲表示
                year_month_stats = existing_df.groupby(['年', '月']).size().reset_index(name='件数')
                st.dataframe(year_month_stats)
                
            except Exception as e:
                st.error(f"既存ファイルの読み込みエラー: {e}")
        
        with col2:
            st.write("**新しいファイル**")
            try:
                sheets = pd.ExcelFile(new_file).sheet_names
                st.write(f"シート数: {len(sheets)}")
                if '日報データ' in sheets:
                    st.success("✅ 日報データシートあり")
                    new_df = pd.read_excel(new_file, sheet_name='日報データ')
                    st.write(f"行数: {len(new_df):,}")
                else:
                    st.warning("⚠️ 日報データシートが見つかりません")
                    st.write("利用可能なシート:", sheets)
                    
            except Exception as e:
                st.error(f"新しいファイルの読み込みエラー: {e}")
        
        # 処理実行
        st.subheader("3. 統合処理")
        
        if st.button("データ処理開始", type="primary"):
            try:
                # プログレスバー
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                
                def update_progress(progress, status):
                    progress = float(max(0.0, min(1.0, progress)))
                    progress_bar.progress(progress)
                    status_text.text(status)
                
                # ファイルをBytesIOとして直接処理
                existing_file.seek(0)  # ファイルポインタを先頭にリセット
                new_file.seek(0)       # ファイルポインタを先頭にリセット
                
                # 統合処理実行（BytesIOオブジェクトを直接渡す）
                output_filename = f"organized_efforts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                
                final_data = process_integrated_workflow_streamlit(
                    existing_file, 
                    new_file, 
                    output_filename,
                    progress_callback=update_progress
                )
                
                if final_data is not None:
                    st.success("✅ 統合処理完了！")
                    
                    # 結果をダウンロード可能にする
                    with open(output_filename, "rb") as f:
                        st.download_button(
                            label="📥 処理済みファイルをダウンロード",
                            data=f.read(),
                            file_name=output_filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    
                    # プレビュー表示
                    st.subheader("4. 結果プレビュー")
                    st.dataframe(final_data.head(10))
                    
                    # 統計情報
                    st.subheader("5. 統計情報")
                    stats = final_data.groupby(['年', '月']).agg({
                        '従業員名': 'nunique',
                        '作業時間(h)': 'sum'
                    }).reset_index()
                    stats.columns = ['年', '月', 'ユニーク従業員数', '総作業時間(h)']
                    st.dataframe(stats)
                    
                    # 業務内容分割統計
                    task_columns = [col for col in final_data.columns if col.startswith('業務内容') and col != '業務内容']
                    if task_columns:
                        st.subheader("6. 業務内容分割統計")
                        task_stats = {}
                        for col in task_columns:
                            non_empty_count = final_data[col].notna().sum()
                            task_stats[col] = non_empty_count
                        
                        task_stats_df = pd.DataFrame(list(task_stats.items()), columns=['カラム', '非空データ数'])
                        st.dataframe(task_stats_df)
                else:
                    st.error("❌ 処理に失敗しました")
                
                # 出力ファイル削除（ダウンロード後）
                if os.path.exists(output_filename):
                    os.remove(output_filename)
                        
            except Exception as e:
                st.error(f"処理エラー: {e}")
                traceback.print_exc()
    
    with st.expander("使い方と処理内容の詳細"):
        st.markdown("""
        ### このアプリの使い方
        
        1. **既存のmerged_effortsファイル**: 過去の工数データが統合されたExcelファイル
        2. **新しい月次工数データファイル**: 新しく追加したい月の工数データ（日報データシートを含む）
        3. 処理により以下が実行されます：
           - 新しいデータを既存データにマージ
           - 重複チェック
           - 作業時間0のデータ除外
           - 業務内容の分割・整理
        4. 処理結果はExcelファイルとしてダウンロードできます
        
        ### 処理内容詳細
        
        **データマージ処理:**
        - 作業日から年・月を抽出
        - 作業時間を分から時間に変換
        - データ型統一（年・月を数字型）
        - 重複データのチェック
        
        **業務内容分割処理:**
        - 業務内容をアンダースコア、スペースなどで分割
        - 括弧内の内容を個別項目として抽出
        - 英単語と日本語の混在文字列を処理
        - 重複項目の削除
        - 業務内容1〜10以上のカラムに展開
        """)


def run_cli(existing_path, new_path, output_path):
    """コマンドライン実行"""
    if not existing_path or not new_path or not output_path:
        print("エラー: 入出力ファイル指定が必要です")
        sys.exit(1)
    
    print(f"既存ファイル: {existing_path}")
    print(f"新しいファイル: {new_path}")
    print(f"出力ファイル: {output_path}")
    
    # ファイル存在確認
    if not os.path.exists(existing_path):
        print(f"エラー: 既存ファイルが見つかりません: {existing_path}")
        sys.exit(1)
    
    if not os.path.exists(new_path):
        print(f"エラー: 新しいファイルが見つかりません: {new_path}")
        sys.exit(1)
    
    try:
        # 統合処理実行
        final_data = process_integrated_workflow(existing_path, new_path, output_path)
        
        if final_data is not None:
            print("\n✅ 処理が正常に完了しました！")
            print(f"結果ファイル: {output_path}")
            print(f"最終データ行数: {len(final_data):,}")
        else:
            print("\n❌ 処理に失敗しました")
            sys.exit(1)
            
    except Exception as e:
        print(f"エラー: 処理中に予期せぬエラー: {e}")
        traceback.print_exc()
        sys.exit(1)


def parse_args():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(
        description='統合工数データ処理ツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  streamlit run job_organizer.py
  
  python job_organizer.py existing_merged.xlsx new_monthly.xlsx output.xlsx
        """
    )
    
    parser.add_argument('existing_file', nargs='?', help='既存のmerged_effortsファイル')
    parser.add_argument('new_file', nargs='?', help='新しい月次工数データファイル')
    parser.add_argument('output_file', nargs='?', help='出力ファイル名')
    
    return parser.parse_args()


def main():
    """メイン関数: コマンドライン引数に基づいて実行モードを判断"""
    args = parse_args()
    
    # 引数が全て指定されていれば CLI モード
    if args.existing_file and args.new_file and args.output_file:
        run_cli(args.existing_file, args.new_file, args.output_file)
    # 引数が指定されていない場合は Streamlit モードを試みる
    else:
        if st:
            run_streamlit()
        else:
            print("Streamlit がインストールされていないようです。")
            print("\nコマンドライン実行には以下の引数が必要です。")
            print(f"使用法: python {os.path.basename(sys.argv[0])} <existing_file> <new_file> <output_file>")
            print("\nまたは、Streamlitをインストールして実行してください:")
            print(f"  pip install streamlit")
            print(f"  streamlit run {os.path.basename(sys.argv[0])}")
            sys.exit(1)


if __name__ == "__main__":
    main()