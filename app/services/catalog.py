from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class Product(BaseModel):
    sku: str
    name: str
    category: str
    price_inr: float
    margin_percentage: float
    stock_quantity: int
    description: str


MOCK_CATALOG: Dict[str, Product] = {
    "SKU-KBD-01": Product(
        sku="SKU-KBD-01",
        name="Tactile Silent Mechanical Keyboard V2",
        category="Keyboards",
        price_inr=4499.00,
        margin_percentage=45.0,
        stock_quantity=15,
        description="Compact 75% hot-swappable mechanical keyboard with silent tactile switches."
    ),
    "SKU-WST-01": Product(
        sku="SKU-WST-01",
        name="Ergonomic Memory Foam Wrist Rest",
        category="Accessories",
        price_inr=599.00,
        margin_percentage=60.0,
        stock_quantity=40,
        description="Padded memory foam wrist rest designed for 75% and tenkeyless keyboards."
    ),
    "SKU-MAT-01": Product(
        sku="SKU-MAT-01",
        name="Waterproof Desk Mat (900x400mm)",
        category="Accessories",
        price_inr=899.00,
        margin_percentage=55.0,
        stock_quantity=25,
        description="Micro-textured cloth desk pad with anti-slip rubber base."
    ),
    "SKU-MSE-01": Product(
        sku="SKU-MSE-01",
        name="Precision Wireless Ergonomic Mouse",
        category="Mice",
        price_inr=2999.00,
        margin_percentage=40.0,
        stock_quantity=8,
        description="Dual-mode Bluetooth and 2.4GHz wireless mouse with customizable side buttons."
    )
}


class CatalogService:
    @staticmethod
    def get_by_sku(sku: str) -> Optional[Product]:
        return MOCK_CATALOG.get(sku.upper())

    @staticmethod
    def search_catalog(query: str, max_price: Optional[float] = None) -> List[Product]:
        """
        Filters catalog by keyword match and max price constraint.
        """
        query_terms = query.lower().split()
        matched_products = []

        for product in MOCK_CATALOG.values():
            if max_price and product.price_inr > max_price:
                continue

            text_corpus = f"{product.name} {product.category} {product.description}".lower()
            if any(term in text_corpus for term in query_terms):
                matched_products.append(product)

        return matched_products


catalog_service = CatalogService()
