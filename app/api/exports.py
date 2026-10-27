"""Export endpoints — Excel, PDF, CSV and JSON, generated on the server.

Exports are a Pro feature (see app/api/main.py). The catalogue export takes the
same filters as the catalogue plus an explicit selection (`keys` for perfume
cards, `ids` for shop listings); the analytics export writes every section of
the cabinet. All four formats come from one list of tables, so the columns
match whichever format the user picks.

Streaming responses with proper Content-Type and Content-Disposition so
browsers trigger a download dialog.

Period parameter (1w/1m/3m/6m/1y/all) filters PriceHistory rows before
serialization. Polished in S19.4: product image embed (httpx, 3s timeout with
brand-initial placeholder fallback), LineChart embedded in Price History
sheet, conditional formatting, branded Summary hero, PDF delta badge + section
dividers, catalog header banner with filter description + page numbers.
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta
import csv
import json
from dataclasses import dataclass
from typing import Any, List, Optional

# matplotlib MUST use Agg backend before pyplot import — Docker has no display.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl.chart import LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as XLImage
from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.api.cards import cards_for_keys, query_cards, query_listings
from app.api.deps import get_db
from app.domain.models import Product
from app.services import market
from app.services.price_series import STORE_LABELS, store_key, store_label

router = APIRouter(prefix="/exports", tags=["exports"])

_FORMATS = "^(xlsx|pdf|csv|json)$"


# ── Constants ─────────────────────────────────────────────────────────────────

PERIOD_DAYS = {"1w": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365, "all": None}
PERIOD_LABEL = {"1w": "1 Week", "1m": "1 Month", "3m": "3 Months", "6m": "6 Months", "1y": "1 Year", "all": "All time"}

CHANGE_LABEL = {
    "synthetic": "Estimate",
    "initial": "Initial",
    "price_down": "Drop",
    "price_up": "Rise",
    "no_change": "Flat",
    "back_in_stock": "Restocked",
    "out_of_stock": "OOS",
}
CHANGE_FILL = {
    "synthetic": "DCEEF6",      # light blue
    "initial": "E5E7EB",        # gray
    "price_down": "DCFCE7",     # green
    "price_up": "FEE2E2",       # red
    "no_change": "F1F5F9",      # near-gray
    "back_in_stock": "DCFCE7",  # green
    "out_of_stock": "FEE2E2",   # red
}

# Brand palette
# Ink, accent and the down/up colours of the site (see frontend/src/index.css).
TEAL = "111315"
TEAL_DARK = "111315"
ACCENT = "D0106F"
GREEN = "1D7A3E"
RED = "B3262F"
GRAY = "6B7280"
LIGHT = "F4F6F8"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _period_cutoff(period: str) -> Optional[datetime]:
    days = PERIOD_DAYS.get(period)
    if days is None:
        return None
    return datetime.utcnow() - timedelta(days=days)


def _safe_filename(s: str, max_len: int = 60) -> str:
    keep = "-_.() "
    out = "".join(c if c.isalnum() or c in keep else "_" for c in s).strip()
    return (out[:max_len] or "export").rstrip(".")


def _stream(buf: io.BytesIO, filename: str, media_type: str) -> StreamingResponse:
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _fetch_image_bytes(url: Optional[str], timeout: float = 3.0) -> Optional[bytes]:
    """Best-effort image fetch. Returns None on any failure — caller renders placeholder."""
    if not url or not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as cli:
            r = cli.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; MarketPulse/1.0)"})
            ct = r.headers.get("content-type", "")
            if r.status_code == 200 and ct.startswith("image/") and r.content:
                return r.content
    except (httpx.HTTPError, httpx.TimeoutException, Exception):
        pass
    return None


def _delta_percent(current: float, previous: Optional[float]) -> Optional[float]:
    if not previous or previous <= 0 or previous == current:
        return None
    return ((current - previous) / previous) * 100


def _delta_str(current: float, previous: Optional[float]) -> str:
    pct = _delta_percent(current, previous)
    if pct is None:
        return "flat"
    return f"{pct:+.1f}%"


def _render_history_png(
    history_rows: list[tuple[datetime, float]],
    title: str = "",
    width_px: int = 1200,
    height_px: int = 460,
) -> io.BytesIO:
    """Render a polished area chart of price history to a PNG BytesIO."""
    fig, ax = plt.subplots(figsize=(width_px / 100, height_px / 100), dpi=100)
    if history_rows:
        xs = [r[0] for r in history_rows]
        ys = [r[1] for r in history_rows]
        ax.plot(xs, ys, color="#1F4E5F", linewidth=2.2)
        ax.fill_between(xs, ys, alpha=0.18, color="#3CB6B0")
        ax.set_ylim(min(ys) * 0.94, max(ys) * 1.06)
    else:
        ax.text(0.5, 0.5, "No price history in this period",
                ha="center", va="center", transform=ax.transAxes,
                color="#888", fontsize=12)
        ax.set_xticks([])
        ax.set_yticks([])

    if title:
        ax.set_title(title, fontsize=12, loc="left", color="#222", pad=10)
    ax.tick_params(axis="both", labelsize=9, colors="#555")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#CBD5E1")
    ax.grid(True, alpha=0.20, linewidth=0.6, color="#94A3B8")
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_placeholder_png(brand: Optional[str], size_px: int = 320) -> io.BytesIO:
    """Render a teal square with the brand's initial centered — fallback when image fetch fails."""
    initial = (brand or "?").strip()[:1].upper() or "?"
    fig, ax = plt.subplots(figsize=(size_px / 100, size_px / 100), dpi=100)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_facecolor("#1F4E5F")
    fig.patch.set_facecolor("#1F4E5F")
    ax.text(0.5, 0.5, initial, ha="center", va="center", color="white",
            fontsize=120, fontweight="bold", family="DejaVu Sans")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor="#1F4E5F", pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Excel — single product ───────────────────────────────────────────────────


