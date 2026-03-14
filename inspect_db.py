import asyncio
import sys
import os
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Rich UI imports
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

# Ensure the root project directory is in PYTHONPATH
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from sqlalchemy.orm import selectinload
from app.services.analyzer import price_analyzer
from app.core.config import settings
from app.domain.models import Product, ProductGroup

engine = create_async_engine(settings.DATABASE_URL, echo=False)
console = Console()

async def inspect():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Load Products
        stmt = select(Product).order_by(Product.search_term, Product.id.asc())
        products = (await session.execute(stmt)).scalars().all()
        
        # Load Groups (Chains) with their products for analysis
        groups_stmt = select(ProductGroup).options(selectinload(ProductGroup.products)).order_by(ProductGroup.created_at.desc())
        groups_res = await session.execute(groups_stmt)
        groups = groups_res.scalars().all()

        # Header Panel
        console.print(Panel(
            f"[bold cyan]MARKET PULSE[/bold cyan] [white]Database Intelligence[/white]\n"
            f"[dim]Total Products:[/dim] [bold green]{len(products)}[/bold green] | "
            f"[dim]Total Chains (Groups):[/dim] [bold yellow]{len(groups)}[/bold yellow]",
            expand=False,
            border_style="blue",
            box=box.ROUNDED
        ))
        
        if not products:
            console.print("[yellow]No products found.[/yellow]")
            return

        # 1. CHAIN REPORT (The "Connections")
        if groups:
            from rich.tree import Tree
            console.print("\n[bold cyan]🔗 PRICE COMPARISON CHAINS[/bold cyan]")
            
            all_analyses = []
            for g in groups:
                analysis = await price_analyzer.analyze_group(session, g.id)
                if analysis:
                    all_analyses.append(analysis)
            
            # Sort by score (most competition first)
            sorted_analyses = sorted(all_analyses, key=lambda a: a.get("score", 0), reverse=True)[:20]

            for analysis in sorted_analyses:
                # Re-fetch products for this group
                group_products_stmt = select(Product).where(Product.group_id == analysis['group_id']).order_by(Product.volume, Product.last_price)
                group_products = (await session.execute(group_products_stmt)).scalars().all()

                # Group by volume
                from collections import defaultdict
                vol_map = defaultdict(list)
                for gp in group_products:
                    vol_map[gp.volume or "Unknown"].append(gp)

                # Create Root Tree for the Group
                root = Tree(f"[bold yellow]📦 {analysis['name']}[/bold yellow] [dim]({analysis['category']})[/dim]")
                
                for vol, prods in sorted(vol_map.items()):
                    # Sub-node for the Volume
                    vol_node = root.add(f"[bold green]🔗 {vol}[/bold green]")
                    
                    for p in prods:
                        price_str = f"[bold white]{p.last_price:.2f} €[/bold white]" if p.last_price else "[dim]N/A[/dim]"
                        store_name = (p.search_term or "Unknown").capitalize()
                        last_seen = f"[dim]({p.last_seen.strftime('%H:%M')})[/dim]" if p.last_seen else ""
                        
                        vol_node.add(f"[blue]{store_name:20}[/blue] │ {price_str} {last_seen}")
                
                console.print(root)
                console.print(f"[dim]{'—' * 60}[/dim]")

        # 2. RAW DATA TABLE
        console.print("\n[bold]📦 RAW PRODUCT DATA[/bold]")
        table = Table(
            box=box.DOUBLE_EDGE,
            header_style="bold magenta",
            border_style="bright_black",
            row_styles=["none", "dim"]
        )
        
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Store", style="blue")
        table.add_column("Brand", style="yellow")
        table.add_column("Title", style="white", ratio=3)
        table.add_column("Volume", justify="center", style="green")
        table.add_column("Price", justify="right", style="bold green")

        for p in products: # Show ALL products in raw data
            store = (p.search_term or "N/A").capitalize()
            brand = (p.brand or "Unknown").upper()
            title = p.title
            vol = p.volume or "---"
            price = f"{p.last_price:.2f} €" if p.last_price else "---"
            
            table.add_row(
                str(p.id),
                store,
                brand,
                title,
                vol,
                price
            )
        
        console.print(table)
        console.print(f"[dim]Total products in database: {len(products)}[/dim]")
        console.print(f"\n[bold green]✅ Intelligence update complete.[/bold green]")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(inspect())
