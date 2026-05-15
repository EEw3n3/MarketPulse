"""Export endpoints — server-side Excel and PDF generation.

CSV and JSON are generated client-side (see frontend/src/lib/exporters.ts) for
zero-latency download. Excel and PDF need real layout/styling/charts so they
live here.

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
from typing import List, Optional

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
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.domain.models import Product

router = APIRouter(prefix="/exports", tags=["exports"])


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
TEAL = "1F4E5F"
TEAL_DARK = "143841"
GREEN = "1F8E5F"
RED = "B91C1C"
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


def _store_filter_clause(stores: List[str]):
    return or_(*(func.lower(Product.search_term).like(f"%{s.lower()}%") for s in stores))


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
    """Draw a thin black border around the entire cell range AND each cell inside.
    `cell_range` is like 'A1:F14'."""
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


def _build_product_xlsx(product: Product, history_rows: list, offer_rows: list, period: str) -> io.BytesIO:
    """3-sheet workbook with classic spreadsheet aesthetic: gridlines visible,
    black borders around tables, no large teal banners (just bold headings)."""
    import openpyxl
    wb = openpyxl.Workbook()

    current = float(product.last_price) if product.last_price else 0.0
    previous = float(product.old_price) if product.old_price else current
    pct = _delta_percent(current, previous)

    # ── Summary ──────────────────────────────────────────────────────────────
    s = wb.active
    s.title = "Summary"
    # gridlines stay visible (Excel default)

    # Title row
    s["A1"] = "MarketPulse — Price Report"
    s["A1"].font = Font(name="Calibri", size=16, bold=True, color="111827")
    s["A2"] = f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  ·  Period: {PERIOD_LABEL.get(period, period)}"
    s["A2"].font = Font(name="Calibri", size=10, color=GRAY)

    # Hero block
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

    # Price hero — current big and colored, previous strike, delta as colored text (no fill)
    s["A8"] = f"{current:.2f} €"
    s["A8"].font = Font(name="Calibri", size=24, bold=True,
                        color=(GREEN if (pct or 0) < 0 else (RED if (pct or 0) > 0 else "111827")))
    s.row_dimensions[8].height = 32

    if pct is not None:
        s["B8"] = f"was {previous:.2f} €"
        s["B8"].font = Font(name="Calibri", size=11, italic=True, strike=True, color=GRAY)
        s["B8"].alignment = Alignment(vertical="center")
        s["C8"] = f"{pct:+.1f}%"
        s["C8"].font = Font(name="Calibri", size=12, bold=True,
                            color=(GREEN if pct < 0 else RED))
        s["C8"].alignment = Alignment(horizontal="left", vertical="center")

    # Embedded image
    img_bytes = _fetch_image_bytes(product.image_url)
    img_buf = io.BytesIO(img_bytes) if img_bytes else _make_placeholder_png(product.brand)
    try:
        xl_img = XLImage(img_buf)
        xl_img.width = 150
        xl_img.height = 150
        s.add_image(xl_img, "E4")
    except Exception:
        pass

    # Data table (k/v pairs) with black borders. URL merged across B:F so it fits.
    rows_data = [
        ("In stock", "Yes" if product.is_available else "No"),
        ("Store", (product.search_term or "—").capitalize()),
        ("URL", product.url or "—"),
        ("Exported at", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")),
    ]
    start_row = 11
    for i, (k, v) in enumerate(rows_data, start=start_row):
        s.cell(row=i, column=1, value=k).font = Font(name="Calibri", size=10, bold=True, color="111827")
        s.cell(row=i, column=2, value=v).font = Font(name="Calibri", size=10, color="111827")
        s.cell(row=i, column=2).alignment = Alignment(horizontal="left", vertical="center")

    # URL is on row start_row+2 — merge B:F so it stays within the table frame
    url_row = start_row + 2
    s.merge_cells(start_row=url_row, start_column=2, end_row=url_row, end_column=6)
    if product.url:
        s.cell(row=url_row, column=2).hyperlink = product.url
        s.cell(row=url_row, column=2).font = Font(name="Calibri", size=10, color="2563EB", underline="single")

    # Frame the entire data table in thin black border
    end_row = start_row + len(rows_data) - 1
    _apply_box_border(s, f"A{start_row}:F{end_row}", color="111827")

    s.column_dimensions["A"].width = 16
    s.column_dimensions["B"].width = 30
    s.column_dimensions["C"].width = 14
    s.column_dimensions["D"].width = 14
    s.column_dimensions["E"].width = 14
    s.column_dimensions["F"].width = 24

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

        # Embedded LineChart
        if len(history_rows) >= 2:
            chart = LineChart()
            chart.title = "Price trend"
            chart.y_axis.title = "Price (€)"
            chart.x_axis.title = "Date"
            chart.height = 10
            chart.width = 22
            data_ref = Reference(h, min_col=2, min_row=header_row, max_col=2, max_row=last_row)
            cats_ref = Reference(h, min_col=1, min_row=4, max_row=last_row)
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats_ref)
            h.add_chart(chart, "F3")

    # Frame the table in thin black border
    _apply_box_border(h, f"A{header_row}:D{last_row}", color="111827")

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
            ch_cell.alignment = Alignment(horizontal="left")
            if opct is not None:
                ch_cell.font = Font(bold=True, color=(GREEN if opct < 0 else RED))
            url_cell = o.cell(row=ri, column=5, value=p.url or "—")
            if p.url:
                url_cell.hyperlink = p.url
                url_cell.font = Font(color="2563EB", underline="single")
        offer_last_row = 3 + len(offer_rows)

        if len(offer_rows) == 1:
            note_row = offer_last_row + 2
            o.cell(row=note_row, column=1, value="Only one store currently carries this product at this volume.").font = Font(italic=True, color=GRAY)

    # Frame
    _apply_box_border(o, f"A{offer_header_row}:E{offer_last_row}", color="111827")

    o.column_dimensions["A"].width = 22
    o.column_dimensions["B"].width = 14
    o.column_dimensions["C"].width = 14
    o.column_dimensions["D"].width = 14
    o.column_dimensions["E"].width = 60

    buf = io.BytesIO()
    wb.save(buf)
    return buf


# ── Excel — catalog ──────────────────────────────────────────────────────────


def _build_catalog_xlsx(catalog_rows: list[Product], filters_desc: str) -> io.BytesIO:
    """Single sheet with title row + filter description + bordered table."""
    import openpyxl
    wb = openpyxl.Workbook()
    s = wb.active
    s.title = "Catalog"

    s["A1"] = "MarketPulse — Catalog Export"
    s["A1"].font = Font(size=16, bold=True, color="111827")
    s["A2"] = (f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  ·  "
               f"{len(catalog_rows)} rows  ·  Filters: {filters_desc}")
    s["A2"].font = Font(size=10, color=GRAY)

    header_row = 4
    headers = ["Brand", "Title", "Volume", "Type", "Store", "Current (€)", "Previous (€)", "Change %", "In stock", "URL"]
    for ci, label in enumerate(headers, start=1):
        c = s.cell(row=header_row, column=ci, value=label)
        c.font = Font(bold=True, color="111827")
        c.alignment = Alignment(horizontal="left")

    if not catalog_rows:
        s.cell(row=5, column=1, value="No products match these filters.").font = Font(italic=True, color=GRAY)
        last_row = 5
    else:
        for ri, p in enumerate(catalog_rows, start=5):
            cur = float(p.last_price) if p.last_price else 0
            prev = float(p.old_price) if p.old_price else cur
            pct = _delta_percent(cur, prev)
            s.cell(row=ri, column=1, value=p.brand or "—")
            s.cell(row=ri, column=2, value=p.title or "—")
            s.cell(row=ri, column=3, value=p.volume or "—")
            s.cell(row=ri, column=4, value=p.concentration or "—")
            s.cell(row=ri, column=5, value=(p.search_term or "—").capitalize())
            s.cell(row=ri, column=6, value=cur).number_format = "0.00"
            s.cell(row=ri, column=7, value=prev).number_format = "0.00"
            ch = s.cell(row=ri, column=8, value=f"{pct:+.1f}%" if pct is not None else "flat")
            if pct is not None:
                ch.font = Font(bold=True, color=(GREEN if pct < 0 else RED))
            s.cell(row=ri, column=9, value="Yes" if p.is_available else "No")
            url_cell = s.cell(row=ri, column=10, value=p.url or "—")
            if p.url:
                url_cell.hyperlink = p.url
                url_cell.font = Font(color="2563EB", underline="single")
        last_row = 4 + len(catalog_rows)

    _apply_box_border(s, f"A{header_row}:J{last_row}", color="111827")

    widths = [18, 40, 10, 10, 14, 12, 12, 12, 10, 50]
    for i, w in enumerate(widths, start=1):
        s.column_dimensions[get_column_letter(i)].width = w

    s.freeze_panes = "A5"

    buf = io.BytesIO()
    wb.save(buf)
    return buf


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
        "marketpulse.lv  ·  automated perfume price intelligence",
        small,
    ))

    doc.build(story)
    return buf


# ── PDF — catalog ────────────────────────────────────────────────────────────


def _build_catalog_pdf(catalog_rows: list[Product], filters_desc: str) -> io.BytesIO:
    """Landscape multi-page table report with branded header + filter chips + page numbers."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        topMargin=1.2 * cm, bottomMargin=1.4 * cm,
        leftMargin=1.2 * cm, rightMargin=1.2 * cm,
        title="MarketPulse Catalog Export",
    )
    title_style, sub_style, h2, body, small = _pdf_styles()
    story = []

    story.append(Paragraph("MarketPulse · Catalog Export", title_style))
    story.append(Paragraph(
        f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  ·  "
        f"<b>{len(catalog_rows)} rows</b>  ·  {filters_desc}",
        sub_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1.2, color=rl_colors.HexColor(f"#{TEAL}"), spaceAfter=6))

    header = ["Brand", "Title", "Volume", "Type", "Store", "Price (€)", "Prev (€)", "Δ%", "Stock"]
    data = [header]
    for p in catalog_rows:
        cur = float(p.last_price) if p.last_price else 0
        prev = float(p.old_price) if p.old_price else cur
        pct = _delta_percent(cur, prev)
        data.append([
            (p.brand or "—")[:20],
            (p.title or "—")[:55],
            p.volume or "—",
            p.concentration or "—",
            (p.search_term or "—").capitalize()[:12],
            f"{cur:.2f}",
            f"{prev:.2f}",
            f"{pct:+.1f}" if pct is not None else "—",
            "Y" if p.is_available else "N",
        ])
    if len(data) == 1:
        data.append(["—"] * len(header))

    tbl = Table(data, repeatRows=1, colWidths=[
        2.8 * cm, 7.5 * cm, 1.7 * cm, 1.5 * cm, 2.2 * cm, 1.9 * cm, 1.9 * cm, 1.4 * cm, 1.1 * cm,
    ])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor(f"#{TEAL_DARK}")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.8),
        ("ALIGN", (5, 1), (7, -1), "RIGHT"),
        ("ALIGN", (8, 1), (8, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor(f"#{LIGHT}")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, rl_colors.HexColor(f"#{TEAL}")),
    ]
    # Color the Δ% cells
    for ri in range(1, len(data)):
        cell = data[ri][7]
        if cell == "—":
            continue
        try:
            val = float(cell)
        except (TypeError, ValueError):
            continue
        if val < 0:
            style_cmds.append(("TEXTCOLOR", (7, ri), (7, ri), rl_colors.HexColor(f"#{GREEN}")))
        elif val > 0:
            style_cmds.append(("TEXTCOLOR", (7, ri), (7, ri), rl_colors.HexColor(f"#{RED}")))
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)
    story.append(Spacer(1, 8))
    story.append(Paragraph("marketpulse.lv · automated perfume price intelligence", small))

    def _draw_page_num(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(rl_colors.HexColor("#6B7280"))
        page = canvas.getPageNumber()
        canvas.drawRightString(landscape(A4)[0] - 1.2 * cm, 0.8 * cm, f"Page {page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_page_num, onLaterPages=_draw_page_num)
    return buf


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/products/{product_id}")
async def export_product(
    product_id: int,
    format: str = Query("xlsx", pattern="^(xlsx|pdf)$"),
    period: str = Query("3m", pattern="^(1w|1m|3m|6m|1y|all)$"),
    db: AsyncSession = Depends(get_db),
):
    """Export a single product (xlsx | pdf). CSV/JSON live on the frontend."""
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
    if format == "xlsx":
        buf = _build_product_xlsx(product, history, offers, period)
        return _stream(buf, f"{base}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    buf = _build_product_pdf(product, history, offers, period)
    return _stream(buf, f"{base}.pdf", "application/pdf")


@router.get("/catalog")
async def export_catalog(
    format: str = Query("xlsx", pattern="^(xlsx|pdf)$"),
    search: Optional[str] = None,
    brands: List[str] = Query(None),
    stores: List[str] = Query(None),
    limit: int = Query(2000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Export filtered catalog. Same filter semantics as /products/catalog."""
    stmt = select(Product)
    if search:
        stmt = stmt.where(or_(Product.title.ilike(f"%{search}%"), Product.brand.ilike(f"%{search}%")))
    if brands:
        stmt = stmt.where(Product.brand.in_(brands))
    if stores:
        stmt = stmt.where(_store_filter_clause(stores))
    stmt = stmt.order_by(Product.brand.asc(), Product.title.asc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    filt_parts = []
    if search: filt_parts.append(f"search='{search}'")
    if brands: filt_parts.append(f"brands={','.join(brands)}")
    if stores: filt_parts.append(f"stores={','.join(stores)}")
    filters_desc = "  ·  ".join(filt_parts) if filt_parts else "no filters"

    base = f"marketpulse_catalog_{datetime.utcnow().strftime('%Y%m%d')}"
    if format == "xlsx":
        buf = _build_catalog_xlsx(rows, filters_desc)
        return _stream(buf, f"{base}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    buf = _build_catalog_pdf(rows, filters_desc)
    return _stream(buf, f"{base}.pdf", "application/pdf")
