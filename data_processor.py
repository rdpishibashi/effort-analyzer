#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_processor.py - 業務内容分割処理とデータ処理共通機能
"""

import pandas as pd
import numpy as np
import re
import unicodedata


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


def load_data_from_source(source):
    """データソースから工数データを読み込む"""
    try:
        if hasattr(source, 'read'):
            # ファイルオブジェクトの場合
            excel_data = pd.read_excel(source, sheet_name=None)
        else:
            # ファイルパスの場合
            excel_data = pd.read_excel(source, sheet_name=None)
        
        # 全てのシートを結合
        df = pd.concat(excel_data.values(), ignore_index=True)
        df.columns = df.columns.str.strip()
        
        return df
    except Exception as e:
        print(f"データ読み込みエラー: {e}")
        return None