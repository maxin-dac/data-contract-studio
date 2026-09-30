from __future__ import annotations

import dataclasses
import json
import pathlib
from urllib.parse import quote

import pandas as pd
import streamlit as st

from core.contract import (
    dump_yaml,
    generate_contract,
    load_yaml,
    validate_contract_structure,
)
from core.io import read_csv_bytes
from core.profiler import profile_dataframe
from core.session_store import clear_session, load_session, save_session
from core.validator import validate_dataframe
from report.builder import build_payload
from report.exporters import export_report
from ui.components import (
    card,
    esc,
    kv_grid,
    ok_box,
    page_header,
    render_contract_editor,
    render_profile_table,
    render_validation_report,
    section,
    warn_box,
)
from ui.i18n import format_warning, t
from ui.nav import render_nav, render_sidebar
from ui.theme import load_css


ROOT = pathlib.Path(__file__).resolve().parent
MAX_ROWS = 200_000

_FAV_BODY = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
    "<rect width='24' height='24' rx='6' fill='#4f46e5'/>"
    "<g fill='none' stroke='#ffffff' stroke-width='1.8' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<path d='M4 7h16'/>"
    "<path d='M4 12h10'/>"
    "<path d='M4 17h7'/>"
    "<path d='M17 14l2 2 3-4'/>"
    "</g></svg>"
)
FAVICON = "data:image/svg+xml," + quote(_FAV_BODY, safe="")


def _read_version() -> str:
    vf = ROOT / "VERSION"
    try:
        return vf.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


VERSION = _read_version()


def init_state() -> None:
    s = st.session_state
    s.setdefault("lang", "en")
    s.setdefault("nav_view", "home")
    s.setdefault("df", None)
    s.setdefault("filename", None)
    s.setdefault("profile", None)
    s.setdefault("contract", None)
    s.setdefault("contract_text", None)
    s.setdefault("validation_report", None)
    s.setdefault("warnings", [])
    s.setdefault("_session_restored", False)


def restore_session_if_available() -> None:
    s = st.session_state
    if s.get("_session_restored"):
        return

    saved = load_session()
    if saved:
        for k, v in saved.items():
            s[k] = v
        s["_session_restored"] = True


def clean_prefixes(*prefixes: str) -> None:
    s = st.session_state
    for k in list(s.keys()):
        if any(str(k).startswith(p) for p in prefixes):
            del s[k]


def load_df(df: pd.DataFrame, name: str, truncated: bool, enc: str, delim: str) -> None:
    s = st.session_state
    s.df = df
    s.filename = name
    s.profile = None
    s.contract = None
    s.contract_text = None
    s.validation_report = None
    s.warnings = []

    clean_prefixes("contract_", "valid_", "opt_")

    s["_trunc_note"] = f"Truncated to {MAX_ROWS} rows" if truncated else None
    s["_meta"] = {"enc": enc, "delim": delim}

    save_session(s)


def run_profile() -> None:
    s = st.session_state
    if s.df is None:
        return

    profile = profile_dataframe(
        s.df,
        filename=s.filename,
        cat_threshold=int(s.get("opt_catthr", 50)),
        unify_nulls=bool(s.get("opt_unify", True)),
    )

    contract = generate_contract(profile, s.filename)

    s.profile = profile
    s.contract = contract
    s.contract_text = dump_yaml(contract)
    s.validation_report = None
    s.warnings = profile.warnings

    save_session(s)


def require_df() -> bool:
    if st.session_state.df is None:
        warn_box(t("err_nofile", st.session_state.lang))
        return False
    return True


def require_profile() -> bool:
    if st.session_state.profile is None:
        warn_box(t("err_noprofile", st.session_state.lang))
        return False
    return True


def require_contract() -> bool:
    if st.session_state.contract is None:
        warn_box(t("err_nocontract", st.session_state.lang))
        return False
    return True


