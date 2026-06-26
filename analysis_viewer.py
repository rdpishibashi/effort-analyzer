#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analysis_viewer.py - 工数分析ビューアの機能
"""

import pandas as pd
import numpy as np
import plotly.express as px


# 定数定義
BLANK_STR = "[空白]"
BASE_COLUMN_ORDER = [
    "USER_FIELD_01", "USER_FIELD_02", "USER_FIELD_03",
    "業務内容1", "業務内容2", "業務内容3", "業務内容4", "業務内容5"
]
UNIT_COL = "WBS要素(代入)"
EFFORT_COL = "作業時間(h)"


def apply_filters(df, filters, date_range=None):
    """フィルター条件を適用"""
    filtered_df = df.copy()
    
    # 日付範囲フィルター
    if date_range and date_range.get('start') and date_range.get('end'):
        start_year, start_month = date_range['start']
        end_year, end_month = date_range['end']
        
        # 年月の範囲チェック
        if '年' in filtered_df.columns and '月' in filtered_df.columns:
            # 開始年月と終了年月を数値として比較
            start_date_num = start_year * 100 + start_month
            end_date_num = end_year * 100 + end_month
            
            # データフレームの年月を数値化
            filtered_df['年月数値'] = pd.to_numeric(filtered_df['年'], errors='coerce') * 100 + pd.to_numeric(filtered_df['月'], errors='coerce')
            
            # 範囲内のデータのみ抽出
            filtered_df = filtered_df[
                (filtered_df['年月数値'] >= start_date_num) & 
                (filtered_df['年月数値'] <= end_date_num)
            ]
            
            # 一時的なカラムを削除
            filtered_df = filtered_df.drop('年月数値', axis=1)
    
    # 通常のフィルター
    for col, selected_values in filters.items():
        if not selected_values or col not in filtered_df.columns:
            continue
            
        filter_values_actual = [np.nan if v == BLANK_STR else v for v in selected_values]
        is_nan_selected = np.nan in filter_values_actual
        non_nan_values = [v for v in filter_values_actual if v is not np.nan]
        
        if is_nan_selected:
            filtered_df = filtered_df[filtered_df[col].isin(non_nan_values) | filtered_df[col].isna()]
        else:
            filtered_df = filtered_df[filtered_df[col].isin(non_nan_values)]
    
    return filtered_df


def get_grouping_columns(available_columns, applied_filters):
    """グループ化カラムを決定"""
    group_cols = []
    last_selected_index = -1
    
    if applied_filters:
        for col in reversed(available_columns):
            if col in applied_filters:
                try:
                    last_selected_index = available_columns.index(col)
                    break
                except ValueError:
                    pass
        
        if last_selected_index != -1:
            group_cols_candidate_indices = range(last_selected_index + 1, len(available_columns))
            group_cols = [available_columns[i] for i in group_cols_candidate_indices]
    else:
        group_cols = available_columns[:]
    
    return group_cols


def aggregate_data(df, group_cols, effort_col):
    """データを集計"""
    if not group_cols or effort_col not in df.columns:
        return None
    
    try:
        result_df = df.groupby(group_cols, dropna=False, observed=True)[effort_col].sum().reset_index()
        
        # 空白値の処理
        for col in group_cols:
            if result_df[col].isnull().any():
                try:
                    result_df[col] = result_df[col].astype(object).fillna(BLANK_STR)
                except Exception:
                    result_df[col] = result_df[col].fillna(BLANK_STR)
        
        return result_df
    except Exception as e:
        print(f"集計エラー: {e}")
        return None


def aggregate_by_year_month_person(df, effort_col='作業時間(h)'):
    """
    データを年、月、従業員名、USER_FIELD_01/02/03、WBS要素(代入)、MODULE、業務内容1-10で集計
    
    Parameters:
    -----------
    df : pd.DataFrame
        処理対象のデータフレーム
    effort_col : str
        集計する作業時間のカラム名
    
    Returns:
    --------
    pd.DataFrame
        指定されたカラムで集計されたデータフレーム
    """
    required_cols = ['年', '月', '従業員名', effort_col]
    
    # 必要なカラムが存在するか確認
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"必要なカラムが不足しています: {missing_cols}")
    
    # グループ化するカラムのリストを作成
    group_cols = ['年', '月', '従業員名']
    
    # USER_FIELDカラムを追加
    for col in ['USER_FIELD_01', 'USER_FIELD_02', 'USER_FIELD_03']:
        if col in df.columns:
            group_cols.append(col)
    
    # WBS要素(代入)とMODULEも含める（存在する場合）
    for col in [UNIT_COL, 'MODULE']:
        if col in df.columns:
            group_cols.append(col)
    
    # 業務内容カラムを追加（業務内容1から順に存在するものを追加）
    business_cols = []
    for i in range(1, 21):  # 業務内容1〜20まで対応
        col = f'業務内容{i}'
        if col in df.columns:
            business_cols.append(col)
            group_cols.append(col)
    
    # グループ化して作業時間を合計
    aggregated_df = df.groupby(group_cols, dropna=False).agg({
        effort_col: 'sum'
    }).reset_index()
    
    # 他のカラム（第1分類、第2分類、第3分類など）も含める場合
    other_cols = ['第1分類', '第2分類', '第3分類', 'USER_FIELD_04', 'USER_FIELD_05']
    for col in other_cols:
        if col in df.columns and col not in group_cols:
            # これらのカラムは最頻値を取得
            mode_series = df.groupby(group_cols)[col].apply(
                lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0] if len(x) > 0 else None
            ).reset_index()
            aggregated_df = aggregated_df.merge(mode_series, on=group_cols, how='left')
    
    # ソート（年、月、従業員名の順）
    aggregated_df = aggregated_df.sort_values(['年', '月', '従業員名'])
    
    return aggregated_df


def export_aggregated_data_to_excel(df, output_buffer=None):
    """
    集計データをExcelファイルとして出力
    
    Parameters:
    -----------
    df : pd.DataFrame
        出力するデータフレーム
    output_buffer : BytesIO or str, optional
        出力先（BytesIOオブジェクトまたはファイルパス）
    
    Returns:
    --------
    BytesIO or None
        output_bufferが指定されていない場合はBytesIOオブジェクトを返す
    """
    import io
    from datetime import datetime
    
    # output_bufferが指定されていない場合は新規作成
    if output_buffer is None:
        output_buffer = io.BytesIO()
        return_buffer = True
    else:
        return_buffer = False
    
    # ExcelWriterを使用して書き込み
    with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
        # メインデータシート
        df.to_excel(writer, sheet_name='集計データ', index=False)
        
        # サマリーシート作成
        summary_data = []
        
        # 全体統計
        summary_data.append(['統計情報', ''])
        summary_data.append(['総レコード数', len(df)])
        summary_data.append(['総作業時間(h)', df['作業時間(h)'].sum() if '作業時間(h)' in df.columns else 0])
        summary_data.append(['ユニーク従業員数', df['従業員名'].nunique() if '従業員名' in df.columns else 0])
        summary_data.append([''])
        
        # 年月別統計
        if '年' in df.columns and '月' in df.columns:
            year_month_stats = df.groupby(['年', '月']).agg({
                '従業員名': 'nunique',
                '作業時間(h)': 'sum'
            }).reset_index()
            year_month_stats.columns = ['年', '月', '従業員数', '総作業時間(h)']
            
            summary_data.append(['年月別統計', '', '', ''])
            summary_data.append(['年', '月', '従業員数', '総作業時間(h)'])
            for _, row in year_month_stats.iterrows():
                summary_data.append(row.tolist())
        
        # サマリーシートに書き込み
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='サマリー', index=False, header=False)
        
        # 処理日時情報シート
        info_data = [
            ['処理情報'],
            ['処理日時', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['データ期間', f"{df['年'].min()}年{df['月'].min()}月 〜 {df['年'].max()}年{df['月'].max()}月" if '年' in df.columns and '月' in df.columns else '']
        ]
        info_df = pd.DataFrame(info_data)
        info_df.to_excel(writer, sheet_name='情報', index=False, header=False)
    
    if return_buffer:
        output_buffer.seek(0)
        return output_buffer
    
    return None


def sort_aggregated_data(df, sort_column, sort_ascending):
    """集計データをソート"""
    if not sort_column or df.empty:
        return df
    
    try:
        return df.sort_values(
            by=sort_column, 
            ascending=sort_ascending,
            key=lambda col: col.astype(str) if col.dtype == 'object' else col
        )
    except Exception as e:
        print(f"ソートエラー: {e}")
        return df


def create_plot_data(df, group_cols, effort_col, num_items, sort_column, sort_ascending):
    """グラフ用データを作成"""
    try:
        plot_df = df.copy()
        
        # 項目名を作成
        item_cols = [col for col in group_cols if col in plot_df.columns]
        if item_cols:
            plot_df["項目"] = plot_df[item_cols].astype(str).agg(" / ".join, axis=1)
        else:
            plot_df["項目"] = "合計"
        
        # 表示件数を制限
        if isinstance(num_items, int) and num_items < len(plot_df):
            plot_df = plot_df.head(num_items)
        
        # ソート方向を判定
        sort_direction = "上位" if not sort_ascending else "下位"
        if sort_column != effort_col:
            sort_direction = "ソート順"
        
        # タイトル作成
        if isinstance(num_items, int) and num_items < len(df):
            title = f"{sort_direction}{num_items}件の作業時間"
        else:
            title = "すべての作業時間"
        
        return plot_df, title
    except Exception as e:
        print(f"グラフデータ作成エラー: {e}")
        return None, None


def create_bar_chart(plot_df, title, effort_col, graph_type="横棒グラフ"):
    """棒グラフを作成"""
    try:
        if plot_df.empty or effort_col not in plot_df.columns:
            return None
        
        max_item_length = max(plot_df["項目"].astype(str).apply(len)) if not plot_df.empty else 10
        
        if graph_type == "横棒グラフ":
            plot_df_ordered = plot_df[::-1]  # 逆順にする
            fig = px.bar(plot_df_ordered, x=effort_col, y="項目", orientation="h", title=title)
            fig.update_layout(
                xaxis_side='top',
                xaxis_title="作業時間 [h]",
                yaxis={"tickfont": {"size": 10}},
                margin=dict(l=min(350, max(150, max_item_length * 7)), r=30, t=110, b=20),
                height=max(400, 20 * len(plot_df_ordered)),
            )
            hover_template = '%{y}: %{x:.2f} h'
        else:  # 縦棒グラフ
            fig = px.bar(plot_df, x="項目", y=effort_col, title=title)
            fig.update_layout(
                xaxis={
                    'categoryorder': 'array',
                    'categoryarray': plot_df["項目"].tolist(),
                    "tickfont": {"size": 10}
                },
                xaxis_tickangle=-45,
                yaxis_title="作業時間 [h]",
                margin=dict(l=70, r=30, t=80, b=min(300, max(100, max_item_length * 6))),
                height=max(500, 350 + min(300, max(100, max_item_length * 6))),
            )
            hover_template = '%{x}: %{y:.2f} h'
        
        fig.update_layout(
            font=dict(size=12),
            plot_bgcolor='rgba(240,240,240,0.5)',
            bargap=0.2,
            title_font=dict(size=16)
        )
        fig.update_traces(hovertemplate=hover_template)
        
        return fig
    except Exception as e:
        print(f"グラフ作成エラー: {e}")
        return None


def get_available_columns(df):
    """利用可能なカラムを取得"""
    available_columns = []
    for col in BASE_COLUMN_ORDER:
        if col in df.columns:
            available_columns.append(col)
    # BASE_COLUMN_ORDERにない業務内容Xカラムを番号順に追加
    already_added = set(available_columns)
    prefix = '業務内容'
    extra = sorted(
        [col for col in df.columns
         if col.startswith(prefix) and col != prefix and col not in already_added],
        key=lambda x: int(x[len(prefix):]) if x[len(prefix):].isdigit() else 999
    )
    available_columns.extend(extra)
    return available_columns


def get_nonempty_business_columns(df, columns):
    """フィルター後データで全空白の業務内容Xカラムを除外して返す"""
    if df.empty:
        return [col for col in columns if not col.startswith('業務内容') or col == '業務内容']

    result = []
    prefix = '業務内容'
    for col in columns:
        if col.startswith(prefix) and col != prefix:
            if col not in df.columns:
                continue
            non_blank = df[col].dropna()
            non_blank = non_blank[non_blank.astype(str).str.strip() != '']
            if not non_blank.empty:
                result.append(col)
        else:
            result.append(col)
    return result


def get_unique_values_with_blank(df, column):
    """カラムのユニーク値を取得（空白値を含む）"""
    if column not in df.columns:
        return []
    
    options = df[column].fillna(BLANK_STR).unique().tolist()
    try:
        options.sort(key=lambda x: str(x))
    except TypeError:
        pass
    
    return options


def format_display_dataframe(df, effort_col, decimal_places=2):
    """表示用にデータフレームをフォーマット"""
    display_df = df.copy()
    
    if effort_col in display_df.columns:
        display_df[effort_col] = display_df[effort_col].apply(
            lambda x: f"{x:.{decimal_places}f}"
        )
    
    return display_df


def get_column_display_order(df, unit_col_exists=False):
    """カラムの表示順序を取得"""
    columns = df.columns.tolist()
    
    if EFFORT_COL in columns:
        columns.remove(EFFORT_COL)
        if unit_col_exists and UNIT_COL in columns:
            columns.remove(UNIT_COL)
            columns.append(UNIT_COL)
        columns.append(EFFORT_COL)
    
    return columns


def get_date_range_options(df):
    """データフレームから年月の範囲を取得"""
    if '年' not in df.columns or '月' not in df.columns:
        return None, None, None
    
    # 年月の組み合わせを取得してソート
    years = pd.to_numeric(df['年'], errors='coerce').dropna().astype(int)
    months = pd.to_numeric(df['月'], errors='coerce').dropna().astype(int)
    
    if years.empty or months.empty:
        return None, None, None
    
    # 年月の組み合わせを作成
    year_month_combinations = []
    for _, row in df.iterrows():
        year = pd.to_numeric(row['年'], errors='coerce')
        month = pd.to_numeric(row['月'], errors='coerce')
        if pd.notna(year) and pd.notna(month):
            year_month_combinations.append((int(year), int(month)))
    
    # 重複を削除してソート
    unique_combinations = sorted(list(set(year_month_combinations)))
    
    if not unique_combinations:
        return None, None, None
    
    min_year_month = unique_combinations[0]
    max_year_month = unique_combinations[-1]
    
    return unique_combinations, min_year_month, max_year_month