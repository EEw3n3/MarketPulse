from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from app.domain.models import Product, ProductGroup
import os

DB_PATH = "sqlite:///lab/lab_test.db"

def check_groups():
    if not os.path.exists("lab/lab_test.db"):
        print("❌ Database not found.")
        return

    engine = create_engine(DB_PATH)
    Session = sessionmaker(bind=engine)
    session = Session()

    total_products = session.query(func.count(Product.id)).scalar()
    total_groups = session.query(func.count(ProductGroup.id)).scalar()
    
    print("\n" + "="*50)
    print("🧠 GROUPING EFFICIENCY REPORT")
    print("="*50)
    print(f"Total Products: {total_products}")
    print(f"Total Groups (Chains): {total_groups}")
    
    if total_groups > 0:
        ratio = total_products / total_groups
        print(f"Average variants per group: {ratio:.2f}")
    
    print("\n📝 TOP 10 LARGEST GROUPS (CHAINS):")
    # Join Product and ProductGroup to see which chains have most variants
    top_groups = session.query(
        ProductGroup.name, 
        func.count(Product.id).label('variant_count')
    ).join(Product).group_by(ProductGroup.id).order_by(func.count(Product.id).desc()).limit(10).all()
    
    for name, count in top_groups:
        print(f"- {name}: {count} variants")
    
    # Check for "Single-item groups" (Potential failures in grouping)
    single_items = session.query(func.count(ProductGroup.id)).filter(
        ProductGroup.id.notin_(
            session.query(Product.group_id).group_by(Product.group_id).having(func.count(Product.id) > 1)
        )
    ).scalar()
    
    print(f"\nGroups with only 1 item: {single_items} ({(single_items/total_groups)*100:.1f}%)")
    print("="*50)
    
    session.close()

if __name__ == "__main__":
    check_groups()
