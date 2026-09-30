from __future__ import annotations

import html
from typing import Any, Iterable

import pandas as pd
import streamlit as st

from .i18n import t


def esc(value: Any) -> str:
    return html.escape(str(value))


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="pg-h"><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    st.markdown(f'<h2 class="sec-h">{esc(title)}</h2>', unsafe_allow_html=True)


def card(inner_html: str) -> None:
    st.markdown(f'<div class="card">{inner_html}</div>', unsafe_allow_html=True)


def kv_grid(items: Iterable[tuple[str, Any]]) -> None:
    cells = "".join(
        f'<div class="kvcell"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div></div>'
        for k, v in items
    )
    st.markdown(f'<div class="kvgrid">{cells}</div>', unsafe_allow_html=True)


def warn_box(message: str) -> None:
    st.markdown(
        f'<div class="warnbox"><span>&#9888;&#65039;</span><div>{esc(message)}</div></div>',
        unsafe_allow_html=True,
    )


def ok_box(message: str) -> None:
    st.markdown(
        f'<div class="okbox"><span>&#9989;</span><div>{esc(message)}</div></div>',
        unsafe_allow_html=True,
    )


def md_bold_to_html(text: str) -> str:
    out = esc(text)
    return out.replace("**", "<b>").replace("__", "<b>")


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def render_profile_table(profile: Any) -> None:
    from core.profiler import profile_to_dataframe

    st.dataframe(profile_to_dataframe(profile), use_container_width=True, hide_index=True)


def render_contract_editor(text: str, key: str, lang: str) -> str:
    return st.text_area(
        t("ctr_editor", lang),
        value=text,
        height=520,
        key=key,
        label_visibility="collapsed",
    )


def render_validation_report(report: dict[str, Any] | None, lang: str) -> None:
    if not report:
        ok_box(t("val_none", lang))
        return

    rows = [
        {
            "rule_id": _get(r, "rule_id", ""),
            "column": _get(r, "column", "-") or "-",
            "type": _get(r, "rule_type", ""),
            "status": _get(r, "status", ""),
            "violations": _get(r, "violations_count", 0),
            "message": _get(r, "message", ""),
        }
        for r in report.get("results", [])
    ]

    kv_grid(
        [
            (t("val_score", lang), f"{report.get('score', 0):.2%}"),
            (t("val_passed", lang), report.get("passed", 0)),
            (t("val_failed", lang), report.get("failed", 0)),
            (t("val_warnings", lang), report.get("warnings", 0)),
        ]
    )

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
