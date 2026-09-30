from __future__ import annotations

import html

import streamlit as st

from .i18n import t


NAV_ITEMS = [
    ("home", "nav_home"),
    ("import", "nav_import"),
    ("profile", "nav_profile"),
    ("contract", "nav_contract"),
    ("validate", "nav_validate"),
    ("export", "nav_export"),
]

_TAGLINE = {
    "en": "Data contract generator",
    "fr": "Generateur de contrats",
}

_LOGO_SVG = (
    '<svg class="logo-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M4 7h16"></path><path d="M4 12h10"></path><path d="M4 17h7"></path>'
    '<path d="M17 14l2 2 3-4"></path></svg>'
)


def _e(value: str) -> str:
    return html.escape(str(value))


def render_sidebar(version: str) -> None:
    lang = st.session_state.get("lang", "en")

    st.sidebar.markdown(
        f'<div class="idcard"><div class="logo-wrap">{_LOGO_SVG}</div>'
        f'<div class="idmeta"><div class="idtitle">{_e(t("app_name", lang))}</div>'
        f'<div class="idsub">{_e(_TAGLINE.get(lang, _TAGLINE["en"]))}</div>'
        f'<div class="idver">version v{_e(version)}</div></div></div>',
        unsafe_allow_html=True,
    )

    st.sidebar.markdown(
        f'<div class="lang-label">{_e(t("language", lang))}</div>',
        unsafe_allow_html=True,
    )

    choice = st.sidebar.radio(
        t("language", lang),
        ["FR", "EN"],
        index=0 if lang == "fr" else 1,
        horizontal=True,
        key="dds_lang_radio",
        label_visibility="collapsed",
    )
    new_lang = "fr" if choice == "FR" else "en"
    if new_lang != lang:
        st.session_state.lang = new_lang
        st.rerun()


def render_nav() -> str:
    lang = st.session_state.get("lang", "en")
    labels = [t(key, lang) for _, key in NAV_ITEMS]

    try:
        selected = st.segmented_control(
            t("nav_label", lang),
            labels,
            key="dds-top-nav",
            label_visibility="collapsed",
        )
    except Exception:
        selected = st.radio(
            t("nav_label", lang),
            labels,
            horizontal=True,
            key="dds-top-nav",
            label_visibility="collapsed",
        )

    if selected not in labels:
        selected = labels[0]

    view = NAV_ITEMS[labels.index(selected)][0]
    st.session_state.nav_view = view
    return view
