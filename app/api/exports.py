"""Export endpoints — server-side Excel and PDF generation.

CSV and JSON are generated client-side (see frontend/src/lib/exporters.ts) for
zero-latency download. Excel and PDF need real layout/styling/charts so they
live here.

Streaming responses with proper Content-Type and Content-Disposition so
browsers trigger a download dialog.

Period parameter (1w/1m/3m/6m/1y/all) filters PriceHistory rows before serialization.
"""
from __future__ import annotations

import io
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional

# matplotlib MUST use Agg backend before pyplot import — Docker has no display.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.domain.models import Product

router = APIRouter(prefix="/exports", tags=["exports"])


# ── Helpers ───────────────────────────────────────────────────────────────────

PERIOD_DAYS = {"1w": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365, "all": None}


def _period_cutoff(period: str) -> Optional[datetime]:
    days = PERIOD_DAYS.get(period)
    if days is None:
        return None
    return datetime.utcnow() - timedelta(days=days)


def _safe_filename(s: str, max_len: int = 60) -> str:
    """Sanitize for Content-Disposition filename header."""
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


def _render_history_png(
    history_rows: list[tuple[datetime, float]],
    title: str,
    width_px: int = 900,
    height_px: int = 360,
) -> io.BytesIO:
    """Render an Area-style line chart of price history to a PNG BytesIO."""
    fig, ax = plt.subplots(figsize=(width_px / 100, height_px / 100), dpi=100)
    if history_rows:
        xs = [r[0] for r in history_rows]
        ys = [r[1] for r in history_rows]
        ax.plot(xs, ys, color="#3CB6B0", linewidth=2)
        ax.fill_between(xs, ys, alpha=0.15, color="#3CB6B0")
        ax.set_ylim(min(ys) * 0.95, max(ys) * 1.05)
    else:
        ax.text(0.5, 0.5, "No price history in this period",
                ha="center", va="center", transform=ax.transAxes,
                color="#888", fontsize=11)
        ax.set_xticks([])
        ax.set_yticks([])

    ax.set_title(title, fontsize=11, loc="left", color="#222")
    ax.tick_params(axis="both", labelsize=8, colors="#555")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.grid(True, alpha=0.18, linewidth=0.5)
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Excel builders ────────────────────────────────────────────────────────────

