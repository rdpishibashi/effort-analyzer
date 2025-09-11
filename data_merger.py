#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_merger.py - Data Merger Functions
統合工数データ処理とマージ機能
"""

import pandas as pd
import numpy as np
import re
import unicodedata
import os
import traceback
from datetime import datetime
from pathlib import Path


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
            # Web実行時は自動的に上書きしない（エラーで停止）
            if hasattr(existing_file_input, 'read'):
                print("Web実行時は重複データの上書きを行いません")
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


def process_integrated_workflow(existing_file_input, new_file_input, output_file_path, progress_callback=None):
    """
    統合ワークフロー: データマージから業務内容分割まで一括処理
    """
    try:
        if progress_callback:
            progress_callback(0.1, "月次データ処理中...")
        
        # 1. 月次データ処理
        print("\n=== 月次データ処理開始 ===")
        new_data = process_monthly_data(new_file_input)
        
        if new_data is None:
            print("月次データ処理に失敗しました")
            return None
        
        if progress_callback:
            progress_callback(0.3, "データマージ中...")
        
        # 2. データマージ
        print("\n=== データマージ開始 ===")
        merged_data = merge_effort_data(existing_file_input, new_data)
        
        if merged_data is None:
            print("データマージに失敗しました")
            return None
        
        if progress_callback:
            progress_callback(0.7, "業務内容分割中...")
        
        # 3. 業務内容分割
        print("\n=== 業務内容分割開始 ===")
        from data_processor import split_business_content
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