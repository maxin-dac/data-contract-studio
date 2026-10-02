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


def render_topbar(version: str) -> str:
    lang = st.session_state.get("lang", "en")
    keys = [key for key, _ in NAV_ITEMS]
    current = st.session_state.get("nav_view", "home")
    if current not in keys:
        current = keys[0]
    with st.container(key="suite-topbar"):
        nav_col, language_col, brand_col = st.columns([6.7, 1.1, 2.2])
        with nav_col:
            view = st.segmented_control(
                t("nav_label", lang),
                options=keys,
                default=current,
                format_func=lambda key: t(dict(NAV_ITEMS)[key], lang),
                key="suite-nav",
                required=True,
                label_visibility="collapsed",
                width="stretch",
            )
        with language_col:
            choice = st.segmented_control(
                t("language", lang),
                ["FR", "EN"],
                default="FR" if lang == "fr" else "EN",
                key="dds_lang_radio",
                required=True,
                label_visibility="collapsed",
            )
        with brand_col:
            version_text = version if version.startswith("v") else f"v{version}"
            st.markdown(
                f'<div class="suite-product"><span class="suite-product-logo">{_LOGO_SVG}</span>'
                f'<span class="suite-product-copy"><strong>{_e(t("app_name", lang))}</strong>'
                f'<small>{_e(version_text)}</small></span></div>',
                unsafe_allow_html=True,
            )
    new_lang = "fr" if choice == "FR" else "en"
    if new_lang != lang:
        st.session_state.lang = new_lang
        st.rerun()
    st.session_state.nav_view = view
    return view
