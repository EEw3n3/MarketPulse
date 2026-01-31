import sqlite3
import asyncio
from sqlalchemy.future import select
from app.core.database import async_session, init_db
from app.domain.models import ScrapingRule, Product, ProductGroup, PriceHistory

LAB_DB = 'lab/lab_test.db'

def get_all_rows(conn, table_name):
    try:
        return conn.execute(f"SELECT * FROM {table_name}").fetchall()
    except sqlite3.OperationalError:
        return []

from datetime import datetime

def parse_dates(data):
    """Recursively convert known date keys to datetime objects."""
    date_keys = {'created_at', 'last_seen', 'parsed_at', 'last_success', 'last_used'}
    for k, v in data.items():
        if k in date_keys and isinstance(v, str):
            try:
                # Try common formats
                data[k] = datetime.fromisoformat(v)
            except ValueError:
                try:
                    # SQLite default format often uses space instead of T
                    data[k] = datetime.strptime(v, "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    try:
                        data[k] = datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
                    except:
                        pass # Leave as string or set to None?
    return data

async def migrate():
    print("🚀 Starting migration from Lab SQLite to Main Postgres...")
    
    # Initialize Main DB (create tables if missing)
    await init_db()
    
    conn = sqlite3.connect(LAB_DB)
    # Use generic row factory
    conn.row_factory = sqlite3.Row
    
    # Read Lab Data
    print("📖 Reading Lab data...")
    lab_rules = get_all_rows(conn, "scrapingrule")
    lab_groups = get_all_rows(conn, "productgroup")
    lab_products = get_all_rows(conn, "product")
    lab_history = get_all_rows(conn, "pricehistory")
    
    print(f"   Found: {len(lab_rules)} rules, {len(lab_groups)} groups, {len(lab_products)} products, {len(lab_history)} history items.")
    
    async with async_session() as session:
        
        # --- 1. SCRAPING RULES ---
        print("\nUsing scraping rules...")
        for row in lab_rules:
            data = dict(row)
            data.pop('id', None)
            data = parse_dates(data) # <--- Parse dates
            
            # Check existing
            stmt = select(ScrapingRule).where(ScrapingRule.domain == data['domain'])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            
            if not existing:
                try:
                    obj = ScrapingRule(**data)
                    session.add(obj)
                    print(f"   + Added rule for {data['domain']}")
                except Exception as e:
                    print(f"   ! Error adding rule {data['domain']}: {e}")
            else:
                # Optional: Update existing rule?
                # For now, skip to preserve main DB integrity or assume it's same
                pass
        
        await session.commit()
        
        # --- 2. PRODUCT GROUPS ---
        # Map old_id -> new_id
        group_id_map = {}
        
        print("\nMigrating product groups...")
        for row in lab_groups:
            data = dict(row)
            old_id = data.pop('id', None)
            data = parse_dates(data) # <--- Parse
            
            stmt = select(ProductGroup).where(ProductGroup.name == data['name'])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            
            if existing:
                group_id_map[old_id] = existing.id
            else:
                try:
                    obj = ProductGroup(**data)
                    session.add(obj)
                    await session.flush() # Get ID
                    group_id_map[old_id] = obj.id
                except Exception as e:
                    print(f"   ! Error adding group {data['name']}: {e}")
        
        await session.commit()
        
        # --- 3. PRODUCTS ---
        # Map old_id -> new_id for history
        product_id_map = {}
        
        print("\nMigrating products...")
        new_cnt = 0
        for row in lab_products:
            data = dict(row)
            old_id = data.pop('id', None)
            old_group_id = data.pop('group_id', None)
            data = parse_dates(data) # <--- Parse
            
            # Remap foreign key
            if old_group_id and old_group_id in group_id_map:
                data['group_id'] = group_id_map[old_group_id]
            else:
                data['group_id'] = None
                
            stmt = select(Product).where(Product.url == data['url'])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            
            if existing:
                product_id_map[old_id] = existing.id
            else:
                try:
                    obj = Product(**data)
                    session.add(obj)
                    await session.flush()
                    product_id_map[old_id] = obj.id
                    new_cnt += 1
                except Exception as e:
                    print(f"   ! Error adding product {data['url']}: {e}")

        await session.commit()
        print(f"   + Added {new_cnt} new products.")
        
        # --- 4. PRICE HISTORY ---
        print("\nMigrating price history...")
        hist_cnt = 0
        
        for row in lab_history:
            data = dict(row)
            data.pop('id', None)
            old_prod_id = data.pop('product_id', None)
            data = parse_dates(data) # <--- Parse
            
            if old_prod_id and old_prod_id in product_id_map:
                data['product_id'] = product_id_map[old_prod_id]
                
                try:
                    obj = PriceHistory(**data)
                    session.add(obj)
                    hist_cnt += 1
                except Exception as e:
                    pass
            
        await session.commit()
        print(f"   + Added {hist_cnt} history records.")

    conn.close()
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    # Ensure Windows loop policy if needed
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(migrate())
