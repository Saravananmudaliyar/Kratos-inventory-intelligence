"""
audit.py — Decision audit trail and export functionality.

Records all decisions, provides history browsing, and exports to CSV.
"""

import csv
import io
from datetime import datetime
from typing import List, Dict, Optional


class AuditTrail:
    """Manages the decision audit trail."""
    
    def __init__(self):
        self.decisions: List[dict] = []
    
    def record_decisions(self, decisions: List[dict]):
        """Record a batch of decisions from the decision engine."""
        self.decisions = decisions  # Replace with latest run
    
    def append_decisions(self, decisions: List[dict]):
        """Append new decisions to the trail."""
        self.decisions.extend(decisions)
    
    def get_history(self) -> List[dict]:
        """Return full decision history."""
        return self.decisions
    
    def get_decision_by_id(self, decision_id: str) -> Optional[dict]:
        """Look up a specific decision by ID."""
        for d in self.decisions:
            if d.get("decision_id") == decision_id:
                return d
        return None
    
    def get_decisions_for_order(self, order_id: str) -> List[dict]:
        """Get all decisions related to a specific order."""
        return [d for d in self.decisions if d.get("order_id") == order_id]
    
    def get_decisions_for_sku(self, sku_id: str) -> List[dict]:
        """Get all decisions related to a specific SKU."""
        return [d for d in self.decisions if d.get("sku_id") == sku_id]
    
    def export_csv(self) -> str:
        """Export decision history as CSV string."""
        if not self.decisions:
            return "No decisions recorded."
        
        output = io.StringIO()
        
        fields = [
            "decision_id", "timestamp", "sku_id", "sku_name",
            "warehouse_id", "warehouse_name", "order_id", "customer",
            "order_priority", "order_quantity", "available_stock",
            "shortage_quantity", "risk_level", "days_to_stockout",
            "selected_action", "reason", "estimated_cost",
            "estimated_arrival", "meets_deadline",
            "feasible_options_count", "evidence_completeness",
            "demand_multiplier", "delay_additional_days",
            "express_cost_multiplier", "transfer_cost_multiplier",
        ]
        
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        
        for d in self.decisions:
            row = {**d}
            # Flatten input conditions
            conditions = d.get("input_conditions", {})
            row.update(conditions)
            # Flatten selected strategy info
            sel = d.get("selected_strategy")
            if sel:
                row["selected_action"] = sel.get("strategy", d.get("selected_action", ""))
            writer.writerow(row)
        
        return output.getvalue()
    
    def get_summary_stats(self) -> dict:
        """Get summary statistics of decisions made."""
        if not self.decisions:
            return {
                "total_decisions": 0,
                "actions": {},
                "total_cost": 0,
                "escalations": 0,
            }
        
        actions = {}
        total_cost = 0
        escalations = 0
        
        for d in self.decisions:
            action = d.get("selected_action", "UNKNOWN")
            actions[action] = actions.get(action, 0) + 1
            total_cost += d.get("estimated_cost", 0)
            if action == "ESCALATE":
                escalations += 1
        
        return {
            "total_decisions": len(self.decisions),
            "actions": actions,
            "total_cost": round(total_cost, 2),
            "escalations": escalations,
        }
