import time

import pandas as pd
import streamlit as st

from database import db
from modules import extractor, ingestion, po_generator, saw_engine

st.set_page_config(page_title="Local LLM Procurement Pipeline", layout="wide")
db.init_db()

OFFER_COLUMNS = ["supplier", "product", "quantity", "unit", "unit_price", "delivery_days"]


def empty_offers():
    return pd.DataFrame(columns=OFFER_COLUMNS)


def init_state():
    defaults = {
        "raw_text": "",
        "messages": [],
        "draft_for": None,
        "offers": empty_offers(),
        "edited_offers": empty_offers(),
        "editor_version": 0,
        "errors": [],
        "ranked": None,
        "draft": None,
        "timing_log": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clean_records(frame):
    if frame is None or frame.empty:
        return []
    return frame.dropna(how="all").to_dict("records")


init_state()

st.title("Local LLM Procurement Pipeline")
st.caption("Weighted decision heuristic for assisted order dispatching")

with st.sidebar:
    st.header("Settings")
    model_name = st.text_input("Ollama model", value=extractor.MODEL_NAME)
    business_name = st.text_input("Business name")
    buyer_name = st.text_input("Buyer name")
    st.divider()
    st.caption("All processing runs locally. Nothing is sent to external services.")

tab_input, tab_extract, tab_rank, tab_po, tab_history = st.tabs(
    ["1. Input", "2. Extract and review", "3. Rank suppliers", "4. Purchase order", "5. History"]
)

with tab_input:
    st.subheader("Supplier messages and documents")
    pasted = st.text_area(
        "Paste supplier messages from Messenger, Viber or WhatsApp",
        height=220,
        key="pasted_text",
    )
    split_mode = st.radio("How are the pasted messages separated?", ingestion.SPLIT_MODES, horizontal=True)
    uploaded = st.file_uploader("Or upload a PDF, Excel, CSV or text file", type=["pdf", "xlsx", "csv", "txt"])

    if st.button("Load input", type="primary"):
        try:
            messages = []
            if pasted.strip():
                messages.extend(ingestion.split_messages(ingestion.read_pasted_text(pasted), split_mode))
            if uploaded is not None:
                messages.append(ingestion.read_uploaded_file(uploaded))
            if not messages:
                st.warning("Paste some text or upload a file first.")
            else:
                st.session_state.messages = messages
                st.session_state.raw_text = "\n\n".join(messages)
                st.success(f"Loaded {len(messages)} message(s), {len(st.session_state.raw_text):,} characters.")
        except ValueError as exc:
            st.error(str(exc))

    if st.session_state.raw_text:
        with st.expander("Loaded messages preview", expanded=True):
            preview = "\n\n".join(
                f"Message {number}:\n{message}" for number, message in enumerate(st.session_state.messages, start=1)
            )
            st.text(preview[:5000])

with tab_extract:
    st.subheader("Extract offers with the local LLM")
    if not st.session_state.raw_text:
        st.info("Load some input in the first tab.")
    else:
        supplier_name = st.text_input(
            "Supplier name (optional)",
            help="Leave blank to use the supplier named in each message. If filled in, it is applied to every offer extracted in this run.",
        )
        if st.button("Run extraction", type="primary"):
            with st.spinner("The local model is reading the messages..."):
                try:
                    started = time.perf_counter()
                    result = extractor.extract_messages(
                        st.session_state.messages, model=model_name, supplier=supplier_name
                    )
                    elapsed = time.perf_counter() - started
                    st.session_state.timing_log.append(
                        {
                            "run": len(st.session_state.timing_log) + 1,
                            "seconds": round(elapsed, 1),
                            "messages": result["message_count"],
                            "characters": len(st.session_state.raw_text),
                            "offers_extracted": len(result["offers"]),
                            "rejected": len(result["errors"]),
                            "model": model_name,
                        }
                    )
                    st.session_state.offers = pd.DataFrame(result["offers"], columns=OFFER_COLUMNS)
                    st.session_state.edited_offers = st.session_state.offers
                    st.session_state.errors = result["errors"]
                    st.session_state.editor_version += 1
                    st.session_state.ranked = None
                    st.session_state.draft = None
                    st.session_state.draft_for = None
                except extractor.ExtractionError as exc:
                    st.error(str(exc))

        if st.session_state.timing_log:
            last = st.session_state.timing_log[-1]
            st.info(f"Last extraction took {last['seconds']} seconds ({last['offers_extracted']} offer(s) extracted).")
            with st.expander("Extraction timing log"):
                st.dataframe(pd.DataFrame(st.session_state.timing_log), hide_index=True, width="stretch")

        for message in st.session_state.errors:
            st.warning(message)

        st.caption("Review and correct the extracted values. You can also add or delete rows.")
        edited = st.data_editor(
            st.session_state.offers,
            num_rows="dynamic",
            width="stretch",
            key=f"offers_editor_{st.session_state.editor_version}",
        )
        st.session_state.edited_offers = edited

        if st.button("Save offers to database"):
            valid, errors = extractor.validate_offers(clean_records(edited))
            for message in errors:
                st.warning(message)
            if valid:
                saved = db.save_offers(valid, source_text=st.session_state.raw_text)
                st.success(f"Saved {saved} offer(s) to the database.")
            elif not errors:
                st.info("There are no offers to save.")

with tab_rank:
    st.subheader("Weighted decision heuristic (SAW)")
    valid_offers, _ = extractor.validate_offers(clean_records(st.session_state.edited_offers))
    if not valid_offers:
        st.info("Extract and review offers first.")
    else:
        products = sorted({offer["product"] for offer in valid_offers})
        product = st.selectbox("Product", products)
        price_weight = st.slider("Price importance (%)", 0, 100, 60)
        delivery_weight = 100 - price_weight
        st.caption(f"Delivery time importance: {delivery_weight}%")

        if st.button("Rank suppliers", type="primary"):
            candidates = [offer for offer in valid_offers if offer["product"] == product]
            st.session_state.ranked = saw_engine.rank_offers(
                candidates,
                {"unit_price": price_weight / 100, "delivery_days": delivery_weight / 100},
            )
            st.session_state.draft = None
            st.session_state.draft_for = None

        if st.session_state.ranked:
            ranked_frame = pd.DataFrame(st.session_state.ranked)
            columns = [
                "rank",
                "supplier",
                "product",
                "quantity",
                "unit",
                "unit_price",
                "delivery_days",
                "norm_unit_price",
                "norm_delivery_days",
                "utility_score",
            ]
            st.dataframe(ranked_frame[columns], hide_index=True, width="stretch")
            st.bar_chart(ranked_frame.set_index("supplier")["utility_score"])
            top = st.session_state.ranked[0]
            st.success(f"Top supplier: {top['supplier']} with a utility score of {top['utility_score']:.4f}")

with tab_po:
    st.subheader("Purchase order draft")
    if not st.session_state.ranked:
        st.info("Rank suppliers first.")
    else:
        ranked = st.session_state.ranked
        labels = [f"{row['rank']}. {row['supplier']} (score {row['utility_score']:.4f})" for row in ranked]
        choice = st.selectbox("Supplier for this purchase order", labels, index=0)
        best = ranked[labels.index(choice)]
        channel = st.radio("Send through", po_generator.CHANNELS, horizontal=True)

        if st.button("Generate draft", type="primary"):
            st.session_state.draft = po_generator.generate_po_draft(
                best, channel, business_name=business_name, buyer_name=buyer_name
            )
            st.session_state.draft_for = (choice, channel)

        if st.session_state.draft and st.session_state.draft_for != (choice, channel):
            st.info("The supplier or channel changed. Click Generate draft to update the draft.")
        elif st.session_state.draft:
            draft = st.session_state.draft
            subject = draft["subject"]
            if subject:
                subject = st.text_input("Subject", value=subject)
            body = st.text_area("Message", value=draft["body"], height=340)
            final_text = f"Subject: {subject}\n\n{body}" if subject else body
            st.caption("Copy-ready text")
            st.code(final_text, language=None)
            st.caption("Review and edit the draft, then copy it into your email or messaging app. Orders are never sent automatically.")

            if st.button("Save to purchase order history"):
                order_id = db.save_purchase_order(best, channel, final_text)
                st.success(f"Saved purchase order #{order_id}.")

with tab_history:
    st.subheader("Saved purchase orders")
    orders = db.get_purchase_orders()
    if orders:
        st.dataframe(pd.DataFrame(orders).drop(columns=["draft_text"]), hide_index=True, width="stretch")
    else:
        st.info("No purchase orders saved yet.")

    st.subheader("Saved offers")
    saved_offers = db.get_offers()
    if saved_offers:
        st.dataframe(pd.DataFrame(saved_offers), hide_index=True, width="stretch")
    else:
        st.info("No offers saved yet.")
