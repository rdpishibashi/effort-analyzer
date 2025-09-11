#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_interface.py - Streamlit UI コンポーネント
"""

import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime
import io

from data_merger import process_integrated_workflow
from analysis_viewer import (
    apply_filters, get_grouping_columns, aggregate_data, sort_aggregated_data,
    create_plot_data, create_bar_chart, get_available_columns, 
    get_unique_values_with_blank, format_display_dataframe, get_column_display_order,
    get_date_range_options, aggregate_by_year_month_person, export_aggregated_data_to_excel,
    BLANK_STR, BASE_COLUMN_ORDER, UNIT_COL, EFFORT_COL
)
from data_processor import load_data_from_source


def show_job_organizer_interface():
    """job_organizer機能のインターフェース"""
    st.header("Job Organizer - 工数データ統合")
    st.write("毎月の工数データファイルを統合工数データファイルに追加し、業務内容を分割・整理します。")
    
    # ファイルアップロード
    st.subheader("ファイルを選択してください")
    
    existing_file = st.file_uploader(
        "既存の統合工数データファイル", 
        type=['xlsx'], 
        key="existing_merged"
    )
    
    new_file = st.file_uploader(
        "新しい月次工数データファイル", 
        type=['xlsx'], 
        key="new_monthly"
    )
    
    if existing_file and new_file:
        # ファイル情報表示
        show_file_info(existing_file, new_file)
        
        # 処理実行
        st.subheader("統合処理")
        
        if st.button("データ処理開始", type="primary", key="process_data"):
            result_data = process_job_organizer(existing_file, new_file)
            
            if result_data is not None:
                st.success("統合処理完了！")
                
                # 処理結果の表示
                show_processing_results(result_data)
                
                # セッション状態に結果を保存
                st.session_state.latest_processed_data = result_data
                st.session_state.show_analysis = True
                
                # 分析ビューアに切り替えるボタン
                if st.button("分析ビューアで確認", key="switch_to_analysis"):
                    st.session_state.current_tab = "analysis"
                    st.rerun()
            else:
                st.error("❌ 処理に失敗しました")


def show_file_info(existing_file, new_file):
    """ファイル情報を表示"""
    st.subheader("ファイル情報")
    
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
                st.success("日報データシートあり")
                new_df = pd.read_excel(new_file, sheet_name='日報データ')
                st.write(f"行数: {len(new_df):,}")
            else:
                st.warning("⚠️ 日報データシートが見つかりません")
                st.write("利用可能なシート:", sheets)
                
        except Exception as e:
            st.error(f"新しいファイルの読み込みエラー: {e}")


def process_job_organizer(existing_file, new_file):
    """job_organizer処理を実行"""
    try:
        # プログレスバー
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        def update_progress(progress, status):
            progress = float(max(0.0, min(1.0, progress)))
            progress_bar.progress(progress)
            status_text.text(status)
        
        # ファイルをBytesIOとして直接処理
        existing_file.seek(0)
        new_file.seek(0)
        
        # 統合処理実行
        output_filename = f"merged_efforts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        final_data = process_integrated_workflow(
            existing_file, 
            new_file, 
            output_filename,
            progress_callback=update_progress
        )
        
        # 一時ファイルを削除
        if os.path.exists(output_filename):
            os.remove(output_filename)
        
        return final_data
        
    except Exception as e:
        st.error(f"処理エラー: {e}")
        return None


def show_processing_results(data):
    """処理結果を表示"""
    st.subheader("処理結果")
    
    # 基本統計
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("総行数", f"{len(data):,}")
    with col2:
        st.metric("総作業時間", f"{data['作業時間(h)'].sum():.1f} h")
    with col3:
        st.metric("従業員数", f"{data['従業員名'].nunique()}")
    
    # データプレビュー
    st.subheader("データプレビュー")
    st.dataframe(data.head(10))
    
    # 統計情報
    st.subheader("年月別統計")
    stats = data.groupby(['年', '月']).agg({
        '従業員名': 'nunique',
        '作業時間(h)': 'sum'
    }).reset_index()
    stats.columns = ['年', '月', 'ユニーク従業員数', '総作業時間(h)']
    st.dataframe(stats)
    
    # 業務内容分割統計
    task_columns = [col for col in data.columns if col.startswith('業務内容') and col != '業務内容']
    if task_columns:
        st.subheader("業務内容分割統計")
        task_stats = {}
        for col in task_columns:
            non_empty_count = data[col].notna().sum()
            task_stats[col] = non_empty_count
        
        task_stats_df = pd.DataFrame(list(task_stats.items()), columns=['カラム', '非空データ数'])
        st.dataframe(task_stats_df)
    
    # ダウンロードボタン
    excel_buffer = io.BytesIO()
    data.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)
    
    st.download_button(
        label="処理済みファイルをダウンロード",
        data=excel_buffer.getvalue(),
        file_name=f"merged_efforts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def show_analysis_viewer_interface():
    """分析ビューア機能のインターフェース"""
    st.header("Analysis Viewer - 工数分析")
    
    # データソース選択
    data_source = show_data_source_selection()
    
    if data_source is not None:
        # フィルターとグラフ表示
        show_analysis_filters_and_charts(data_source)
    else:
        st.info("データを選択してください。")


def show_data_source_selection():
    """データソース選択UI"""
    st.subheader("データソース選択")
    
    # タブで選択方法を分ける
    tab1, tab2 = st.tabs(["ファイルアップロード", "最新処理結果"])
    
    with tab1:
        # ファイルタイプの選択
        file_type = st.radio(
            "ファイルタイプ",
            ["通常の工数データファイル", "集計済みデータファイル"],
            help="集計済みデータファイルは、既に年・月・従業員名・業務内容等で集計されたファイルです",
            key="file_type_selection"
        )
        
        uploaded_file = st.file_uploader(
            f"分析するExcelファイルをアップロード（{file_type}）", 
            type=["xlsx", "xls"],
            key="analysis_upload"
        )
        
        if uploaded_file:
            data = load_data_from_source(uploaded_file)
            if data is not None:
                st.success("ファイルが正常に読み込まれました")
                
                # データタイプの確認と表示
                if file_type == "集計済みデータファイル":
                    st.info("集計済みデータとして読み込みました。このデータは既に集計されているため、再集計は不要です。")
                
                # データ概要の表示
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("総行数", f"{len(data):,}")
                with col2:
                    if '作業時間(h)' in data.columns:
                        st.metric("総作業時間", f"{data['作業時間(h)'].sum():.1f} h")
                with col3:
                    if '従業員名' in data.columns:
                        st.metric("従業員数", f"{data['従業員名'].nunique()}")
                
                return data
            else:
                st.error("❌ ファイルの読み込みに失敗しました")
    
    with tab2:
        if hasattr(st.session_state, 'latest_processed_data') and st.session_state.latest_processed_data is not None:
            if st.button("最新処理結果を使用", key="use_latest"):
                st.success("最新処理結果を使用します")
                return st.session_state.latest_processed_data
        else:
            st.info("最新の処理結果がありません。まずJob Organizerでデータを処理してください。")
    
    return None


def show_analysis_filters_and_charts(df):
    """分析フィルターとグラフ表示"""
    st.subheader("フィルター設定")
    
    # サイドバーにフィルター配置
    with st.sidebar:
        st.header("フィルター条件")
        
        available_columns = get_available_columns(df)
        unit_col_exists = UNIT_COL in df.columns
        
        applied_filters = {}
        date_range_filter = None
        
        # 日付範囲フィルター
        date_options, min_date, max_date = get_date_range_options(df)
        if date_options:
            st.subheader("日付範囲")
            
            # 年月の選択肢を文字列として準備
            date_str_options = [f"{year}年{month:02d}月" for year, month in date_options]
            
            # 開始年月選択
            start_index = st.selectbox(
                "開始年月",
                options=range(len(date_str_options)),
                format_func=lambda x: date_str_options[x],
                index=0,
                key="start_date"
            )
            
            # 終了年月選択
            end_index = st.selectbox(
                "終了年月",
                options=range(len(date_str_options)),
                format_func=lambda x: date_str_options[x],
                index=len(date_str_options) - 1,
                key="end_date"
            )
            
            # 選択された範囲が有効かチェック
            if start_index <= end_index:
                start_year_month = date_options[start_index]
                end_year_month = date_options[end_index]
                date_range_filter = {
                    'start': start_year_month,
                    'end': end_year_month
                }
            else:
                st.error("開始年月は終了年月より前の日付を選択してください")
        
        st.divider()
        
        # 初期データフィルター用
        filtered_df = apply_filters(df.copy(), {}, date_range_filter)
        
        # 基本カラムのカスケードフィルター
        for col in available_columns:
            if col not in df.columns:
                continue
                
            options = get_unique_values_with_blank(filtered_df, col)
            if not options:
                continue
            
            selected = st.multiselect(
                f"{col} で絞り込み",
                options=options,
                key=f"filter_{col}",
                default=[]
            )
            
            if selected:
                applied_filters[col] = selected
                # 全てのフィルターを適用
                filtered_df = apply_filters(df.copy(), applied_filters, date_range_filter)
        
        # UNITフィルター（非カスケード）
        if unit_col_exists:
            unit_options = get_unique_values_with_blank(df, UNIT_COL)
            unit_selected = st.multiselect(
                f"{UNIT_COL} で絞り込み (AND条件)",
                options=unit_options,
                key=f"filter_{UNIT_COL}",
                default=[]
            )
            
            if unit_selected:
                applied_filters[UNIT_COL] = unit_selected
        
        # 最終的なフィルター適用
        filtered_df = apply_filters(df.copy(), applied_filters, date_range_filter)
    
    # メインエリアに結果表示
    st.subheader("集計結果")
    
    # 年月従業員別集計とエクスポートセクション
    with st.expander("集計データエクスポート"):
        st.write("フィルター適用後のデータを年・月・従業員名・USER_FIELD_01/02/03・UNIT・MODULE・業務内容で集計してExcelファイルとしてエクスポートできます。")
        
        if st.button("集計してエクスポート", key="export_aggregated", type="primary"):
            try:
                # 年月従業員別に集計
                aggregated_df = aggregate_by_year_month_person(filtered_df)
                
                # Excelファイルとして出力
                excel_buffer = export_aggregated_data_to_excel(aggregated_df)
                
                # ダウンロードボタン
                st.download_button(
                    label="集計データをダウンロード",
                    data=excel_buffer.getvalue(),
                    file_name=f"aggregated_effort_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # 集計結果の確認
                st.success(f"集計完了: {len(aggregated_df)}件のレコード")
                
            except Exception as e:
                st.error(f"集計エクスポート中にエラーが発生しました: {str(e)}")
    
    st.divider()
    
    # グループ化カラム決定
    group_cols = get_grouping_columns(available_columns, applied_filters)
    if unit_col_exists and UNIT_COL not in group_cols and UNIT_COL in df.columns:
        group_cols.append(UNIT_COL)
    
    if group_cols and EFFORT_COL in filtered_df.columns:
        # データ集計
        result_df = aggregate_data(filtered_df, group_cols, EFFORT_COL)
        
        if result_df is not None:
            # ソート設定
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                sort_options = result_df.columns.tolist()
                default_sort = EFFORT_COL if EFFORT_COL in sort_options else sort_options[0]
                sort_column = st.selectbox("ソート列", sort_options, 
                                         index=sort_options.index(default_sort))
            with col2:
                sort_ascending = st.radio("ソート順", ["降順", "昇順"], index=0, horizontal=True) == "昇順"
            with col3:
                decimal_places = st.number_input("表示小数点桁数", 0, 4, 2)
            
            # データソートと表示
            result_df_sorted = sort_aggregated_data(result_df, sort_column, sort_ascending)
            
            # 表示用データフレーム
            display_columns = get_column_display_order(result_df_sorted, unit_col_exists)
            result_df_display = result_df_sorted[display_columns].copy()
            result_df_display = format_display_dataframe(result_df_display, EFFORT_COL, decimal_places)
            
            st.dataframe(result_df_display, use_container_width=True, hide_index=True)
            
            # グラフ表示
            show_charts(result_df_sorted, group_cols, EFFORT_COL, sort_column, sort_ascending)
        else:
            st.error("集計処理に失敗しました")
    else:
        # グループ化できない場合の表示
        if not filtered_df.empty and EFFORT_COL in filtered_df.columns:
            total_effort = filtered_df[EFFORT_COL].sum()
            st.metric("絞り込み結果の合計作業時間", f"{total_effort:.2f} h")
            
            # 表示列を決定
            display_cols = [col for col in available_columns if col in filtered_df.columns]
            if unit_col_exists and UNIT_COL in filtered_df.columns:
                display_cols.append(UNIT_COL)
            if EFFORT_COL in filtered_df.columns:
                display_cols.append(EFFORT_COL)
            
            st.dataframe(filtered_df[display_cols], hide_index=True)
        else:
            st.info("フィルター条件に一致するデータがありません。")


def show_charts(df, group_cols, effort_col, sort_column, sort_ascending):
    """グラフ表示"""
    st.header("グラフ表示")
    
    # グラフ設定
    col1, col2 = st.columns(2)
    with col1:
        graph_type = st.selectbox("グラフの種類", ["横棒グラフ", "縦棒グラフ"])
    with col2:
        num_items_options = [10, 20, 50, 100, "すべて"]
        num_items = st.selectbox("表示件数", num_items_options, index=1)
    
    # グラフ作成
    try:
        plot_df, title = create_plot_data(df, group_cols, effort_col, num_items, sort_column, sort_ascending)
        
        if plot_df is not None and not plot_df.empty:
            fig = create_bar_chart(plot_df, title, effort_col, graph_type)
            
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("グラフの作成に失敗しました")
        else:
            st.info("グラフ表示対象のデータがありません。")
            
    except Exception as e:
        st.error(f"グラフ描画中にエラー: {e}")


def show_usage_info():
    """使い方説明"""
    with st.expander("使い方と処理内容の詳細"):
        st.markdown("""
        ### 統合アプリケーションの使い方
        
        #### Job Organizer機能
        1. **既存の統合工数データファイル**: 過去の工数データが統合されたExcelファイル
        2. **新しい月次工数データファイル**: 新しく追加したい月の工数データ（日報データシートを含む）
        3. 処理により以下が実行されます：
           - 新しいデータを既存データにマージ
           - 重複チェック
           - 作業時間0のデータ除外
           - 業務内容の分割・整理
        4. 処理結果はExcelファイルとしてダウンロードできます
        
        #### Analysis Viewer機能
        1. **データソース選択**: 3つの方法でデータを選択
           - ファイルアップロード: 任意のExcelファイル
           - 最新処理結果: Job Organizerで処理したデータ
           - ローカルファイル: merged_efforts.xlsx
        2. **フィルター機能**: 
           - カスケードフィルター: 上位フィルターが下位に影響
           - UNITフィルター: 独立したAND条件
        3. **集計とグラフ**: 
           - 自動集計とソート
           - 横棒/縦棒グラフ選択
           - 表示件数調整
        
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


def show_main_tabs():
    """メインタブ表示"""
    # タブ選択（セッション状態で管理）
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = "organizer"
    
    # タブ切り替えボタン
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Job Organizer", use_container_width=True, 
                    type="primary" if st.session_state.current_tab == "organizer" else "secondary"):
            st.session_state.current_tab = "organizer"
            st.rerun()
    with col2:
        if st.button("Analysis Viewer", use_container_width=True,
                    type="primary" if st.session_state.current_tab == "analysis" else "secondary"):
            st.session_state.current_tab = "analysis"
            st.rerun()
    
    st.divider()
    
    # タブ内容表示
    if st.session_state.current_tab == "organizer":
        show_job_organizer_interface()
    else:
        show_analysis_viewer_interface()
    
    # 使い方説明
    show_usage_info()