def _apply_box_border(ws, cell_range: str, color: str = "111827", thickness: str = "thin") -> None:
    """Draw a thin border ONLY around the outer perimeter of the range."""
    side = Side(border_style=thickness, color=color)
    from openpyxl.utils.cell import range_boundaries
    min_col, min_row, max_col, max_row = range_boundaries(cell_range)
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            cell = ws.cell(row=r, column=c)
            left = side if c == min_col else cell.border.left
            right = side if c == max_col else cell.border.right
            top = side if r == min_row else cell.border.top
            bottom = side if r == max_row else cell.border.bottom
            cell.border = Border(left=left, right=right, top=top, bottom=bottom)


def _apply_grid_border(ws, cell_range: str, color: str = "111827", thickness: str = "thin") -> None:
    """Draw borders on EVERY cell in the range (outer + inner cell separators)."""
    side = Side(border_style=thickness, color=color)
    from openpyxl.utils.cell import range_boundaries
    min_col, min_row, max_col, max_row = range_boundaries(cell_range)
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            ws.cell(row=r, column=c).border = Border(left=side, right=side, top=side, bottom=side)


def _add_horizontal_divider(ws, row: int, min_col: int, max_col: int, color: str = "111827") -> None:
    """Add a thin horizontal line below the given row across columns."""
    side = Side(border_style="thin", color=color)
    for c in range(min_col, max_col + 1):
        cell = ws.cell(row=row, column=c)
        b = cell.border
        cell.border = Border(left=b.left, right=b.right, top=b.top, bottom=side)