def page_home() -> None:
    lang = st.session_state.lang
    s = st.session_state

    page_header(t("home_title", lang), t("home_sub", lang))

    section(t("home_how", lang))
    steps = "".join(
        f"<li>{esc(t(k, lang)).replace('**', '<b>').replace('__', '<b>')}</li>"
        for k in ("home_s1", "home_s2", "home_s3")
    )
    card(f"<ol>{steps}</ol>")

    section(t("home_status", lang))

    df = s.df
    contract = s.contract
    report = s.validation_report

    kv_grid(
        [
            (t("st_rows", lang), len(df) if df is not None else "-"),
            (t("st_cols", lang), len(df.columns) if df is not None else "-"),
            (
                t("st_contract", lang),
                t("st_ready", lang) if contract else t("st_missing", lang),
            ),
            (
                t("st_validation", lang),
                f"{report.get('score', 0):.2%}" if report else t("st_missing", lang),
            ),
        ]
    )

    if df is None:
        warn_box(t("st_notloaded", lang))
    else:
        ok_box(t("st_ready", lang))


def page_import() -> None:
    lang = st.session_state.lang
    s = st.session_state

    page_header(t("imp_title", lang), t("imp_sub", lang))

    up = st.file_uploader(t("imp_upload", lang), type=["csv"], key="uploader")

    if up is not None:
        max_rows = int(s.get("opt_max_rows", MAX_ROWS))
        df, truncated, enc, delim = read_csv_bytes(up.getvalue(), max_rows=max_rows)
        load_df(df, up.name, truncated, enc, delim)

    if s.df is not None:
        meta = s.get("_meta", {})

        section(t("imp_file", lang))
        kv_grid(
            [
                (t("imp_file", lang), s.filename),
                (t("imp_shape", lang), f"{len(s.df)} x {len(s.df.columns)}"),
                ("encoding", meta.get("enc", "-")),
                ("delimiter", repr(meta.get("delim", ","))),
            ]
        )

        if s.get("_trunc_note"):
            warn_box(s["_trunc_note"])

        section(t("imp_options", lang))

        c1, c2 = st.columns(2)

        with c1:
            st.number_input(
                t("imp_max_rows", lang),
                min_value=1_000,
                max_value=1_000_000,
                value=int(s.get("opt_max_rows", MAX_ROWS)),
                step=10_000,
                key="opt_max_rows",
            )
            st.slider(
                t("imp_cat_threshold", lang),
                min_value=5,
                max_value=200,
                value=int(s.get("opt_catthr", 50)),
                key="opt_catthr",
            )

        with c2:
            st.checkbox(
                t("imp_unify_nulls", lang),
                value=bool(s.get("opt_unify", True)),
                key="opt_unify",
            )

        b1, b2 = st.columns(2)

        with b1:
            if st.button(
                t("imp_run", lang),
                key="run_profile",
                type="primary",
                use_container_width=True,
            ):
                run_profile()
                st.rerun()

        with b2:
            if st.button(
                t("imp_reset", lang),
                key="reset_session",
                use_container_width=True,
            ):
                st.session_state.df = None
                st.session_state.filename = None
                st.session_state.profile = None
                st.session_state.contract = None
                st.session_state.contract_text = None
                st.session_state.validation_report = None
                st.session_state.warnings = []
                clean_prefixes("opt_", "contract_", "valid_")
                clear_session()
                st.rerun()

        if s.profile is not None:
            ok_box(t("imp_profiled", lang))
        else:
            st.markdown(
                f'<div class="note">{esc(t("imp_notyet", lang))}</div>',
                unsafe_allow_html=True,
            )


def page_profile() -> None:
    lang = st.session_state.lang
    s = st.session_state

    page_header(t("prof_title", lang), t("prof_sub", lang))

    if not (require_df() and require_profile()):
        return

    section(t("prof_columns", lang))
    render_profile_table(s.profile)

    section(t("prof_warnings", lang))
    if s.warnings:
        formatted = [format_warning(w, lang) for w in s.warnings]
        card("<ul>" + "".join(f"<li>{esc(x)}</li>" for x in formatted) + "</ul>")
    else:
        ok_box(t("prof_nowarn", lang))

    section(t("prof_preview", lang))
    st.code(s.contract_text or "", language="yaml")


