"""
compatibility.py — MODULE 2: Compatibility-Aware Substitution Engine.

Validates component compatibility using strict rules, filters incompatible
alternatives, ranks eligible substitutes, and provides full rejection reasoning.
"""

from typing import Dict, List, Optional, Any
from engine.inventory import (
    get_sku_details,
    get_inventory_map,
    get_warehouse_details,
    calculate_available_stock,
)


def get_compatibility_rules(scenario: dict) -> List[dict]:
    """Return all compatibility rules from the scenario."""
    return scenario.get("compatibility_rules", [])


def find_compatible_skus(scenario: dict, sku_id: str) -> List[dict]:
    """
    Find all SKUs that have a compatibility relationship with the given SKU.
    Returns list with compatibility status and reasoning.
    """
    rules = get_compatibility_rules(scenario)
    results = []
    
    for rule in rules:
        if rule["sku_id"] == sku_id:
            results.append({
                "substitute_sku_id": rule["compatible_with"],
                "status": rule["status"],
                "notes": rule.get("notes", ""),
                "rejection_reason": rule.get("rejection_reason", ""),
            })
    
    return results


def validate_substitute(
    scenario: dict,
    original_sku_id: str,
    substitute_sku_id: str,
    required_qty: int,
    warehouse_id: Optional[str] = None,
) -> dict:
    """
    Validate whether a substitute SKU can replace the original.
    
    Checks:
    1. Compatibility rule exists and is approved.
    2. Engineering specs match (dimensions, voltage, material for same category).
    3. Sufficient uncommitted inventory available.
    
    Returns validation result with pass/fail, reasons, and available inventory info.
    """
    sku_map = get_sku_details(scenario)
    inv_map = get_inventory_map(scenario)
    wh_map = get_warehouse_details(scenario)
    
    original = sku_map.get(original_sku_id)
    substitute = sku_map.get(substitute_sku_id)
    
    result = {
        "original_sku_id": original_sku_id,
        "substitute_sku_id": substitute_sku_id,
        "substitute_name": substitute.get("name", substitute_sku_id) if substitute else substitute_sku_id,
        "eligible": True,
        "checks": [],
        "rejection_reasons": [],
        "warnings": [],
        "available_locations": [],
        "total_available": 0,
        "unit_cost": None,
        "cost_difference": None,
    }
    
    if not original:
        result["eligible"] = False
        result["rejection_reasons"].append(f"Original SKU {original_sku_id} not found in catalog.")
        return result
    
    if not substitute:
        result["eligible"] = False
        result["rejection_reasons"].append(f"Substitute SKU {substitute_sku_id} not found in catalog.")
        return result
    
    # Check 1: Compatibility rule
    compat_rules = find_compatible_skus(scenario, original_sku_id)
    matching_rule = None
    for cr in compat_rules:
        if cr["substitute_sku_id"] == substitute_sku_id:
            matching_rule = cr
            break
    
    if matching_rule is None:
        result["eligible"] = False
        result["rejection_reasons"].append(
            f"No compatibility rule found between {original_sku_id} and {substitute_sku_id}. "
            f"Substitute requires engineering verification before use."
        )
        result["warnings"].append("VERIFICATION REQUIRED: No compatibility data on file.")
        result["checks"].append({"check": "Compatibility Rule", "status": "MISSING", "detail": "No rule on file."})
        return result
    
    if matching_rule["status"] == "rejected":
        result["eligible"] = False
        result["rejection_reasons"].append(
            f"Compatibility REJECTED: {matching_rule.get('rejection_reason', 'No reason provided.')}"
        )
        result["checks"].append({
            "check": "Compatibility Rule",
            "status": "REJECTED",
            "detail": matching_rule.get("rejection_reason", ""),
        })
        return result
    
    if matching_rule["status"] == "approved":
        result["checks"].append({
            "check": "Compatibility Rule",
            "status": "APPROVED",
            "detail": matching_rule.get("notes", "Approved for substitution."),
        })
    else:
        result["eligible"] = False
        result["warnings"].append(f"Compatibility status is '{matching_rule['status']}' — requires verification.")
        result["checks"].append({
            "check": "Compatibility Rule",
            "status": "UNKNOWN",
            "detail": f"Status: {matching_rule['status']}",
        })
        return result
    
    # Check 2: Engineering spec validation
    spec_checks = []
    if original.get("category") != substitute.get("category"):
        result["eligible"] = False
        result["rejection_reasons"].append(
            f"Category mismatch: {original.get('category')} vs {substitute.get('category')}."
        )
        spec_checks.append({"check": "Category", "status": "FAIL", "detail": f"{original.get('category')} ≠ {substitute.get('category')}"})
    else:
        spec_checks.append({"check": "Category", "status": "PASS", "detail": original.get("category")})
    
    if original.get("dimensions") and substitute.get("dimensions"):
        if original["dimensions"] != substitute["dimensions"]:
            result["eligible"] = False
            result["rejection_reasons"].append(
                f"Dimension mismatch: {original['dimensions']} vs {substitute['dimensions']}."
            )
            spec_checks.append({"check": "Dimensions", "status": "FAIL", "detail": f"{original['dimensions']} ≠ {substitute['dimensions']}"})
        else:
            spec_checks.append({"check": "Dimensions", "status": "PASS", "detail": original["dimensions"]})
    
    if original.get("voltage") and substitute.get("voltage"):
        if original["voltage"] != substitute["voltage"]:
            result["eligible"] = False
            result["rejection_reasons"].append(
                f"Voltage mismatch: {original['voltage']} vs {substitute['voltage']}. Not electrically compatible."
            )
            spec_checks.append({"check": "Voltage", "status": "FAIL", "detail": f"{original['voltage']} ≠ {substitute['voltage']}"})
        else:
            spec_checks.append({"check": "Voltage", "status": "PASS", "detail": original["voltage"]})
    
    if original.get("material") and substitute.get("material"):
        if original["material"] != substitute["material"]:
            result["warnings"].append(
                f"Material differs: {original['material']} vs {substitute['material']}. May need review."
            )
            spec_checks.append({"check": "Material", "status": "WARNING", "detail": f"{original['material']} vs {substitute['material']}"})
        else:
            spec_checks.append({"check": "Material", "status": "PASS", "detail": original["material"]})
    
    result["checks"].extend(spec_checks)
    
    if not result["eligible"]:
        return result
    
    # Check 3: Available inventory
    total_available = 0
    for wh_id, skus in inv_map.items():
        if substitute_sku_id in skus:
            inv = skus[substitute_sku_id]
            avail_info = calculate_available_stock(inv["on_hand"], inv["reserved"])
            avail = avail_info["available"]
            sub_safety = substitute.get("safety_stock", 0)
            usable = max(0, avail - sub_safety)
            if usable > 0:
                wh = wh_map.get(wh_id, {})
                result["available_locations"].append({
                    "warehouse_id": wh_id,
                    "warehouse_name": wh.get("name", wh_id),
                    "on_hand": inv["on_hand"],
                    "reserved": inv["reserved"],
                    "available": avail,
                    "safety_stock": sub_safety,
                    "usable_for_substitution": usable,
                    "transfer_cost_per_unit": wh.get("transfer_cost_per_unit", 0),
                    "transfer_days": wh.get("transfer_days", 0),
                })
                total_available += usable
    
    result["total_available"] = total_available
    result["unit_cost"] = substitute.get("unit_cost", 0)
    result["cost_difference"] = round(
        (substitute.get("unit_cost", 0) - original.get("unit_cost", 0)), 2
    )
    
    if total_available < required_qty:
        result["eligible"] = False
        result["rejection_reasons"].append(
            f"Insufficient substitute inventory: {total_available} available (after safety stock), "
            f"{required_qty} required."
        )
        result["checks"].append({
            "check": "Inventory Availability",
            "status": "FAIL",
            "detail": f"{total_available} usable vs {required_qty} needed.",
        })
    else:
        result["checks"].append({
            "check": "Inventory Availability",
            "status": "PASS",
            "detail": f"{total_available} usable, {required_qty} needed.",
        })
    
    return result