def _build_product_xlsx(product: Product, history_rows: list, offer_rows: list, period: str) -> io.BytesIO:
    """3-sheet workbook with classic spreadsheet aesthetic: gridlines visible,
    black borders around tables, no large teal banners (just bold headings)."""
    import openpyxl
    wb = openpyxl.Workbook()

    current = float(product.last_price) if product.last_price else 0.0
    previous = float(product.old_price) if product.old_price else current
    pct = _delta_percent(current, previous)

    # ── Summary ──────────────────────────────────────────────────────────────
    # Layout spec (user-driven, S19.4 final):
    #   (1) Light gray fill on A1:C6, with outer box border around it
    #   (2) A3:C3 bottom border (inner divider inside the gray block)
    #   (3) A9:C9 bottom border (closes the price section below the gray block)
    #   (4) C7:C9 right border (vertical line below the gray block's right edge)
    #   (5) E1:E9 right border (rightmost vertical line of the summary canvas)
    #   (6) Image roughly centered in D4:E9
    #   (7) A11:A14 each cell has all 4 borders (label column of data table)
    #   (8) B11:E11..B14:E14 merged into one cell per row, text left-aligned
    s = wb.active
    s.title = "Summary"

    # Reusable thin black border side
    BSIDE = Side(border_style="thin", color="111827")

    # (1) Light gray fill on A1:C6
    HERO_BG = "F0F0F0"
    hero_fill = PatternFill("solid", fgColor=HERO_BG)
    for r in range(1, 7):
        for c in range(1, 4):  # cols A=1, B=2, C=3
            s.cell(row=r, column=c).fill = hero_fill
    # (1) Outer box border around the gray block
    _apply_box_border(s, "A1:C6", color="111827")

    # (2) A3:C3 bottom border
    for c in range(1, 4):
        cell = s.cell(row=3, column=c)
        b = cell.border
        cell.border = Border(left=b.left, right=b.right, top=b.top, bottom=BSIDE)

    # (3) A9:C9 bottom border
    for c in range(1, 4):
        cell = s.cell(row=9, column=c)
        b = cell.border
        cell.border = Border(left=b.left, right=b.right, top=b.top, bottom=BSIDE)

    # (4) C7:C9 right border
    for r in range(7, 10):
        cell = s.cell(row=r, column=3)
        b = cell.border
        cell.border = Border(left=b.left, right=BSIDE, top=b.top, bottom=b.bottom)

    # (5) E1:E10 right border (the rightmost vertical line, extended through row 10
    # so the gap row between the gray block and the data table is also bounded).
    for r in range(1, 11):
        cell = s.cell(row=r, column=5)
        b = cell.border
        cell.border = Border(left=b.left, right=BSIDE, top=b.top, bottom=b.bottom)

    # ── Text content within the gray block ──
    s["A1"] = "MarketPulse — Price Report"
    s["A1"].font = Font(name="Calibri", size=16, bold=True, color="111827")
    s["A2"] = f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  ·  Period: {PERIOD_LABEL.get(period, period)}"
    s["A2"].font = Font(name="Calibri", size=10, color=GRAY)

    s["A4"] = (product.brand or "—").upper()
    s["A4"].font = Font(name="Calibri", size=11, bold=True, color="111827")

    s["A5"] = product.title or "—"
    s["A5"].font = Font(name="Calibri", size=16, bold=True, color="111827")
    s.row_dimensions[5].height = 22

    tags = " · ".join(
        x for x in [
            (product.volume or "").upper() or None,
            (product.concentration or "") or None,
            (product.search_term or "").capitalize() or None,
        ] if x
    )
    s["A6"] = tags
    s["A6"].font = Font(name="Calibri", size=10, color=GRAY)

    # ── Price row (row 8 — below the gray block) ──
    s["A8"] = f"{current:.2f} €"
    s["A8"].font = Font(name="Calibri", size=24, bold=True,
                        color=(GREEN if (pct or 0) < 0 else (RED if (pct or 0) > 0 else "111827")))
    s.row_dimensions[8].height = 32

    if pct is not None:
        s["B8"] = f"was {previous:.2f} €"
        s["B8"].font = Font(name="Calibri", size=11, italic=True, strike=True, color=GRAY)
        s["B8"].alignment = Alignment(vertical="center")
        s["C8"] = f"{pct:+.1f}%"
        s["C8"].font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
        s["C8"].fill = PatternFill("solid", fgColor=(GREEN if pct < 0 else RED))
        s["C8"].alignment = Alignment(horizontal="center", vertical="center")
        # Restore the right border on C8 — fill assignment doesn't touch border,
        # but explicit re-set keeps the C7:C9 vertical line continuous.
        cb = s["C8"].border
        s["C8"].border = Border(left=cb.left, right=BSIDE, top=cb.top, bottom=cb.bottom)

    # (6) Image roughly centered in D4:E9 using OneCellAnchor with pixel offsets
    img_bytes = _fetch_image_bytes(product.image_url)
    img_buf = io.BytesIO(img_bytes) if img_bytes else _make_placeholder_png(product.brand)
    try:
        from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
        from openpyxl.drawing.xdr import XDRPositiveSize2D
        from openpyxl.utils.units import pixels_to_EMU

        xl_img = XLImage(img_buf)
        img_size = 110
        xl_img.width = img_size
        xl_img.height = img_size
        # D4 = col index 3 (D), row index 3 (4th row), both 0-indexed.
        # Offsets nudge the image rightward & downward so it sits centered
        # in the D4:E9 area instead of glued to the top-left corner.
        xl_img.anchor = OneCellAnchor(
            _from=AnchorMarker(col=3, colOff=pixels_to_EMU(40), row=3, rowOff=pixels_to_EMU(15)),
            ext=XDRPositiveSize2D(cx=pixels_to_EMU(img_size), cy=pixels_to_EMU(img_size)),
        )
        s.add_image(xl_img)
    except Exception:
        pass

    # ── Data table (rows 11-14) ──
    rows_data = [
        ("In stock", "Yes" if product.is_available else "No"),
        ("Store", (product.search_term or "—").capitalize()),
        ("URL", product.url or "—"),
        ("Exported at", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")),
    ]
    full_border = Border(left=BSIDE, right=BSIDE, top=BSIDE, bottom=BSIDE)
    for i, (k, v) in enumerate(rows_data, start=11):
        # (7) Label cell A — all 4 borders
        a = s.cell(row=i, column=1, value=k)
        a.font = Font(name="Calibri", size=10, bold=True, color="111827")
        a.border = full_border
        a.alignment = Alignment(horizontal="left", vertical="center")

        # (8) Value cell merged B:E, text left-aligned
        s.merge_cells(start_row=i, start_column=2, end_row=i, end_column=5)
        v_cell = s.cell(row=i, column=2, value=v)
        v_cell.font = Font(name="Calibri", size=10, color="111827")
        v_cell.alignment = Alignment(horizontal="left", vertical="center")

        # Border around the merged B:E range. openpyxl only shows borders on
        # cells you explicitly mark — for a merged range, set the appropriate
        # side on each underlying cell so the visual frame is complete.
        # B = left edge; C,D = middle (top/bottom only); E = right edge.
        s.cell(row=i, column=2).border = Border(left=BSIDE, right=None, top=BSIDE, bottom=BSIDE)
        s.cell(row=i, column=3).border = Border(left=None, right=None, top=BSIDE, bottom=BSIDE)
        s.cell(row=i, column=4).border = Border(left=None, right=None, top=BSIDE, bottom=BSIDE)
        s.cell(row=i, column=5).border = Border(left=None, right=BSIDE, top=BSIDE, bottom=BSIDE)

    # URL hyperlink — row 13 (third data row)
    if product.url:
        url_cell = s.cell(row=13, column=2)
        url_cell.hyperlink = product.url
        url_cell.font = Font(name="Calibri", size=10, color="2563EB", underline="single")

    # Column widths — chosen so D+E together roughly form a square area for the image
    s.column_dimensions["A"].width = 12
    s.column_dimensions["B"].width = 24
    s.column_dimensions["C"].width = 12
    s.column_dimensions["D"].width = 8
    s.column_dimensions["E"].width = 18

    # ── Price History ────────────────────────────────────────────────────────
    h = wb.create_sheet("Price History")
    h["A1"] = f"Price History — {PERIOD_LABEL.get(period, period)}"
    h["A1"].font = Font(size=14, bold=True, color="111827")
    h.row_dimensions[1].height = 22

    headers = ["Date", "Price (€)", "In stock", "Change"]
    header_row = 3
    for ci, label in enumerate(headers, start=1):
        c = h.cell(row=header_row, column=ci, value=label)
        c.font = Font(bold=True, color="111827")
        c.alignment = Alignment(horizontal="left")

    if not history_rows:
        h.cell(row=4, column=1, value="—")
        h.cell(row=4, column=2, value=0)
        h.cell(row=4, column=3, value="—")
        h.cell(row=4, column=4, value="no data")
        last_row = 4
    else:
        for ri, row in enumerate(history_rows, start=4):
            ct = row.change_type or ""
            h.cell(row=ri, column=1, value=row.parsed_at.strftime("%Y-%m-%d %H:%M")).alignment = Alignment(horizontal="left")
            h.cell(row=ri, column=2, value=float(row.price)).number_format = "0.00"
            h.cell(row=ri, column=3, value="Yes" if row.in_stock else "No").alignment = Alignment(horizontal="center")
            label_cell = h.cell(row=ri, column=4, value=CHANGE_LABEL.get(ct, ct))
            label_cell.alignment = Alignment(horizontal="left")
            fill_hex = CHANGE_FILL.get(ct)
            if fill_hex:
                label_cell.fill = PatternFill("solid", fgColor=fill_hex)
        last_row = 3 + len(history_rows)

        # Conditional formatting on price column (color scale)
        rule = ColorScaleRule(start_type="min", start_color="DCFCE7",
                              mid_type="percentile", mid_value=50, mid_color="FEF3C7",
                              end_type="max", end_color="FEE2E2")
        h.conditional_formatting.add(f"B4:B{last_row}", rule)

        # Embedded LineChart with explicit axis labels (some Excel versions
        # otherwise render numbers as blank ticks).
        if len(history_rows) >= 2:
            chart = LineChart()
            chart.title = "Price trend"
            chart.y_axis.title = "Price (€)"
            chart.x_axis.title = "Date"
            chart.y_axis.delete = False
            chart.x_axis.delete = False
            chart.y_axis.tickLblPos = "nextTo"
            chart.x_axis.tickLblPos = "nextTo"
            # Drop legend (one series — legend is just noise)
            chart.legend = None
            chart.height = 10
            chart.width = 22
            data_ref = Reference(h, min_col=2, min_row=header_row, max_col=2, max_row=last_row)
            cats_ref = Reference(h, min_col=1, min_row=4, max_row=last_row)
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats_ref)
            h.add_chart(chart, "F3")

    # Full grid borders on every cell in the table (cell-by-cell, not just outer frame)
    _apply_grid_border(h, f"A{header_row}:D{last_row}", color="111827")

    h.column_dimensions["A"].width = 22
    h.column_dimensions["B"].width = 14
    h.column_dimensions["C"].width = 12
    h.column_dimensions["D"].width = 14
    # No freeze_panes — interacted badly with merged banner on prior version, plain header reads fine

    # ── Offers ───────────────────────────────────────────────────────────────
    o = wb.create_sheet("Offers")
    o["A1"] = "Offers by Store"
    o["A1"].font = Font(size=14, bold=True, color="111827")
    o.row_dimensions[1].height = 22

    offer_headers = ["Store", "Price (€)", "Previous (€)", "Change %", "URL"]
    offer_header_row = 3
    for ci, label in enumerate(offer_headers, start=1):
        c = o.cell(row=offer_header_row, column=ci, value=label)
        c.font = Font(bold=True, color="111827")
        c.alignment = Alignment(horizontal="left")

    if not offer_rows:
        o.cell(row=4, column=1, value="—")
        offer_last_row = 4
    else:
        for ri, p in enumerate(offer_rows, start=4):
            op = float(p.last_price) if p.last_price else 0
            oo = float(p.old_price) if p.old_price else op
            opct = _delta_percent(op, oo)
            o.cell(row=ri, column=1, value=(p.search_term or "—").capitalize()).alignment = Alignment(horizontal="left")
            o.cell(row=ri, column=2, value=op).number_format = "0.00"
            o.cell(row=ri, column=3, value=oo).number_format = "0.00"
            ch_cell = o.cell(row=ri, column=4, value=f"{opct:+.1f}%" if opct is not None else "flat")
            ch_cell.alignment = Alignment(horizontal="center")
            if opct is not None:
                ch_cell.font = Font(bold=True, color="FFFFFF")
                ch_cell.fill = PatternFill("solid", fgColor=(GREEN if opct < 0 else RED))
            url_cell = o.cell(row=ri, column=5, value=p.url or "—")
            if p.url:
                url_cell.hyperlink = p.url
                url_cell.font = Font(color="2563EB", underline="single")
        offer_last_row = 3 + len(offer_rows)

        if len(offer_rows) == 1:
            note_row = offer_last_row + 2
            o.cell(row=note_row, column=1, value="Only one store currently carries this product at this volume.").font = Font(italic=True, color=GRAY)

    # Full grid borders on every cell
    _apply_grid_border(o, f"A{offer_header_row}:E{offer_last_row}", color="111827")

    o.column_dimensions["A"].width = 22
    o.column_dimensions["B"].width = 14
    o.column_dimensions["C"].width = 14
    o.column_dimensions["D"].width = 14
    o.column_dimensions["E"].width = 60

    buf = io.BytesIO()
    wb.save(buf)
    return buf


