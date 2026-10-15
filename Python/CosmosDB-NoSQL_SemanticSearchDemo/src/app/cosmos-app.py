"""Original Streamlit controls backed by standalone Azure Data AI reranking."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import search_demo as demo

st.set_page_config(page_title="Azure Cosmos DB Semantic Search Demo", layout="wide",
                   initial_sidebar_state="expanded")

INDEX_NAMES = {
    "QFLAT & Full Text Search Index": "search_qflat",
    "DiskANN & Full Text Search Index": "search_diskann",
}


def run_search(mode):
    # Clear old success before any operation, including embedding/configuration failures.
    st.session_state.pop("search_result", None)
    st.session_state.pop("suggested_listings", None)
    st.session_state.pop("search_error", None)
    try:
        result = demo.search(
            demo.get_container(INDEX_NAMES[st.session_state.index_selection]),
            mode, st.session_state.user_query,
            use_reranker=st.session_state.get("use_reranker", False),
            search_type=st.session_state.get("full_text_search_type", "all keywords"))
        st.session_state.search_result = result
        st.session_state.suggested_listings = pd.DataFrame(result.rows)
    except (demo.SearchError, ValueError) as exc:
        st.session_state.search_error = str(exc)
    except Exception:
        st.session_state.search_error = (
            "Search could not start. Check environment settings, Azure CLI/managed identity, "
            "resource permissions and network access.")


with st.sidebar:
    st.selectbox("Index", options=list(INDEX_NAMES), index=0, key="index_selection")
    st.text_input("Search input", placeholder="James Bond", key="user_query")
    st.checkbox("Use Semantic Reranker", key="use_reranker",
                help="Apply semantic reranking with the standalone Azure Data AI inference service")
    disabled = not st.session_state.user_query.strip()
    st.button("Similarity search", key="location_search", disabled=disabled,
              on_click=run_search, args=("vector",))
    st.button("Full text ranking", key="full_text_ranking", disabled=disabled,
              on_click=run_search, args=("ranking",))
    st.button("Hybrid search", key="hybrid_search", disabled=disabled,
              on_click=run_search, args=("hybrid",))
    st.radio("Search type", options=["all keywords", "any keywords"], key="full_text_search_type")
    st.button("Full text search", key="full_text_search", disabled=disabled,
              on_click=run_search, args=("fulltext",))
    st.write("---")
    st.markdown("[Cosmos DB Samples Gallery](https://azurecosmosdb.github.io/gallery/)")
    st.markdown("[GitHub](https://github.com/microsoft/AzureDataRetrievalAugmentedGenerationSamples)")

st.title("Azure Cosmos DB - Semantic Search Demo")
st.write("Showcasing vector search, full text search, text ranking, hybrid search, "
         "and semantic reranking capabilities.")
st.write("---")

if st.session_state.get("search_error"):
    st.error(st.session_state.search_error)
elif "search_result" in st.session_state:
    result = st.session_state.search_result
    st.write(f"Executed query: {result.query}")
    st.write(f"Embedding generation time: {result.embedding_seconds:.4f} seconds")
    st.write(f"Total end-to-end query execution time: {result.total_seconds:.4f} seconds")
    st.write(f"Retrieval time: {result.retrieval_seconds:.4f} seconds")
    st.write(f"Reranking time: {result.rerank_seconds:.4f} seconds")
    server_time = (f"{result.server_seconds:.4f} seconds"
                   if result.server_seconds is not None else "Not reported")
    ru = f"{result.ru:.2f}" if result.ru is not None else "Not reported"
    st.write(f"Total server query execution time: {server_time}")
    st.write(f"RU consumed: {ru}")
    st.write(f"Semantic reranking: {'✓ Applied' if result.reranked else '✗ Not applied'}")
    st.write(f"Found {len(result.rows)} records.")
    st.table(st.session_state.suggested_listings)
else:
    st.write("Enter text to get started.")
