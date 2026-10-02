from __future__ import annotations
import pathlib
import streamlit as st


ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def read_css() -> str:
    styles = (ASSETS / "styles.css").read_text(encoding="utf-8")
    suite_styles = ASSETS / "suite.css"
    if suite_styles.exists():
        styles += "\n" + suite_styles.read_text(encoding="utf-8")
    return styles


def read_svg() -> str:
    svg_path = ASSETS / "icons.svg"
    if svg_path.exists():
        return svg_path.read_text(encoding="utf-8")
    return ""


def read_layout() -> str:
    html_path = ASSETS / "layout.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return ""


def load_css() -> None:
    css = read_css()
    svg = read_svg()
    st.markdown(f"<style>{css}</style>{svg}", unsafe_allow_html=True)
