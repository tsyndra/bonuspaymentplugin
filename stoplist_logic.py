import re


EXCLUDE_CATEGORIES = {
    "десерты",
    "десерты понедельник",
    "десерты вторник",
    "десерты среда",
    "десерты четверг",
    "пиво",
    "соусы",
}
EXCLUDE_DISHES = {
    "рис острый",
    "индиан тоник",
    "сырный соус",
    "хлебная корзинка",
    "сырный heinz",
    "хлебная белая корзинка",
    "хлебная ч/б корзинка",
    "хлебная черная корзинка",
}
EXCLUDE_ORGS = {"кожуховская", "рязань", "наметкина"}


def extract_org_number(org_name):
    """Извлечение номера из названия организации."""
    match = re.match(r"^(\d+)\.\s*", org_name)
    if match:
        return int(match.group(1))
    numbers = re.findall(r"\d+", org_name)
    return int(numbers[0]) if numbers else 0


def should_skip_org(org_name, exclude_orgs=EXCLUDE_ORGS):
    name = org_name.lower()
    return any(excluded in name for excluded in exclude_orgs)


def build_product_lookup(nomenclature):
    category_id_to_name = {
        category["id"]: category["name"].lower()
        for category in nomenclature.get("productCategories", [])
    }
    product_id_to_name = {}
    product_id_to_category = {}

    for product in nomenclature.get("products", []):
        product_id = product["id"]
        category_id = product.get("productCategoryId")
        product_id_to_name[product_id] = product["name"]
        product_id_to_category[product_id] = category_id_to_name.get(category_id, "").lower()

    return product_id_to_name, product_id_to_category


def should_include_product(
    product_name,
    category,
    exclude_categories=EXCLUDE_CATEGORIES,
    exclude_dishes=EXCLUDE_DISHES,
):
    if category in exclude_categories:
        return False
    if any(excluded.lower() in product_name.lower() for excluded in exclude_dishes):
        return False
    if category == "напитки" and "морс" not in product_name.lower():
        return False
    return True


def collect_stoplist_products(stop_list, product_id_to_name, product_id_to_category):
    products = []
    seen_product_names = set()

    for group in stop_list.get("terminalGroupStopLists", []):
        for terminal in group.get("items", []):
            for item in terminal.get("items", []):
                if not isinstance(item, dict):
                    continue

                product_id = item.get("productId")
                if not product_id:
                    continue

                product_name = product_id_to_name.get(product_id)
                if not product_name:
                    continue

                category = product_id_to_category.get(product_id, "")
                if not should_include_product(product_name, category):
                    continue

                product_key = product_name.strip().lower()
                if product_key in seen_product_names:
                    continue

                seen_product_names.add(product_key)
                products.append(product_name)

    return products


def build_report_text(org_reports):
    report_text = "📋 Отчет по стоп-листам:\n\n"

    for org_name, products in sorted(org_reports.items(), key=lambda item: extract_org_number(item[0])):
        org_number = extract_org_number(org_name)
        display_name = re.sub(r"^\d+\.\s*", "", org_name)
        report_text += f"🏪 {org_number}. {display_name}:\n"
        for product in sorted(products):
            report_text += f"• {product}\n"
        report_text += "\n"

    return report_text