# ── Excel — catalog ──────────────────────────────────────────────────────────


# ── PDF — single product ─────────────────────────────────────────────────────


def _pdf_styles():
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MPTitle", parent=styles["Heading1"],
        fontName="Helvetica-Bold", fontSize=18, leading=22,
        textColor=rl_colors.HexColor(f"#{TEAL}"), spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        "MPSub", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9, textColor=rl_colors.HexColor("#6B7280"),
        spaceAfter=10,
    )
    h2 = ParagraphStyle(
        "MPH2", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=11,
        textColor=rl_colors.HexColor("#111827"), spaceBefore=10, spaceAfter=6,
    )
    body = ParagraphStyle(
        "MPBody", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, leading=14, textColor=rl_colors.HexColor("#1F2937"),
    )
    small = ParagraphStyle(
        "MPSmall", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, textColor=rl_colors.HexColor("#6B7280"),
    )
    return title_style, sub_style, h2, body, small


def _build_product_pdf(product: Product, history_rows: list, offer_rows: list, period: str) -> io.BytesIO:
    """Polished one-page A4 product report with product image + chart + colored delta badge."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.4 * cm, bottomMargin=1.4 * cm,
        leftMargin=1.4 * cm, rightMargin=1.4 * cm,
        title=f"MarketPulse — {product.title}",
    )
    title_style, sub_style, h2, body, small = _pdf_styles()
    story = []

    # Header
    story.append(Paragraph("MarketPulse · Price Report", title_style))
    story.append(Paragraph(
        f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  ·  "
        f"Period: <b>{PERIOD_LABEL.get(period, period)}</b>",
        sub_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1.4, color=rl_colors.HexColor(f"#{TEAL}"), spaceAfter=8))

    # Hero block
    brand = (product.brand or "—").upper()
    title = product.title or "—"
    volume = product.volume or "—"
    conc = product.concentration or "—"
    store = (product.search_term or "—").capitalize()
    current = float(product.last_price) if product.last_price else 0.0
    prev = float(product.old_price) if product.old_price else current
    pct = _delta_percent(current, prev)
    pct_text = f"{pct:+.1f}%" if pct is not None else "flat"

    # Image (or placeholder)
    img_bytes = _fetch_image_bytes(product.image_url)
    if img_bytes:
        img_flow = RLImage(io.BytesIO(img_bytes), width=3.5 * cm, height=3.5 * cm, kind="proportional")
    else:
        img_flow = RLImage(_make_placeholder_png(product.brand, size_px=200),
                           width=3.5 * cm, height=3.5 * cm)

    # Delta badge text
    if pct is None:
        delta_color = rl_colors.HexColor("#6B7280")
    elif pct < 0:
        delta_color = rl_colors.HexColor(f"#{GREEN}")
    else:
        delta_color = rl_colors.HexColor(f"#{RED}")

    info_cell = [
        Paragraph(f'<font color="#{TEAL}"><b>{brand}</b></font>', body),
        Paragraph(f'<font size="14"><b>{title}</b></font>', body),
        Paragraph(f'<font color="#6B7280">{volume} · {conc} · {store}</font>', small),
        Spacer(1, 6),
        Paragraph(
            f'<font size="20" color="#111827"><b>{current:.2f} €</b></font>  '
            f'<font color="#9CA3AF"><strike>was {prev:.2f} €</strike></font>  '
            f'<font color="#{delta_color.hexval()[2:]}"><b>{pct_text}</b></font>',
            body
        ),
    ]

    hero_tbl = Table(
        [[img_flow, info_cell]],
        colWidths=[3.7 * cm, 14.0 * cm],
    )
    hero_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(hero_tbl)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.4, color=rl_colors.HexColor("#E5E7EB"), spaceAfter=8))

    # Chart
    story.append(Paragraph(f"Price history — {PERIOD_LABEL.get(period, period)}", h2))
    chart_data = [(h.parsed_at, float(h.price)) for h in history_rows]
    png = _render_history_png(chart_data, width_px=1200, height_px=500)
    story.append(RLImage(png, width=17.5 * cm, height=7.3 * cm))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.4, color=rl_colors.HexColor("#E5E7EB"), spaceAfter=8))

    # Quick stats — derived from history (or product fields if history empty)
    story.append(Paragraph("Quick stats", h2))
    prices = [float(h.price) for h in history_rows if h.price]
    if prices:
        lo = min(prices)
        hi = max(prices)
        avg = sum(prices) / len(prices)
        obs = len(prices)
        spread = ((hi - lo) / lo * 100) if lo > 0 else 0.0
    else:
        lo = hi = avg = current
        obs = 0
        spread = 0.0

    stats_data = [
        ["Lowest", "Highest", "Average", "Current", "Observations", "Spread"],
        [f"{lo:.2f} €", f"{hi:.2f} €", f"{avg:.2f} €", f"{current:.2f} €", f"{obs}", f"{spread:.1f}%"],
    ]
    stats_tbl = Table(stats_data, colWidths=[2.9 * cm] * 6)
    stats_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor(f"#{LIGHT}")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.HexColor("#6B7280")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("FONTSIZE", (0, 1), (-1, 1), 11),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (-1, 1), rl_colors.HexColor("#111827")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#D1D5DB")),
    ]))
    story.append(stats_tbl)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.4, color=rl_colors.HexColor("#E5E7EB"), spaceAfter=8))

    # Offers
    story.append(Paragraph("Offers by store", h2))
    offer_data = [["Store", "Price (€)", "Previous (€)", "Change"]]
    for p in offer_rows[:8]:
        op = float(p.last_price) if p.last_price else 0
        oo = float(p.old_price) if p.old_price else op
        opct = _delta_percent(op, oo)
        offer_data.append([
            (p.search_term or "—").capitalize(),
            f"{op:.2f}",
            f"{oo:.2f}",
            f"{opct:+.1f}%" if opct is not None else "flat",
        ])
    if len(offer_data) == 1:
        offer_data.append(["—", "—", "—", "—"])
    offers_tbl = Table(offer_data, colWidths=[5 * cm, 4 * cm, 4 * cm, 4 * cm])
    offers_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor(f"#{TEAL_DARK}")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        # Store column: LEFT-aligned (header + values)
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        # Numeric columns: RIGHT-aligned (header + values), so columns line up
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor(f"#{LIGHT}")]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, rl_colors.HexColor(f"#{TEAL}")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(offers_tbl)
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.4, color=rl_colors.HexColor("#E5E7EB"), spaceAfter=6))

    # Footer
    story.append(Paragraph(
        "marketpulse1.me  ·  perfume prices in Latvian shops, checked nightly",
        small,
    ))

    doc.build(story)
    return buf


# ── PDF — catalog ────────────────────────────────────────────────────────────


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/products/{product_id}")
async def export_product(
    product_id: int,
    format: str = Query("xlsx", pattern=_FORMATS),
    period: str = Query("3m", pattern="^(1w|1m|3m|6m|1y|all)$"),
    db: AsyncSession = Depends(get_db),
):
    """Export a single product: price history and today's shop prices."""
    stmt = (
        select(Product)
        .options(selectinload(Product.history))
        .where(Product.id == product_id)
    )
    product = (await db.execute(stmt)).scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found")

    cutoff = _period_cutoff(period)
    history = [h for h in product.history if not cutoff or h.parsed_at >= cutoff]
    history.sort(key=lambda h: h.parsed_at)

    offers: list[Product] = []
    if product.group_id:
        norm_vol = (product.volume or "").lower().replace(" ", "").strip()
        grp_stmt = select(Product).where(
            Product.group_id == product.group_id,
            Product.is_available == True,  # noqa: E712
            Product.last_price.isnot(None),
            Product.last_price > 0,
        )
        grp_products = (await db.execute(grp_stmt)).scalars().all()
        by_store: dict[str, Product] = {}
        for p in grp_products:
            if norm_vol and (p.volume or "").lower().replace(" ", "").strip() != norm_vol:
                continue
            s_key = (p.search_term or "").lower().strip()
            if s_key not in by_store or float(p.last_price) < float(by_store[s_key].last_price):
                by_store[s_key] = p
        offers = sorted(by_store.values(), key=lambda p: float(p.last_price))[:5]
    if not offers:
        offers = [product]

    base = _safe_filename(f"{product.brand or ''}_{product.title}".strip("_"))
    if format in ("csv", "json"):
        tables = [
            _Table("Shop prices", [
                ("Shop", "text"), ("Title", "text"), ("Price", "eur"), ("Previous", "eur"),
                ("Promo price", "eur"), ("Promo code", "text"), ("In stock", "bool"), ("URL", "url"),
            ], [
                [store_label(store_key(o.search_term)), o.title, _num(o.last_price), _num(o.old_price),
                 _num(o.promo_price), o.promo_code, o.is_available, o.url]
                for o in offers
            ]),
            _Table("Price history", [
                ("Date", "datetime"), ("Price", "eur"), ("In stock", "bool"), ("Change", "text"),
            ], [
                [h.parsed_at, _num(h.price), h.in_stock, CHANGE_LABEL.get(h.change_type, h.change_type)]
                for h in history
            ]),
        ]
        title = f"{product.brand or ''} {product.title}".strip()
        return _render(tables, format, base, title, f"Period: {PERIOD_LABEL[period]}")
    if format == "xlsx":
        buf = _build_product_xlsx(product, history, offers, period)
        return _stream(buf, f"{base}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    buf = _build_product_pdf(product, history, offers, period)
    return _stream(buf, f"{base}.pdf", "application/pdf")




# ── Generic tables: one source, four formats ─────────────────────────────────


@dataclass
class _Table:
    title: str
    columns: list[tuple[str, str]]   # (label, kind): text eur pct int num bool url date datetime
    rows: list[list[Any]]


def _num(v) -> Optional[float]:
    return round(float(v), 2) if v is not None else None


def _plain(v, kind: str):
    if v is None:
        return None
    if kind in ("date", "datetime") and isinstance(v, datetime):
        return v.strftime("%Y-%m-%d") if kind == "date" else v.strftime("%Y-%m-%d %H:%M")
    return v


def _tables_csv(tables: list[_Table]) -> io.BytesIO:
    out = io.StringIO()
    w = csv.writer(out)
    for i, t in enumerate(tables):
        if len(tables) > 1:
            if i:
                w.writerow([])
            w.writerow([f"# {t.title}"])
        w.writerow([c for c, _ in t.columns])
        for r in t.rows:
            w.writerow(["" if v is None else ("yes" if v is True else "no" if v is False else _plain(v, k))
                        for v, (_, k) in zip(r, t.columns)])
    # BOM so Excel opens UTF-8 (brand names with accents) correctly.
    return io.BytesIO(("\ufeff" + out.getvalue()).encode("utf-8"))


def _key(label: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in label.lower()).strip("_")


def _tables_json(tables: list[_Table], title: str, subtitle: str) -> io.BytesIO:
    doc = {
        "title": title,
        "note": subtitle,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "marketpulse1.me",
        "tables": {
            _key(t.title): [
                {_key(c): _plain(v, k) for v, (c, k) in zip(r, t.columns)} for r in t.rows
            ]
            for t in tables
        },
    }
    return io.BytesIO(json.dumps(doc, ensure_ascii=False, indent=2, default=str).encode("utf-8"))


_XL_FORMATS = {"eur": '"€"#,##0.00', "pct": '+0.0"%";-0.0"%";0"%"', "int": "#,##0", "num": "0.00"}
_XL_WIDTH = {"text": 22, "eur": 11, "pct": 10, "int": 9, "num": 9, "bool": 9, "url": 46, "date": 12, "datetime": 17}


def _tables_xlsx(tables: list[_Table], title: str, subtitle: str) -> io.BytesIO:
    import openpyxl

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    used: set[str] = set()
    for t in tables:
        name = "".join(c for c in t.title if c not in "[]:*?/\\")[:31] or "Sheet"
        while name in used:
            name = name[:28] + f"_{len(used)}"
        used.add(name)
        ws = wb.create_sheet(name)
        ws["A1"] = f"MarketPulse · {title}"
        ws["A1"].font = Font(size=15, bold=True, color=TEAL)
        ws["A2"] = f"{t.title}  ·  {subtitle}  ·  generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        ws["A2"].font = Font(size=9, color=GRAY)
        hr = 4
        for ci, (label, kind) in enumerate(t.columns, start=1):
            c = ws.cell(row=hr, column=ci, value=label)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor=TEAL)
            c.alignment = Alignment(horizontal="right" if kind in ("eur", "pct", "int", "num") else "left",
                                    vertical="center")
            ws.column_dimensions[get_column_letter(ci)].width = max(_XL_WIDTH.get(kind, 14), min(40, len(label) + 3))
        for ri, row in enumerate(t.rows, start=hr + 1):
            for ci, (v, (_, kind)) in enumerate(zip(row, t.columns), start=1):
                if kind == "bool" and v is not None:
                    v = "Yes" if v else "No"
                c = ws.cell(row=ri, column=ci, value=_plain(v, kind) if kind in ("date", "datetime") else v)
                if kind in _XL_FORMATS:
                    c.number_format = _XL_FORMATS[kind]
                if kind == "pct" and isinstance(v, (int, float)) and v:
                    c.font = Font(color=GREEN if v < 0 else RED)
                if kind == "url" and v:
                    c.hyperlink = v
                    c.font = Font(color="2563EB", underline="single")
            if (ri - hr) % 2 == 0:
                for ci in range(1, len(t.columns) + 1):
                    ws.cell(row=ri, column=ci).fill = PatternFill("solid", fgColor="F7F7F5")
        last = hr + max(1, len(t.rows))
        if t.rows:
            ws.auto_filter.ref = f"A{hr}:{get_column_letter(len(t.columns))}{last}"
        else:
            ws.cell(row=hr + 1, column=1, value="No rows.").font = Font(italic=True, color=GRAY)
        ws.freeze_panes = f"A{hr + 1}"
    buf = io.BytesIO()
    wb.save(buf)
    return buf


