"""Read-only real-browser matrix against apps already owned by the foreground launcher."""

import argparse
import math
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

def local_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")):
        raise argparse.ArgumentTypeError("Use a loopback HTTP app URL without credentials or paths.")
    return value.rstrip("/")


def set_streamlit_checked(page, role, name, checked):
    control = page.get_by_role(role, name=name, exact=True)
    if control.is_checked() != checked:
        # Streamlit styles the input beneath its visible wrapping label.
        # Exercise the user's visible click target, never force the hidden input.
        control.locator("xpath=ancestor::label[1]").get_by_text(name, exact=True).click()
    assert control.is_checked() == checked, f"{name}: label click did not produce the requested checked state."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-dotnet", action="store_true")
    parser.add_argument("--python-url", type=local_url, default="http://127.0.0.1:8501")
    parser.add_argument("--dotnet-url", type=local_url, default="http://127.0.0.1:8503")
    args = parser.parse_args()
    if os.getenv("RUN_LIVE_TESTS") != "1":
        raise SystemExit("Set RUN_LIVE_TESTS=1. This browser matrix calls real Azure services.")
    from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright

    private = Path(__file__).resolve().parents[1] / ".local/validation/original-movies"
    private.mkdir(parents=True, exist_ok=True)
    modes = [
        ("Vector", "Similarity search", "true"),
        ("FullText", "Full text search", "true"),
        ("FullText", "Full text search", "false"),
        ("FullTextRank", "Full text ranking", "true"),
        ("Hybrid", "Hybrid search", "true"),
    ]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = None
        case, implementation = "startup", "browser"
        try:
            page = browser.new_page()
            page.set_default_timeout(180_000)
            for selector, index in (("qflat", "QFLAT & Full Text Search Index"),
                                    ("diskann", "DiskANN & Full Text Search Index")):
                for enabled in (False, True):
                    for mode, button, all_words in modes:
                        case = f"{selector}-{mode}-{all_words}-rerank-{enabled}"
                        implementation = "python"
                        page.goto(args.python_url)
                        page.get_by_role("combobox", name="Index", exact=True).click()
                        page.get_by_role("option", name=index, exact=True).click()
                        query = page.get_by_role("textbox", name="Search input", exact=True)
                        query.fill("SPECTRE spy")
                        query.press("Enter")
                        set_streamlit_checked(page, "checkbox", "Use Semantic Reranker", enabled)
                        set_streamlit_checked(page, "radio",
                                              "all keywords" if all_words == "true" else "any keywords", True)
                        page.get_by_role("button", name=button, exact=True).click()
                        table = page.locator("table")
                        expect(table).to_contain_text("original-movies-v1-spectre", timeout=180_000)
                        expect(page.get_by_text(
                            "Semantic reranking: " + ("✓ Applied" if enabled else "✗ Not applied"),
                            exact=True)).to_be_visible()
                        assert ("rerank_score" in table.inner_text()) is enabled
                        page.screenshot(path=str(private / f"python-{case}.png"))
                        print(f"PASS Python {case}", flush=True)
                        if not args.include_dotnet:
                            continue
                        implementation = "dotnet"
                        page.goto(args.dotnet_url)
                        page.locator("#Query").fill("SPECTRE spy")
                        page.locator("#Container").select_option(selector)
                        page.locator("#Mode").select_option(mode)
                        page.locator("#AllKeywords").select_option(all_words)
                        page.locator("#Rerank").set_checked(enabled)
                        page.get_by_role("button", name="Search", exact=True).click()
                        expect(page.locator("#results")).to_contain_text(
                            "original-movies-v1-spectre", timeout=180_000)
                        assert page.locator("#search-error").count() == 0
                        expect(page.locator("#result-status")).to_have_text(
                            "Reranked results" if enabled else "Retrieval results")
                        scores = page.locator(".rerank-score").all_text_contents()
                        assert scores
                        assert all(math.isfinite(float(score)) if enabled else score == "n/a"
                                   for score in scores)
                        page.screenshot(path=str(private / f"dotnet-{case}.png"))
                        print(f"PASS .NET {case}", flush=True)
        except (AssertionError, PlaywrightError, ValueError):
            if page is not None:
                failure_path = private / f"failure-{implementation}-{case}.png"
                try:
                    page.screenshot(path=str(failure_path), full_page=True, timeout=10_000)
                    print(f"FAIL {implementation} {case}; screenshot: {failure_path}", file=sys.stderr, flush=True)
                except (PlaywrightError, OSError) as capture_error:
                    print(f"Failure screenshot unavailable ({type(capture_error).__name__}); "
                          "preserving the original test failure.", file=sys.stderr, flush=True)
            raise
        finally:
            browser.close()
    print("PASS real browser matrix. No app processes were started or stopped; no data was written.")


if __name__ == "__main__":
    main()
