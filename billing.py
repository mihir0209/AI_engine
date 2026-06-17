"""
Billing and usage tracking module for AI Engine
Provides usage metering, cost allocation, and invoice generation
"""
import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict


@dataclass
class UsageRecord:
    """Single usage record"""
    id: str
    tenant_id: str
    user_id: Optional[str]
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Invoice:
    """Invoice for a billing period"""
    id: str
    tenant_id: str
    period_start: str
    period_end: str
    total_cost: float
    total_tokens: int
    total_requests: int
    breakdown: Dict[str, float] = field(default_factory=dict)  # provider -> cost
    status: str = "pending"  # pending, paid, overdue
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    due_date: Optional[str] = None
    paid_at: Optional[str] = None


class BillingManager:
    """Manages billing and usage tracking"""
    
    def __init__(self, data_dir: str = "data/billing"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.usage_records: List[UsageRecord] = []
        self.invoices: Dict[str, Invoice] = {}
        self._load_data()
    
    def _load_data(self):
        """Load billing data from disk"""
        # Load usage records
        usage_file = os.path.join(self.data_dir, "usage.json")
        if os.path.exists(usage_file):
            with open(usage_file, "r") as f:
                data = json.load(f)
                self.usage_records = [UsageRecord(**r) for r in data]
        
        # Load invoices
        invoices_file = os.path.join(self.data_dir, "invoices.json")
        if os.path.exists(invoices_file):
            with open(invoices_file, "r") as f:
                data = json.load(f)
                for inv_id, inv_data in data.items():
                    self.invoices[inv_id] = Invoice(**inv_data)
    
    def _save_data(self):
        """Save billing data to disk"""
        # Save usage records (keep last 10000)
        usage_file = os.path.join(self.data_dir, "usage.json")
        recent_records = self.usage_records[-10000:]
        with open(usage_file, "w") as f:
            json.dump([r.__dict__ for r in recent_records], f, indent=2)
        
        # Save invoices
        invoices_file = os.path.join(self.data_dir, "invoices.json")
        with open(invoices_file, "w") as f:
            json.dump({iid: inv.__dict__ for iid, inv in self.invoices.items()}, f, indent=2)
    
    def record_usage(
        self,
        tenant_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        user_id: str = None,
        request_id: str = None,
        metadata: Dict = None
    ) -> UsageRecord:
        """Record a usage event"""
        record_id = f"usage_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self.usage_records)}"
        
        record = UsageRecord(
            id=record_id,
            tenant_id=tenant_id,
            user_id=user_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost=cost,
            request_id=request_id,
            metadata=metadata or {}
        )
        
        self.usage_records.append(record)
        self._save_data()
        return record
    
    def get_tenant_usage(
        self,
        tenant_id: str,
        start_date: str = None,
        end_date: str = None
    ) -> Dict:
        """Get usage summary for a tenant"""
        records = [r for r in self.usage_records if r.tenant_id == tenant_id]
        
        if start_date:
            records = [r for r in records if r.timestamp >= start_date]
        if end_date:
            records = [r for r in records if r.timestamp <= end_date]
        
        total_cost = sum(r.cost for r in records)
        total_tokens = sum(r.total_tokens for r in records)
        total_requests = len(records)
        
        # Breakdown by provider
        provider_breakdown = defaultdict(lambda: {"cost": 0, "tokens": 0, "requests": 0})
        for r in records:
            provider_breakdown[r.provider]["cost"] += r.cost
            provider_breakdown[r.provider]["tokens"] += r.total_tokens
            provider_breakdown[r.provider]["requests"] += 1
        
        # Breakdown by model
        model_breakdown = defaultdict(lambda: {"cost": 0, "tokens": 0, "requests": 0})
        for r in records:
            model_breakdown[r.model]["cost"] += r.cost
            model_breakdown[r.model]["tokens"] += r.total_tokens
            model_breakdown[r.model]["requests"] += 1
        
        return {
            "tenant_id": tenant_id,
            "period": {
                "start": start_date or (records[0].timestamp if records else None),
                "end": end_date or (records[-1].timestamp if records else None)
            },
            "total_cost": round(total_cost, 6),
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "by_provider": dict(provider_breakdown),
            "by_model": dict(model_breakdown)
        }
    
    def get_user_usage(self, tenant_id: str, user_id: str) -> Dict:
        """Get usage summary for a specific user"""
        records = [r for r in self.usage_records if r.tenant_id == tenant_id and r.user_id == user_id]
        
        total_cost = sum(r.cost for r in records)
        total_tokens = sum(r.total_tokens for r in records)
        
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "total_cost": round(total_cost, 6),
            "total_tokens": total_tokens,
            "total_requests": len(records)
        }
    
    def generate_invoice(
        self,
        tenant_id: str,
        period_start: str,
        period_end: str
    ) -> Invoice:
        """Generate an invoice for a billing period"""
        records = [
            r for r in self.usage_records
            if r.tenant_id == tenant_id
            and period_start <= r.timestamp <= period_end
        ]
        
        total_cost = sum(r.cost for r in records)
        total_tokens = sum(r.total_tokens for r in records)
        
        # Breakdown by provider
        breakdown = defaultdict(float)
        for r in records:
            breakdown[r.provider] += r.cost
        
        invoice_id = f"inv_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        due_date = (datetime.now() + timedelta(days=30)).isoformat()
        
        invoice = Invoice(
            id=invoice_id,
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            total_cost=round(total_cost, 6),
            total_tokens=total_tokens,
            total_requests=len(records),
            breakdown=dict(breakdown),
            due_date=due_date
        )
        
        self.invoices[invoice_id] = invoice
        self._save_data()
        return invoice
    
    def get_invoices(self, tenant_id: str) -> List[Invoice]:
        """Get all invoices for a tenant"""
        return [inv for inv in self.invoices.values() if inv.tenant_id == tenant_id]
    
    def mark_invoice_paid(self, invoice_id: str) -> bool:
        """Mark an invoice as paid"""
        if invoice_id in self.invoices:
            self.invoices[invoice_id].status = "paid"
            self.invoices[invoice_id].paid_at = datetime.now().isoformat()
            self._save_data()
            return True
        return False
    
    def get_cost_alerts(self, tenant_id: str, threshold: float = 100.0) -> List[Dict]:
        """Check if tenant exceeds cost threshold"""
        usage = self.get_tenant_usage(tenant_id)
        alerts = []
        
        if usage["total_cost"] > threshold:
            alerts.append({
                "type": "cost_threshold",
                "tenant_id": tenant_id,
                "current_cost": usage["total_cost"],
                "threshold": threshold,
                "message": f"Tenant {tenant_id} has exceeded ${threshold} in costs"
            })
        
        # Check per-provider costs
        for provider, stats in usage.get("by_provider", {}).items():
            if stats["cost"] > threshold * 0.5:  # 50% of threshold per provider
                alerts.append({
                    "type": "provider_cost",
                    "tenant_id": tenant_id,
                    "provider": provider,
                    "cost": stats["cost"],
                    "message": f"Provider {provider} costs ${stats['cost']:.4f}"
                })
        
        return alerts


# Global instance
billing_manager = BillingManager()
