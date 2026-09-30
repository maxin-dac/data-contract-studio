from __future__ import annotations

import pathlib

import streamlit as st


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_css() -> None:
    css_path = ROOT / "assets" / "styles.css"
    if not css_path.exists():
        return

    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)