_PDF_WIDTH = {"text": 3.2, "eur": 1.9, "pct": 1.6, "int": 1.6, "num": 1.6, "bool": 1.4, "url": 0, "date": 2.0,
              "datetime": 2.8}


def _pdf_cell(v, kind: str) -> str:
    if v is None:
        return "—"
    if kind == "eur":
        return f"€{v:,.2f}"
    if kind == "pct":
        return f"{v:+.1f}%" if v else "0%"
    if kind == "int":
        return f"{v:,}"
    if kind == "num":
        return f"{v:.2f}"
    if kind == "bool":
        return "Yes" if v else "No"
    return str(_plain(v, kind))


def _tables_pdf(tables: list[_Table], title: str, subtitle: str) -> io.BytesIO:
    buf = io.BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(
        buf, pagesize=page, topMargin=1.2 * cm, bottomMargin=1.4 * cm,
        leftMargin=1.2 * cm, rightMargin=1.2 * cm, title=f"MarketPulse · {title}",
    )
    title_style, sub_style, h2, body, small = _pdf_styles()
    cell = ParagraphStyle("MPCell", parent=body, fontSize=7.6, leading=9.2)
    story = [
        Paragraph(f"MarketPulse · {title}", title_style),
        Paragraph(f"{subtitle}  ·  generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", sub_style),
        HRFlowable(width="100%", thickness=1.2, color=rl_colors.HexColor(f"#{ACCENT}"), spaceAfter=6),
    ]
    usable = page[0] - 2.4 * cm
    for t in tables:
        cols = [(c, k) for c, k in t.columns if k != "url"]   # links do not fit on paper
        idx = [i for i, (_, k) in enumerate(t.columns) if k != "url"]
        fixed = sum(_PDF_WIDTH.get(k, 2) for _, k in cols if k != "text") * cm
        n_text = sum(1 for _, k in cols if k == "text") or 1
        text_w = max(2.4 * cm, (usable - fixed) / n_text)
        widths = [text_w if k == "text" else _PDF_WIDTH.get(k, 2) * cm for _, k in cols]
        data = [[c for c, _ in cols]]
        for r in t.rows:
            data.append([
                Paragraph(_pdf_cell(r[i], k).replace("&", "&amp;").replace("<", "&lt;"), cell) if k == "text"
                else _pdf_cell(r[i], k)
                for i, (_, k) in zip(idx, cols)
            ])
        if len(data) == 1:
            data.append(["No rows."] + [""] * (len(cols) - 1))
        tbl = Table(data, repeatRows=1, colWidths=widths)
        cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor(f"#{TEAL}")),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F7F7F5")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for ci, (_, k) in enumerate(cols):
            if k in ("eur", "pct", "int", "num"):
                cmds.append(("ALIGN", (ci, 0), (ci, -1), "RIGHT"))
            if k == "pct":
                for ri, r in enumerate(t.rows, start=1):
                    v = r[idx[ci]]
                    if isinstance(v, (int, float)) and v:
                        cmds.append(("TEXTCOLOR", (ci, ri), (ci, ri), rl_colors.HexColor(f"#{GREEN if v < 0 else RED}")))
        tbl.setStyle(TableStyle(cmds))
        story += [Paragraph(t.title, h2), tbl, Spacer(1, 8)]
    story.append(Paragraph("marketpulse1.me · perfume prices in Latvian shops, checked nightly", small))

    def _page_num(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(rl_colors.HexColor("#6B7280"))
        canvas.drawRightString(page[0] - 1.2 * cm, 0.8 * cm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_page_num, onLaterPages=_page_num)
    return buf


_MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "csv": "text/csv; charset=utf-8",
    "json": "application/json",
}