def evaluate_all_substitutes(
    scenario: dict,
    sku_id: str,
    required_qty: int,
    warehouse_id: Optional[str] = None,
) -> dict:
    """
    MODULE 2 main entry point.
    
    Evaluates all potential substitutes for a given SKU, applying strict 
    compatibility rules and ranking eligible options.
    
    Returns dict with eligible substitutes, rejected alternatives, and reasoning.
    """
    sku_map = get_sku_details(scenario)
    all_skus = list(sku_map.keys())
    
    # Find all potential substitutes (same category or explicit rules)
    candidates = set()
    
    # From explicit compatibility rules
    for rule in get_compatibility_rules(scenario):
        if rule["sku_id"] == sku_id:
            candidates.add(rule["compatible_with"])
    
    # Also check same-category SKUs without explicit rules
    original = sku_map.get(sku_id)
    if original:
        for other_id, other in sku_map.items():
            if other_id != sku_id and other.get("category") == original.get("category"):
                candidates.add(other_id)
    
    eligible = []
    rejected = []
    
    for candidate_id in candidates:
        validation = validate_substitute(scenario, sku_id, candidate_id, required_qty, warehouse_id)
        if validation["eligible"]:
            eligible.append(validation)
        else:
            rejected.append(validation)
    
    # Rank eligible by: cost (lower is better), then availability (higher is better)
    eligible.sort(key=lambda x: (x.get("unit_cost", 999), -x.get("total_available", 0)))
    
    return {
        "original_sku_id": sku_id,
        "original_name": original.get("name", sku_id) if original else sku_id,
        "required_qty": required_qty,
        "eligible_substitutes": eligible,
        "rejected_alternatives": rejected,
        "has_eligible": len(eligible) > 0,
        "best_substitute": eligible[0] if eligible else None,
    }