def page_contract() -> None:
    lang = st.session_state.lang
    s = st.session_state

    page_header(t("ctr_title", lang), t("ctr_sub", lang))

    if not require_profile():
        return

    if s.contract_text is None:
        s.contract_text = dump_yaml(s.contract or generate_contract(s.profile, s.filename))

    edited = render_contract_editor(s.contract_text or "", "contract_editor", lang)

    b1, b2 = st.columns(2)

    with b1:
        if st.button(t("ctr_save", lang), type="primary", use_container_width=True):
            try:
                contract = load_yaml(edited)
                errors = validate_contract_structure(contract)
                if errors:
                    for err in errors:
                        warn_box(err)
                else:
                    s.contract = contract
                    s.contract_text = edited
                    s.validation_report = None
                    save_session(s)
                    ok_box(t("ctr_saved", lang))
                    st.rerun()
            except Exception as exc:
                warn_box(f"{t('ctr_invalid', lang)}: {exc}")

    with b2:
        if st.button(t("ctr_reset", lang), use_container_width=True):
            contract = generate_contract(s.profile, s.filename)
            s.contract = contract
            s.contract_text = dump_yaml(contract)
            s.validation_report = None
            save_session(s)
            st.rerun()

    if s.contract:
        section(t("prof_preview", lang))
        st.code(s.contract_text or "", language="yaml")


def page_validate() -> None:
    lang = st.session_state.lang
    s = st.session_state

    page_header(t("val_title", lang), t("val_sub", lang))

    if not (require_df() and require_contract()):
        return

    if st.button(t("val_run", lang), type="primary"):
        report = validate_dataframe(s.df, s.contract)
        s.validation_report = dataclasses.asdict(report)
        save_session(s)
        st.rerun()

    section(t("val_report", lang))
    render_validation_report(s.validation_report, lang)


def page_export() -> None:
    lang = st.session_state.lang
    s = st.session_state

    page_header(t("exp_title", lang), t("exp_sub", lang))

    if not require_contract():
        return

    payload = build_payload(s.contract, s.validation_report, lang)

    contract_yaml = s.contract_text or dump_yaml(s.contract)
    contract_json = json.dumps(s.contract, indent=2, default=str)
    report_json = export_report(payload, "json")
    report_md = export_report(payload, "markdown")
    report_html = export_report(payload, "html")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.download_button(
            t("exp_contract_yaml", lang),
            data=contract_yaml.encode("utf-8"),
            file_name="data_contract.yaml",
            mime="text/yaml",
            use_container_width=True,
        )

    with c2:
        st.download_button(
            t("exp_contract_json", lang),
            data=contract_json.encode("utf-8"),
            file_name="data_contract.json",
            mime="application/json",
            use_container_width=True,
        )

    with c3:
        st.download_button(
            t("exp_report_json", lang),
            data=report_json.encode("utf-8"),
            file_name="validation_report.json",
            mime="application/json",
            use_container_width=True,
            disabled=s.validation_report is None,
        )

    with c4:
        st.download_button(
            t("exp_report_md", lang),
            data=report_md.encode("utf-8"),
            file_name="validation_report.md",
            mime="text/markdown",
            use_container_width=True,
            disabled=s.validation_report is None,
        )

    with c5:
        st.download_button(
            t("exp_report_html", lang),
            data=report_html.encode("utf-8"),
            file_name="validation_report.html",
            mime="text/html",
            use_container_width=True,
            disabled=s.validation_report is None,
        )


ROUTES = {
    "home": page_home,
    "import": page_import,
    "profile": page_profile,
    "contract": page_contract,
    "validate": page_validate,
    "export": page_export,
}


def main() -> None:
    st.set_page_config(
        page_title="Data Contract Studio",
        page_icon=FAVICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_state()
    load_css()
    restore_session_if_available()
    render_sidebar(VERSION)
    view = render_nav()
    ROUTES[view]()


if __name__ == "__main__":
    main()