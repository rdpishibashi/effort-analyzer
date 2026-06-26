#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
effort_analysis_viewer.py - 統合工数分析ビューア
Job Organizer と Analysis Viewer の統合アプリケーション

Usage:
    streamlit run effort_analysis_viewer.py

機能:
- Job Organizer: 月次工数データの統合と業務内容分割
- Analysis Viewer: 工数データの分析とグラフ表示
- 入力選択: job_organizer処理 vs 既存xlsxファイル
- merged_efforts.xlsxのダウンロード機能付き
"""

import streamlit as st
import pandas as pd
import sys
import os
from pathlib import Path

# モジュールインポート
try:
    from web_interface import show_main_tabs
except ImportError as e:
    st.error(f"モジュールインポートエラー: {e}")
    st.error("必要なモジュールファイルが見つかりません。")
    st.stop()


def main():
    """メイン関数"""
    # Streamlitページ設定
    st.set_page_config(
        page_title="統合工数分析ビューア",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # メインタイトル
    st.title("工数分析ツール")
    st.markdown("月別工数の統合と工数分析ツール")
    
    # セッション状態初期化
    if 'latest_processed_data' not in st.session_state:
        st.session_state.latest_processed_data = None
    if 'show_analysis' not in st.session_state:
        st.session_state.show_analysis = False
    
    # メインインターフェース表示
    try:
        show_main_tabs()
    except Exception as e:
        st.error(f"アプリケーション実行エラー: {e}")
        st.exception(e)
    
    # フッター
    st.markdown("---")
    st.caption("Integrated Effort Analysis Viewer - Job Organizer + Analysis Viewer")


if __name__ == "__main__":
    main()