def _build_product_xlsx(product: Product, history_rows: list, offer_rows: list) -> io.BytesIO:
    """3-sheet workbook: Summary / Price History / Offers."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # Summary
        summary_df = pd.DataFrame([
            ("Brand", product.brand or "—"),
            ("Title", product.title),
            ("Volume", product.volume or "—"),
            ("Concentration", product.concentration or "—"),
            ("Store", (product.search_term or "—").capitalize()),
            ("Current price (€)", float(product.last_price) if product.last_price else 0),
            ("Previous price (€)", float(product.old_price) if product.old_price else 0),
            ("In stock", "Yes" if product.is_available else "No"),
            ("URL", product.url),
            ("Exported at", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")),
        ], columns=["Field", "Value"])
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        # Price History
        hist_df = pd.DataFrame([
            {
                "Date": h.parsed_at.strftime("%Y-%m-%d %H:%M"),
                "Price (€)": float(h.price),
                "In stock": "Yes" if h.in_stock else "No",
                "Change": h.change_type,
            }
            for h in history_rows
        ])
        if hist_df.empty:
            hist_df = pd.DataFrame([{"Date": "—", "Price (€)": 0, "In stock": "—", "Change": "no data"}])
        hist_df.to_excel(writer, sheet_name="Price History", index=False)

        # Offers
        offers_df = pd.DataFrame([
            {
                "Store": (p.search_term or "—").capitalize(),
                "Price (€)": float(p.last_price) if p.last_price else 0,
                "Previous (€)": float(p.old_price) if p.old_price else 0,
                "URL": p.url,
            }
            for p in offer_rows
        ])
        if offers_df.empty:
            offers_df = pd.DataFrame([{"Store": "—", "Price (€)": 0, "Previous (€)": 0, "URL": "—"}])
        offers_df.to_excel(writer, sheet_name="Offers", index=False)

        # Styling
        for sheet_name in ("Summary", "Price History", "Offers"):
            ws = writer.book[sheet_name]
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1F4E5F")
                cell.alignment = Alignment(horizontal="left")
            for col_idx, col in enumerate(ws.columns, start=1):
                max_len = max((len(str(c.value)) if c.value is not None else 0) for c in col)
                ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 2, 10), 60)
            ws.freeze_panes = "A2"

    return buf


def _build_catalog_xlsx(catalog_rows: list[Product]) -> io.BytesIO:
    """Single sheet of catalog data."""
    buf = io.BytesIO()
    rows = []
    for p in catalog_rows:
        rows.append({
            "Brand": p.brand or "—",
            "Title": p.title,
            "Volume": p.volume or "—",
            "Concentration": p.concentration or "—",
            "Store": (p.search_term or "—").capitalize(),
            "Current (€)": float(p.last_price) if p.last_price else 0,
            "Previous (€)": float(p.old_price) if p.old_price else 0,
            "In stock": "Yes" if p.is_available else "No",
            "Last seen": p.last_seen.strftime("%Y-%m-%d") if p.last_seen else "—",
            "URL": p.url,
        })
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
        "Brand", "Title", "Volume", "Concentration", "Store",
        "Current (€)", "Previous (€)", "In stock", "Last seen", "URL"
    ])
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Catalog", index=False)
        ws = writer.book["Catalog"]
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E5F")
        for col_idx, col in enumerate(ws.columns, start=1):
            max_len = max((len(str(c.value)) if c.value is not None else 0) for c in col)
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 2, 10), 50)
        ws.freeze_panes = "A2"
    return buf


# ── PDF builders ──────────────────────────────────────────────────────────────

def _pdf_styles():
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MPTitle", parent=styles["Heading1"],
        fontName="Helvetica-Bold", fontSize=16, leading=20,
        textColor=colors.HexColor("#1F4E5F"), spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "MPSub", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#777"),
        spaceAfter=12,
    )
    h2 = ParagraphStyle(
        "MPH2", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=11,
        textColor=colors.HexColor("#222"), spaceBefore=10, spaceAfter=6,
    )
    body = ParagraphStyle(
        "MPBody", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#333"),
    )
    small = ParagraphStyle(
        "MPSmall", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#888"),
    )
    return title_style, sub_style, h2, body, small


def _build_product_pdf(product: Product, history_rows: list, offer_rows: list, period: str) -> io.BytesIO:
    """One-page A4 product report with embedded price chart."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        title=f"MarketPulse — {product.title}",
    )
    title_style, sub_style, h2, body, small = _pdf_styles()
    story = []

    # Header
    story.append(Paragraph("MarketPulse · Price Report", title_style))
    story.append(Paragraph(
        f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · period: {period}",
        sub_style,
    ))

    # Product summary block
    brand = product.brand or "—"
    title = product.title
    volume = product.volume or "—"
    conc = product.concentration or "—"
    current = float(product.last_price) if product.last_price else 0.0
    prev = float(product.old_price) if product.old_price else current
    delta_pct = ((current - prev) / prev * 100) if prev > 0 and prev != current else 0.0
    delta_str = f"{delta_pct:+.1f}%" if delta_pct != 0 else "flat"

    summary_tbl = Table(
        [
            [Paragraph(f"<b>{brand}</b>", body), Paragraph(f"<font size=14><b>{title}</b></font>", body)],
            ["", Paragraph(f"{volume} · {conc}", small)],
            ["", Paragraph(f"<font size=13><b>{current:.2f} €</b></font>  "
                           f"<font color='#888'>was {prev:.2f} €  ·  {delta_str}</font>", body)],
        ],
        colWidths=[3.5 * cm, 13.5 * cm],
    )
    summary_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(summary_tbl)
    story.append(Spacer(1, 8))

    # Chart
    story.append(Paragraph(f"Price history ({period})", h2))
    chart_data = [(h.parsed_at, float(h.price)) for h in history_rows]
    png = _render_history_png(chart_data, title="", width_px=900, height_px=320)
    story.append(RLImage(png, width=17 * cm, height=6 * cm))
    story.append(Spacer(1, 8))

    # Offers
    story.append(Paragraph("Offers by store", h2))
    offer_data = [["Store", "Price (€)", "Previous (€)", "Change"]]
    for p in offer_rows[:8]:
        op = float(p.last_price) if p.last_price else 0
        oo = float(p.old_price) if p.old_price else op
        d = ((op - oo) / oo * 100) if oo > 0 and oo != op else 0.0
        offer_data.append([
            (p.search_term or "—").capitalize(),
            f"{op:.2f}",
            f"{oo:.2f}",
            f"{d:+.1f}%" if d != 0 else "flat",
        ])
    if len(offer_data) == 1:
        offer_data.append(["—", "—", "—", "—"])
    offers_tbl = Table(offer_data, colWidths=[5 * cm, 4 * cm, 4 * cm, 4 * cm])
    offers_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E5F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F8")]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#1F4E5F")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(offers_tbl)
    story.append(Spacer(1, 12))

    # Footer
    story.append(Paragraph(
        "marketpulse.lv · automated perfume price intelligence",
        small,
    ))

    doc.build(story)
    return buf