def _render(tables: list[_Table], format: str, base: str, title: str, subtitle: str) -> StreamingResponse:
    if format == "csv":
        buf = _tables_csv(tables)
    elif format == "json":
        buf = _tables_json(tables, title, subtitle)
    elif format == "pdf":
        buf = _tables_pdf(tables, title, subtitle)
    else:
        buf = _tables_xlsx(tables, title, subtitle)
    return _stream(buf, f"{base}.{format}", _MEDIA[format])


# ── Catalogue ─────────────────────────────────────────────────────────────────


def _filters_desc(**f) -> str:
    parts = []
    for k, v in f.items():
        if v in (None, [], False, ""):
            continue
        parts.append(f"{k.replace('_', ' ')}: {', '.join(map(str, v)) if isinstance(v, list) else v}")
    return "  ·  ".join(parts) or "all perfumes"


@router.get("/catalog")
async def export_catalog(
    format: str = Query("xlsx", pattern=_FORMATS),
    view: str = Query("cards", pattern="^(cards|listings)$"),
    keys: List[str] = Query(None, description="Selected perfume cards (view=cards)"),
    ids: List[int] = Query(None, description="Selected shop listings (view=listings)"),
    search: Optional[str] = None,
    brands: List[str] = Query(None),
    stores: List[str] = Query(None),
    volumes: List[str] = Query(None),
    types: List[str] = Query(None),
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    in_stock: Optional[bool] = None,
    promo: Optional[bool] = None,
    multi_shop: Optional[bool] = None,
    dropped: Optional[bool] = None,
    sort: Optional[str] = None,
    limit: int = Query(2000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Catalogue export: the selected rows, or everything matching the filters.

    view=cards writes one row per perfume and size with a price column per
    shop; view=listings writes one row per shop listing, like the table view.
    """
    filters = dict(search=search, brands=brands, stores=stores, volumes=volumes, types=types,
                   price_min=price_min, price_max=price_max, in_stock=in_stock, promo=promo)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    desc = f"{len(keys or ids or [])} selected" if (keys or ids) else _filters_desc(
        **filters, multi_shop=multi_shop, dropped=dropped)

    if view == "cards":
        if keys:
            cards = await cards_for_keys(db, keys[:limit])
        else:
            page = await query_cards(db, **filters, multi_shop=multi_shop, dropped=dropped,
                                     sort=sort if sort in ("popular", "shops", "drop", "low", "high", "gap", "brand", "new") else "popular",
                                     skip=0, limit=limit)
            cards = page.items
        shops = [k for k in STORE_LABELS if any(o.store == k for c in cards for o in c.offers)]
        cols = [("Brand", "text"), ("Perfume", "text"), ("Type", "text"), ("Volume", "text"),
                ("Cheapest shop", "text"), ("Lowest", "eur"), ("Highest", "eur"), ("Shops", "int"),
                ("30-day change", "pct")] + [(f"{store_label(k)}", "eur") for k in shops]
        rows = []
        for c in cards:
            by_shop = {}
            for o in c.offers:
                if o.in_stock and (o.store not in by_shop or o.price < by_shop[o.store]):
                    by_shop[o.store] = o.price
            rows.append([c.brand, c.name, c.concentration, c.volume, store_label(c.cheapest_store),
                         c.min_price, c.max_price, c.shops, c.change_30d] + [by_shop.get(k) for k in shops])
        table = _Table("Perfumes", cols, rows)
    else:
        page = await query_listings(db, ids=ids, **filters, multi_shop=multi_shop, dropped=dropped,
                                    sort=sort if sort in ("popular", "brand", "name", "price", "change", "shop") else "popular",
                                    skip=0, limit=limit)
        table = _Table("Shop listings", [
            ("Brand", "text"), ("Perfume", "text"), ("Type", "text"), ("Volume", "text"), ("Shop", "text"),
            ("Price", "eur"), ("Previous", "eur"), ("Promo price", "eur"), ("Promo code", "text"),
            ("30-day change", "pct"), ("In stock", "bool"), ("Checked", "datetime"), ("URL", "url"),
        ], [
            [r.brand, r.name, r.concentration, r.volume, r.store_name, r.price, r.old_price, r.promo_price,
             r.promo_code, r.change_30d, r.in_stock, r.checked_at, r.url]
            for r in page.items
        ])
    return _render([table], format, f"marketpulse_catalogue_{stamp}", "Catalogue", desc)


# ── Analytics ────────────────────────────────────────────────────────────────

_SECTIONS = ("overview", "shops", "drops", "rises", "gaps", "brands", "bands", "activity", "index")


@router.get("/analytics")
async def export_analytics(
    format: str = Query("xlsx", pattern=_FORMATS),
    days: int = Query(7, ge=1, le=90, description="Window for the biggest moves"),
    section: Optional[str] = Query(None, description="Only this section (CSV of one table)"),
    db: AsyncSession = Depends(get_db),
):
    """Everything on the analytics page, one table per section."""
    if section and section not in _SECTIONS:
        raise HTTPException(422, f"section must be one of {', '.join(_SECTIONS)}")
    want = (lambda name: section is None or section == name)
    snap = await market.snapshot(db)
    tables: list[_Table] = []
    if want("overview"):
        tables.append(_Table("Market overview", [("Metric", "text"), ("Value", "text")], [
            ["Latest scan", snap.as_of.strftime("%Y-%m-%d %H:%M UTC") if snap.as_of else "—"],
            ["Listings tracked", f"{snap.total_products:,}"],
            ["In stock now", f"{snap.current_products:,}"],
            ["Bottles in 2+ shops", f"{snap.comparable:,}"],
            ["Price changes, 7 days", f"{snap.changes_7d:,}"],
            ["Price changes, 30 days", f"{snap.changes_30d:,}"],
            ["Median gap, dearest vs cheapest shop", f"{snap.spread_median:.1f}%"],
            ["Mean gap", f"{snap.spread_mean:.1f}%"],
            ["Price records since", snap.history_since.strftime("%Y-%m-%d") if snap.history_since else "—"],
        ]))
    if want("shops"):
        tables.append(_Table("Shops", [
            ("Shop", "text"), ("Listings", "int"), ("In stock", "int"), ("Changes 7d", "int"),
            ("Changes 30d", "int"), ("Cheapest for", "int"), ("Cheapest share", "pct"), ("Promo listings", "int"),
        ], [[s.store_name, s.products, s.current, s.changes_7d, s.changes_30d, s.cheapest_count,
             s.cheapest_share, s.promo_listings] for s in snap.shops]))
    move_cols = [("Brand", "text"), ("Perfume", "text"), ("Type", "text"), ("Volume", "text"), ("Shop", "text"),
                 ("Before", "eur"), ("Now", "eur"), ("Change", "pct")]
    if want("drops"):
        rows = await market.moves(db, days=days, direction="down", limit=30)
        tables.append(_Table(f"Biggest drops, {days} days", move_cols, [
            [m.brand, m.name, m.concentration, m.volume, m.store_name, m.old_price, m.new_price, m.change_percent]
            for m in rows]))
    if want("rises"):
        rows = await market.moves(db, days=days, direction="up", limit=30)
        tables.append(_Table(f"Biggest rises, {days} days", move_cols, [
            [m.brand, m.name, m.concentration, m.volume, m.store_name, m.old_price, m.new_price, m.change_percent]
            for m in rows]))
    if want("gaps"):
        cards = await cards_for_keys(db, await market.top_gap_keys(db, limit=50))
        rows = []
        for c in cards:
            live = [o for o in c.offers if o.in_stock] or c.offers
            dear = max(live, key=lambda o: o.price)
            rows.append([c.brand, c.name, c.concentration, c.volume, store_label(c.cheapest_store), c.min_price,
                         dear.store_name, dear.price, round((dear.price - c.min_price) / c.min_price * 100, 1)])
        tables.append(_Table("Widest gaps between shops", [
            ("Brand", "text"), ("Perfume", "text"), ("Type", "text"), ("Volume", "text"),
            ("Cheapest shop", "text"), ("Lowest", "eur"), ("Dearest shop", "text"), ("Highest", "eur"), ("Gap", "pct"),
        ], rows))
    if want("brands"):
        m = await market.brand_shop(db, top=20)
        cell = {(c.brand, c.store): c for c in m.cells}
        tables.append(_Table("Brand × shop premium over the cheapest", [("Brand", "text")] + [
            (store_label(s), "pct") for s in m.stores
        ], [[b] + [cell[(b, s)].premium if (b, s) in cell else None for s in m.stores] for b in m.brands]))
    if want("bands"):
        bands = await market.price_bands(db)
        labels = list(dict.fromkeys(b.label for b in sorted(bands, key=lambda b: b.band)))
        stores = list(dict.fromkeys(b.store for b in bands))
        cnt = {(b.store, b.label): b.count for b in bands}
        tables.append(_Table("In-stock listings by price band", [("Shop", "text")] + [(lb, "int") for lb in labels],
                             [[store_label(s)] + [cnt.get((s, lb), 0) for lb in labels] for s in stores]))
    if want("activity"):
        act = await market.activity(db, 30)
        tables.append(_Table("Price changes per day, 30 days", [
            ("Date", "text"), ("Shop", "text"), ("Rises", "int"), ("Drops", "int"),
        ], [[a.date, store_label(a.store), a.up, a.down] for a in act]))
    if want("index"):
        idx = await market.price_index(db, 30)
        shops = list(idx.shops)
        tables.append(_Table("Price index, 100 = 30 days ago", [("Date", "text")] + [
            (store_label(s), "num") for s in shops
        ], [[d] + [idx.shops[s][i] for s in shops] for i, d in enumerate(idx.days)]))
    stamp = datetime.utcnow().strftime("%Y%m%d")
    return _render(tables, format, f"marketpulse_analytics_{stamp}", "Market analytics",
                   f"Moves over {days} days")
