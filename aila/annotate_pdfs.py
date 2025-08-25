# %%
import json
from pathlib import Path
from typing import Any, Callable, cast

import fitz as _fitz  # PyMuPDF

# Treat PyMuPDF as Any for static type checking to avoid 'Unknown' propagation
fitz = cast(Any, _fitz)


def annotate_pdfs(
    changes: list[dict[str, str]],
    pdf1_path: str | Path,
    pdf2_path: str | Path,
    out1_path: str | Path,
    out2_path: str | Path,
    circle_radius: int = 8,
    badge_margin_px: int = 14,
    highlight_color: tuple[float, float, float] = (1, 0.9, 0.3),
    stroke_color: tuple[float, float, float] = (0.2, 0.2, 0.2),
    text_color: tuple[float, float, float] = (0, 0, 0),
) -> None:
    """
    Annotate two PDFs with highlights and circled change indices.

    Args:
        changes: list of dicts containing "change_id", "old_text", "new_text", etc.
        pdf1_path: original document 1 (old_text annotations).
        pdf2_path: original document 2 (new_text annotations).
        out1_path: output annotated PDF 1.
        out2_path: output annotated PDF 2.
    """

    # Color map per change type, with a fallback to highlight_color
    type_color_map: dict[str, tuple[float, float, float]] = {
        "Critical": (1.0, 0.4, 0.4),
        "Minor": (1.0, 0.75, 0.3),
        "Formatting": (1.0, 0.95, 0.5),
    }
    type_severity: dict[str, int] = {"Critical": 3, "Minor": 2, "Formatting": 1}

    def _collect_rows(
        doc: Any,
        find_text: str,
        idx_label: str,
        change_type: str,
        page_rows: dict[int, dict[float, Any]],
        row_tol: float = 3.0,
    ) -> bool:
        """Search text, highlight it, and collect row centers per page.

        page_rows: page_index -> {row_center_y -> {"labels": [idx_label, ...], "types": set[str]}}
        """
        found_any = False

        # Determine page count in a robust way
        _pc = getattr(doc, "page_count", None)
        if _pc is None:
            try:
                _pc = len(doc)
            except Exception:
                _pc = 0
        page_count: int = int(_pc)

        for pno in range(page_count):
            page: Any = doc[pno]
            try:
                rects = page.search_for(
                    find_text,
                    flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_DEHYPHENATE,
                )
            except Exception:
                rects = page.search_for(find_text)

            if not rects:
                continue

            found_any = True
            # Highlight matches and collect their row centers
            for r in rects:
                annot = page.add_highlight_annot(r)
                if hasattr(annot, "set_colors"):
                    ch_color = type_color_map.get(change_type, highlight_color)
                    annot.set_colors(stroke=ch_color, fill=ch_color)
                if hasattr(annot, "update"):
                    annot.update()

                row_center = r.y0 + (r.height / 2.0)
                rows = page_rows.setdefault(pno, {})
                # Find an existing bucket within tolerance
                bucket_key: float | None = None
                for existing in rows.keys():
                    if abs(existing - row_center) <= row_tol:
                        bucket_key = existing
                        break
                final_key: float = bucket_key if bucket_key is not None else float(row_center)
                row_entry: Any = rows.setdefault(final_key, {"labels": [], "types": set()})
                if str(idx_label) not in row_entry["labels"]:
                    row_entry["labels"].append(str(idx_label))
                try:
                    row_entry["types"].add(str(change_type))
                except Exception:
                    # Fallback in case set isn't available
                    types_list: list[str] = list(row_entry.get("types", []))
                    if str(change_type) not in types_list:
                        types_list.append(str(change_type))
                    row_entry["types"] = set(types_list)

        return found_any

    def _annotate(
        doc_path: str | Path,
        out_path: str | Path,
        text_key_func: Callable[[dict[str, str]], str | None],
        changes: list[dict[str, str]],
    ) -> None:
        doc: Any = fitz.open(str(doc_path))
        not_found: list[str] = []
        # page_index -> { row_center_y -> {"labels": [...], "types": set[str]} }
        page_rows: dict[int, dict[float, Any]] = {}
        for ch in changes:
            idx = str(ch.get("change_id", "?"))
            target_text = text_key_func(ch)
            ch_type = ch.get("change_type", "")
            if not target_text:
                continue
            ok = _collect_rows(doc, target_text, idx, ch_type, page_rows)
            if not ok:
                not_found.append(idx)

        # Robust page count detection across PyMuPDF versions
        _pc = getattr(doc, "page_count", None)
        if _pc is None:
            try:
                _pc = len(doc)
            except Exception:
                _pc = 0
        page_count: int = int(_pc)

        def _id_key(s: str) -> tuple[int, int | str]:
            try:
                return (0, int(s))
            except Exception:
                return (1, s)

        # Render left-margin numbers per row per page
        left_margin = 10.0  # minimum inset from absolute page left
        left_gutter = 12.0  # space before the leftmost text on the page
        for pno, rows in page_rows.items():
            if pno < 0 or pno >= page_count:
                continue
            page: Any = doc[pno]
            # Determine the left edge of page text content; fallback to page left
            try:
                words_raw: Any = page.get_text("words") or []
                words_list: list[tuple[Any, ...]] = (
                    cast(list[tuple[Any, ...]], words_raw) if isinstance(words_raw, list) else []
                )
                if words_list:
                    page_text_left = min(float(w[0]) for w in words_list if len(w) >= 2)
                else:
                    page_text_left = float(getattr(page.rect, "x0", 0.0))
            except Exception:
                page_text_left = float(getattr(page.rect, "x0", 0.0))

            page_left = float(getattr(page.rect, "x0", 0.0))
            min_left_x = page_left + left_margin
            base_anchor_x = page_text_left - left_gutter
            # Sort rows by vertical position for consistent rendering
            for row_y in sorted(rows.keys()):
                row_entry: Any = rows[row_y]
                labels: list[str] = list(row_entry.get("labels", []))
                sorted_labels = sorted(labels, key=_id_key)
                label_text = ", ".join(sorted_labels)
                # Shift further left if multiple labels to avoid overlap with text
                n = len(labels)
                extra_offset = 0.0
                if n == 2:
                    extra_offset = 10.0
                elif n >= 3:
                    extra_offset = 20.0
                row_x = max(min_left_x, base_anchor_x - extra_offset)
                # Pick label color by highest-severity change type present on this row
                row_types = row_entry.get("types", set())
                chosen_type = None
                try:
                    chosen_type = max(row_types, key=lambda t: type_severity.get(str(t), 0))
                except Exception:
                    chosen_type = None
                label_color = type_color_map.get(str(chosen_type), text_color) if chosen_type else text_color
                page.insert_text(
                    fitz.Point(row_x, row_y),
                    label_text,
                    fontsize=8,
                    color=label_color,
                )
        if not_found and page_count > 0:
            msg = f"Changes not found in this document: {', '.join(not_found)}"
            page: Any = doc[0]
            note_pos = fitz.Point(page.rect.x0 + 36, page.rect.y0 + 36)
            # Pass icon name during creation for broader compatibility
            note = page.add_text_annot(note_pos, msg, icon="Comment")
            if hasattr(note, "update"):
                note.update()

        doc.save(str(out_path))
        doc.close()

    _annotate(pdf1_path, out1_path, lambda ch: ch.get("old_text"), changes)
    _annotate(pdf2_path, out2_path, lambda ch: ch.get("new_text"), changes)


# -------------------- Example --------------------
if __name__ == "__main__":
    # Simple CLI/demo payload for local testing
    payload_json = r"""{}"""

    payload: dict[str, Any] = json.loads(payload_json)
    annotate_pdfs(
        payload["changes"],
        pdf1_path="data/1.pdf",
        pdf2_path="data/2.pdf",
        out1_path="data/1_annotated.pdf",
        out2_path="data/2_annotated.pdf",
    )