def _build_catalog_pdf(catalog_rows: list[Product], filters_desc: str) -> io.BytesIO:
    """Landscape multi-page table report."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        topMargin=1.2 * cm, bottomMargin=1.2 * cm,
        leftMargin=1.2 * cm, rightMargin=1.2 * cm,
        title="MarketPulse Catalog Export",
    )
    title_style, sub_style, h2, body, small = _pdf_styles()
    story = []
    story.append(Paragraph("MarketPulse · Catalog Export", title_style))
    story.append(Paragraph(
        f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · "
        f"{len(catalog_rows)} rows · {filters_desc}",
        sub_style,
    ))

    header = ["Brand", "Title", "Volume", "Type", "Store", "Price (€)", "Prev (€)", "Stock"]
    data = [header]
    for p in catalog_rows:
        cur = float(p.last_price) if p.last_price else 0
        prev = float(p.old_price) if p.old_price else cur
        data.append([
            (p.brand or "—")[:18],
            (p.title or "—")[:50],
            p.volume or "—",
            p.concentration or "—",
            (p.search_term or "—").capitalize()[:10],
            f"{cur:.2f}",
            f"{prev:.2f}",
            "Y" if p.is_available else "N",
        ])
    if len(data) == 1:
        data.append(["—"] * len(header))

    tbl = Table(data, repeatRows=1, colWidths=[
        3 * cm, 7 * cm, 1.8 * cm, 1.5 * cm, 2 * cm, 2 * cm, 2 * cm, 1.2 * cm
    ])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E5F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (5, 1), (6, -1), "RIGHT"),
        ("ALIGN", (7, 1), (7, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F8")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 10))
    story.append(Paragraph("marketpulse.lv · automated perfume price intelligence", small))

    doc.build(story)
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

    # Period-filtered, chronologically sorted history
    cutoff = _period_cutoff(period)
    history = [h for h in product.history if not cutoff or h.parsed_at >= cutoff]
    history.sort(key=lambda h: h.parsed_at)

    # Offers — same group, in-stock, priced, same normalized volume
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
        # dedupe by normalized store, keeping cheapest per store
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
        buf = _build_product_xlsx(product, history, offers)
        return _stream(buf, f"{base}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    # pdf
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
    filters_desc = "; ".join(filt_parts) if filt_parts else "no filters"

    base = f"marketpulse_catalog_{datetime.utcnow().strftime('%Y%m%d')}"
    if format == "xlsx":
        buf = _build_catalog_xlsx(rows)
        return _stream(buf, f"{base}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    buf = _build_catalog_pdf(rows, filters_desc)
    return _stream(buf, f"{base}.pdf", "application/pdf")
