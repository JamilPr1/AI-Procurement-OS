"""Local storage — SQLite + JSON file entities."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.dedup import deal_dedupe_key, lead_dedupe_key, supplier_dedupe_key
from src.core.company_name import normalize_lead_record
from src.core.pipeline_stages import PIPELINE_STAGES
from src.core.logger import PlatformLogger


SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'agency',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    data JSON NOT NULL,
    lead_score REAL DEFAULT 0,
    status TEXT DEFAULT 'new',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS deals (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    lead_id TEXT,
    stage TEXT NOT NULL DEFAULT 'qualification',
    buyer_requirements JSON,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS suppliers (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    factory_name TEXT NOT NULL,
    data JSON NOT NULL,
    trust_score REAL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS rfqs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deal_id TEXT NOT NULL,
    data JSON NOT NULL,
    status TEXT DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (deal_id) REFERENCES deals(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deal_id TEXT NOT NULL,
    data JSON NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (deal_id) REFERENCES deals(id)
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT,
    agent_id TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    input_data JSON,
    output_data JSON,
    status TEXT NOT NULL,
    duration_ms INTEGER,
    model TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_leads_tenant ON leads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_deals_tenant ON deals(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_id);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    current_stage TEXT,
    pending_gate TEXT,
    stage_status JSON NOT NULL DEFAULT '{}',
    context JSON NOT NULL DEFAULT '{}',
    summary JSON,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tenant_settings (
    tenant_id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    plan TEXT NOT NULL DEFAULT 'starter',
    branding JSON,
    margin_percent REAL DEFAULT 15,
    store_enabled INTEGER DEFAULT 1,
    tagline TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS store_sessions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'intake',
    product_query TEXT,
    answers JSON NOT NULL DEFAULT '{}',
    spec JSON,
    quote JSON,
    deal_id TEXT,
    order_id TEXT,
    customer_email TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE INDEX IF NOT EXISTS idx_store_sessions_tenant ON store_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_settings_slug ON tenant_settings(slug);

CREATE TABLE IF NOT EXISTS tenant_users (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    email TEXT NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    name TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(tenant_id, email),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);
"""


class Storage:
    """SQLite for structured records; JSON files for large documents."""

    ENTITY_DIRS = [
        "leads",
        "companies",
        "products",
        "suppliers",
        "rfqs",
        "quotes",
        "proposals",
        "orders",
        "hot_leads",
        "outreach",
        "outreach_images",
        "personalization",
        "reviews",
        "supplier_approvals",
        "supplier_selection",
        "store_sessions",
        "niche",
    ]

    def __init__(self, db_path: Path, data_dir: Path, logger: PlatformLogger) -> None:
        self.db_path = db_path
        self.data_dir = data_dir
        self.logger = logger
        self._local = threading.local()

    def initialize(self, agency_config: dict[str, Any]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for sub in self.ENTITY_DIRS:
            (self.data_dir / sub).mkdir(exist_ok=True)

        conn = self._connect()
        conn.executescript(SCHEMA)
        conn.commit()
        self._migrate_schema(conn)

        tenant_id = agency_config.get("tenant_id", "agency_primary")
        tenant_name = agency_config.get("name", "Agency")
        now = _utc_now()
        conn.execute(
            "INSERT OR IGNORE INTO tenants (id, name, type, created_at) VALUES (?, ?, 'agency', ?)",
            (tenant_id, tenant_name, now),
        )
        conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def save_json_entity(self, entity_type: str, entity_id: str, data: dict[str, Any]) -> Path:
        path = self.data_dir / entity_type / f"{entity_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return path

    def load_json_entity(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        path = self.data_dir / entity_type / f"{entity_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def reset_workspace(self, tenant_id: str, *, include_suppliers: bool = False) -> dict[str, Any]:
        """Delete all leads, deals, and related JSON artifacts for a fresh start."""
        import shutil

        conn = self._connect()
        deal_rows = conn.execute("SELECT id FROM deals WHERE tenant_id = ?", (tenant_id,)).fetchall()
        lead_rows = conn.execute("SELECT id FROM leads WHERE tenant_id = ?", (tenant_id,)).fetchall()
        deal_ids = [r[0] for r in deal_rows]
        lead_ids = [r[0] for r in lead_rows]

        for did in deal_ids:
            conn.execute("DELETE FROM orders WHERE deal_id = ?", (did,))
            conn.execute("DELETE FROM rfqs WHERE deal_id = ?", (did,))
        conn.execute("DELETE FROM deals WHERE tenant_id = ?", (tenant_id,))
        conn.execute("DELETE FROM leads WHERE tenant_id = ?", (tenant_id,))
        conn.execute("DELETE FROM pipeline_runs WHERE tenant_id = ?", (tenant_id,))
        conn.commit()

        entity_map = {
            "leads": lead_ids,
            "companies": lead_ids,
            "hot_leads": lead_ids,
            "outreach": lead_ids,
            "personalization": lead_ids,
            "products": deal_ids,
            "proposals": deal_ids,
            "quotes": deal_ids,
            "supplier_approvals": deal_ids,
            "reviews": lead_ids + deal_ids,
        }
        removed = 0
        for entity_type, ids in entity_map.items():
            for eid in ids:
                path = self.data_dir / entity_type / f"{eid}.json"
                if path.exists():
                    path.unlink()
                    removed += 1
        for sub in ("rfqs", "orders"):
            for path in (self.data_dir / sub).glob("*.json"):
                path.unlink()
                removed += 1
        images_dir = self.data_dir / "images"
        if images_dir.exists():
            shutil.rmtree(images_dir)
        images_dir.mkdir(parents=True, exist_ok=True)
        niche_dir = self.data_dir / "niche"
        niche_dir.mkdir(parents=True, exist_ok=True)
        for path in niche_dir.glob("*.json"):
            path.unlink()

        suppliers_deleted = 0
        if include_suppliers:
            conn.execute("DELETE FROM suppliers WHERE tenant_id = ?", (tenant_id,))
            conn.commit()
            for path in (self.data_dir / "suppliers").glob("*.json"):
                path.unlink()
                suppliers_deleted += 1

        return {
            "leads_deleted": len(lead_ids),
            "deals_deleted": len(deal_ids),
            "files_removed": removed,
            "suppliers_deleted": suppliers_deleted,
        }

    def repair_company_names(self, tenant_id: str) -> dict[str, Any]:
        """Fix SEO page titles stored as company names; refresh outreach/proposal drafts."""
        from src.core.draft_composer import (
            compose_outreach_email,
            compose_personalization,
            compose_proposal_client_email,
        )

        conn = self._connect()
        leads_fixed = 0
        drafts_fixed = 0
        rows = conn.execute(
            "SELECT id, company_name, data FROM leads WHERE tenant_id = ?", (tenant_id,)
        ).fetchall()
        for row in rows:
            data = json.loads(row["data"])
            normalized = normalize_lead_record({**data, "company_name": row["company_name"]})
            new_name = normalized.get("company_name", row["company_name"])
            outreach = self.load_json_entity("outreach", row["id"])
            name_changed = new_name != row["company_name"]
            needs_draft_refresh = not outreach or outreach.get("status") != "sent"

            if name_changed:
                data["email"] = normalized.get("email") or data.get("email", "")
                conn.execute(
                    "UPDATE leads SET company_name=?, data=?, updated_at=? WHERE id=?",
                    (new_name, json.dumps(data), _utc_now(), row["id"]),
                )
                self.save_json_entity("leads", row["id"], data)
                leads_fixed += 1

            if name_changed or needs_draft_refresh:
                profile = self.load_json_entity("companies", row["id"]) or {}
                top_lead = {**data, "id": row["id"], "company_name": new_name}
                top_lead["email"] = normalized.get("email") or data.get("email", "")
                pers = compose_personalization(top_lead, profile)
                self.save_json_entity("personalization", row["id"], pers)
                images = profile.get("product_images") or []
                from src.core.hot_leads import extract_buying_intent
                from src.core.outreach_images import resolve_outreach_images

                intent = extract_buying_intent(data, profile)
                factory_images = resolve_outreach_images(
                    row["id"], top_lead, intent, self, tenant_id,
                    dashboard_base="http://127.0.0.1:8765", force_refresh=True,
                )
                outreach = compose_outreach_email(
                    top_lead, pers, product_images=factory_images or images, profile=profile,
                )
                self.save_json_entity("outreach", row["id"], outreach)
                drafts_fixed += 1

        for deal in self.list_tracking_deals(tenant_id) + self.list_closed_deals(tenant_id):
            lead_id = deal.get("lead_id")
            if not lead_id:
                continue
            lead_row = conn.execute("SELECT company_name, data FROM leads WHERE id=?", (lead_id,)).fetchone()
            if not lead_row:
                continue
            lead_data = json.loads(lead_row["data"])
            lead_data["company_name"] = lead_row["company_name"]
            proposal = self.load_json_entity("proposals", deal["id"]) or {}
            if not proposal:
                continue
            company = lead_row["company_name"]
            changed = False
            client_price = float(proposal.get("client_price_usd") or 0)
            if client_price and not proposal.get("factory_cost_usd"):
                margin_pct = float(proposal.get("margin_percent") or 15)
                factory_cost = round(client_price / (1 + margin_pct / 100), 2)
                proposal["factory_cost_usd"] = factory_cost
                proposal["margin_usd"] = round(client_price - factory_cost, 2)
                proposal["margin_percent"] = margin_pct
                changed = True
            if company not in (proposal.get("title") or ""):
                proposal["title"] = f"Proposal for {company}"
                changed = True
            if changed:
                proposal["client_email_draft"] = compose_proposal_client_email(proposal, lead_data)
                self.save_json_entity("proposals", deal["id"], proposal)
                drafts_fixed += 1
        conn.commit()
        return {"leads_fixed": leads_fixed, "drafts_fixed": drafts_fixed}

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        for table, col in (("leads", "dedupe_key"), ("suppliers", "dedupe_key")):
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if col not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
        deal_cols = {r[1] for r in conn.execute("PRAGMA table_info(deals)")}
        if "closed_manually" not in deal_cols:
            conn.execute("ALTER TABLE deals ADD COLUMN closed_manually INTEGER DEFAULT 0")
        if "tracking_entered_at" not in deal_cols:
            conn.execute("ALTER TABLE deals ADD COLUMN tracking_entered_at TEXT")
        conn.commit()
        # Reopen deals that were auto-closed (never manually closed by user)
        conn.execute(
            """UPDATE deals SET stage='order_tracking', status='tracking', closed_manually=0
               WHERE stage='closed' AND (closed_manually IS NULL OR closed_manually=0)"""
        )
        # Ensure proposal_sent deals are in tracking status
        conn.execute(
            """UPDATE deals SET status='tracking'
               WHERE stage IN ('proposal_sent','order_tracking','finance','client_review')
               AND status NOT IN ('closed','completed')"""
        )
        conn.commit()
        # Backfill dedupe keys for existing rows
        for row in conn.execute("SELECT id, data FROM leads WHERE dedupe_key IS NULL OR dedupe_key = ''"):
            data = json.loads(row["data"])
            key = lead_dedupe_key(data)
            if key:
                conn.execute("UPDATE leads SET dedupe_key = ? WHERE id = ?", (key, row["id"]))
        for row in conn.execute("SELECT id, data FROM suppliers WHERE dedupe_key IS NULL OR dedupe_key = ''"):
            data = json.loads(row["data"])
            key = supplier_dedupe_key(data)
            if key:
                conn.execute("UPDATE suppliers SET dedupe_key = ? WHERE id = ?", (key, row["id"]))
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_dedupe ON leads(tenant_id, dedupe_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_dedupe ON suppliers(tenant_id, dedupe_key)")
        conn.commit()

    def upsert_lead(self, tenant_id: str, company_name: str, data: dict[str, Any]) -> tuple[str, bool]:
        """Returns (lead_id, is_new). Updates existing lead if domain/email matches."""
        data = normalize_lead_record({**data, "company_name": company_name})
        company_name = data["company_name"]
        key = lead_dedupe_key(data)
        conn = self._connect()
        now = _utc_now()
        score = data.get("lead_score", 0)
        if key:
            row = conn.execute(
                "SELECT id, data, lead_score FROM leads WHERE tenant_id = ? AND dedupe_key = ?",
                (tenant_id, key),
            ).fetchone()
            if row:
                lead_id = row["id"]
                old = json.loads(row["data"])
                merged = {**old, **data, "last_seen_at": now}
                new_score = max(float(row["lead_score"] or 0), float(score))
                conn.execute(
                    "UPDATE leads SET company_name=?, data=?, lead_score=?, updated_at=? WHERE id=?",
                    (company_name, json.dumps(merged), new_score, now, lead_id),
                )
                conn.commit()
                self.save_json_entity("leads", lead_id, merged)
                self.logger.change("lead", lead_id, "updated", after={"dedupe_key": key, "score": new_score})
                return lead_id, False
        lead_id = str(uuid.uuid4())
        data = {**data, "first_seen_at": data.get("first_seen_at", now), "last_seen_at": now}
        conn.execute(
            "INSERT INTO leads (id, tenant_id, company_name, dedupe_key, data, lead_score, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?)",
            (lead_id, tenant_id, company_name, key, json.dumps(data), score, now, now),
        )
        conn.commit()
        self.save_json_entity("leads", lead_id, data)
        self.logger.change("lead", lead_id, "created", after={"company_name": company_name, "dedupe_key": key})
        return lead_id, True

    def upsert_supplier(self, tenant_id: str, factory_name: str, data: dict[str, Any]) -> tuple[str, bool]:
        key = supplier_dedupe_key(data)
        conn = self._connect()
        now = _utc_now()
        score = data.get("trust_score", 0)
        if key:
            row = conn.execute(
                "SELECT id, data, trust_score FROM suppliers WHERE tenant_id = ? AND dedupe_key = ?",
                (tenant_id, key),
            ).fetchone()
            if row:
                sid = row["id"]
                old = json.loads(row["data"])
                merged = {**old, **data, "last_seen_at": now}
                new_score = max(float(row["trust_score"] or 0), float(score))
                conn.execute(
                    "UPDATE suppliers SET factory_name=?, data=?, trust_score=?, updated_at=? WHERE id=?",
                    (factory_name, json.dumps(merged), new_score, now, sid),
                )
                conn.commit()
                self.save_json_entity("suppliers", sid, merged)
                return sid, False
        sid = str(uuid.uuid4())
        data = {**data, "first_seen_at": data.get("first_seen_at", now), "last_seen_at": now}
        conn.execute(
            "INSERT INTO suppliers (id, tenant_id, factory_name, dedupe_key, data, trust_score, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, tenant_id, factory_name, key, json.dumps(data), score, now, now),
        )
        conn.commit()
        self.save_json_entity("suppliers", sid, data)
        self.logger.change("supplier", sid, "created", after={"factory_name": factory_name})
        return sid, True

    def create_lead(self, tenant_id: str, company_name: str, data: dict[str, Any]) -> str:
        lead_id, _ = self.upsert_lead(tenant_id, company_name, data)
        return lead_id

    def list_leads(self, tenant_id: str, limit: int = 200) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM leads WHERE tenant_id = ? ORDER BY updated_at DESC LIMIT ?",
            (tenant_id, limit),
        ).fetchall()
        return [self._parse_row(r, "data") for r in rows]

    def list_deals(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """SELECT d.*, l.company_name as lead_company
               FROM deals d LEFT JOIN leads l ON d.lead_id = l.id
               WHERE d.tenant_id = ? ORDER BY d.updated_at DESC LIMIT ?""",
            (tenant_id, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = self._parse_row(r, "buyer_requirements")
            out.append(d)
        return out

    def list_suppliers(self, tenant_id: str, limit: int = 200) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM suppliers WHERE tenant_id = ? ORDER BY updated_at DESC LIMIT ?",
            (tenant_id, limit),
        ).fetchall()
        return [self._parse_row(r, "data") for r in rows]

    def list_agent_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._parse_row(r, "input_data", "output_data") for r in rows]

    def get_latest_agent_runs(self) -> dict[str, dict[str, Any]]:
        """Most recent run per agent_id."""
        conn = self._connect()
        rows = conn.execute(
            """SELECT ar.* FROM agent_runs ar
               INNER JOIN (
                   SELECT agent_id, MAX(created_at) AS max_created
                   FROM agent_runs GROUP BY agent_id
               ) latest ON ar.agent_id = latest.agent_id AND ar.created_at = latest.max_created"""
        ).fetchall()
        return {r["agent_id"]: self._parse_row(r, "input_data", "output_data") for r in rows}

    def get_activity_log(self, limit: int = 150) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for log_file in ("agents/agents.log", "changes/changes.log", "system/platform.log"):
            path = self.data_dir.parent / "logs" / log_file
            if not path.exists():
                continue
            try:
                lines = path.read_text(encoding="utf-8").strip().split("\n")
                for line in lines[-limit:]:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append({**json.loads(line), "_source": log_file})
                    except json.JSONDecodeError:
                        entries.append({"timestamp": "", "message": line, "_source": log_file})
            except OSError:
                pass
        entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return entries[:limit]

    @staticmethod
    def _parse_row(row: sqlite3.Row, *json_cols: str) -> dict[str, Any]:
        d = dict(row)
        for col in json_cols:
            if col in d and d[col]:
                try:
                    d[col] = json.loads(d[col])
                except (json.JSONDecodeError, TypeError):
                    pass
        if "data" in d and isinstance(d["data"], str):
            try:
                d["data"] = json.loads(d["data"])
            except json.JSONDecodeError:
                pass
        return d

    def create_deal(self, tenant_id: str, lead_id: str | None, stage: str = "qualification") -> str:
        deal_id = str(uuid.uuid4())
        now = _utc_now()
        conn = self._connect()
        conn.execute(
            "INSERT INTO deals (id, tenant_id, lead_id, stage, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (deal_id, tenant_id, lead_id, stage, now, now),
        )
        conn.commit()
        self.logger.change("deal", deal_id, "created", after={"stage": stage, "lead_id": lead_id})
        return deal_id

    def update_deal(
        self,
        deal_id: str,
        *,
        stage: str | None = None,
        status: str | None = None,
        buyer_requirements: dict | None = None,
        closed_manually: bool | None = None,
        tracking_entered_at: str | None = None,
    ) -> None:
        conn = self._connect()
        row = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
        if not row:
            return
        before = dict(row)
        now = _utc_now()
        updates: dict[str, Any] = {"updated_at": now}
        if stage:
            updates["stage"] = stage
        if status:
            updates["status"] = status
        if buyer_requirements is not None:
            updates["buyer_requirements"] = json.dumps(buyer_requirements)
        if closed_manually is not None:
            updates["closed_manually"] = 1 if closed_manually else 0
        if tracking_entered_at is not None:
            updates["tracking_entered_at"] = tracking_entered_at

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE deals SET {set_clause} WHERE id = ?", (*updates.values(), deal_id))
        conn.commit()
        self.logger.change("deal", deal_id, "updated", before=before, after=updates)

    def list_tracking_deals(self, tenant_id: str) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """SELECT d.*, l.company_name as lead_company, l.data as lead_data
               FROM deals d LEFT JOIN leads l ON d.lead_id = l.id
               WHERE d.tenant_id = ? AND d.stage != 'closed'
               AND (d.status = 'tracking' OR d.stage IN ('proposal_sent','order_tracking','finance','client_review','awaiting_payment','production'))
               AND (d.closed_manually IS NULL OR d.closed_manually = 0)
               ORDER BY d.updated_at DESC""",
            (tenant_id,),
        ).fetchall()
        return [self._parse_row(r, "buyer_requirements") for r in rows]

    def list_closed_deals(self, tenant_id: str) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """SELECT d.*, l.company_name as lead_company, l.data as lead_data
               FROM deals d LEFT JOIN leads l ON d.lead_id = l.id
               WHERE d.tenant_id = ? AND (d.stage = 'closed' OR d.closed_manually = 1 OR d.status IN ('closed','completed'))
               ORDER BY d.updated_at DESC""",
            (tenant_id,),
        ).fetchall()
        return [self._parse_row(r, "buyer_requirements") for r in rows]

    def list_active_sourcing_deals(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """SELECT d.*, l.company_name as lead_company
               FROM deals d LEFT JOIN leads l ON d.lead_id = l.id
               WHERE d.tenant_id = ? AND d.stage != 'closed'
               AND (d.closed_manually IS NULL OR d.closed_manually = 0)
               AND d.status != 'tracking'
               AND d.stage NOT IN ('proposal_sent','order_tracking','finance','client_review','awaiting_payment','production')
               ORDER BY d.updated_at DESC LIMIT ?""",
            (tenant_id, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = self._parse_row(r, "buyer_requirements")
            out.append(d)
        return out

    def close_deal_manually(self, deal_id: str, tenant_id: str) -> bool:
        conn = self._connect()
        row = conn.execute(
            "SELECT id FROM deals WHERE id = ? AND tenant_id = ?", (deal_id, tenant_id)
        ).fetchone()
        if not row:
            return False
        now = _utc_now()
        conn.execute(
            "UPDATE deals SET stage='closed', status='closed', closed_manually=1, updated_at=? WHERE id=?",
            (now, deal_id),
        )
        lead_row = conn.execute("SELECT lead_id FROM deals WHERE id=?", (deal_id,)).fetchone()
        if lead_row and lead_row["lead_id"]:
            conn.execute(
                "UPDATE leads SET status='won', updated_at=? WHERE id=?",
                (now, lead_row["lead_id"]),
            )
        conn.commit()
        return True

    def revenue_stats(self, tenant_id: str) -> dict[str, Any]:
        tracking = self.list_tracking_deals(tenant_id)
        closed = self.list_closed_deals(tenant_id)
        expected = 0.0
        billed = 0.0
        closed_rev = 0.0
        factory_cost = 0.0
        margin_total = 0.0
        for d in tracking:
            prop = self.load_json_entity("proposals", d["id"]) or {}
            order = self.get_order_for_deal(d["id"])
            od = (order or {}).get("data") or {}
            p = float(prop.get("client_price_usd") or 0)
            expected += p
            factory_cost += float(prop.get("factory_cost_usd") or 0)
            margin_total += float(prop.get("margin_usd") or (p - float(prop.get("factory_cost_usd") or 0)))
            billed += float(od.get("amount_billed_usd") or od.get("deposit_received_usd") or 0)
        for d in closed:
            prop = self.load_json_entity("proposals", d["id"]) or {}
            p = float(prop.get("client_price_usd") or 0)
            closed_rev += p
            factory_cost += float(prop.get("factory_cost_usd") or 0)
            margin_total += float(prop.get("margin_usd") or (p - float(prop.get("factory_cost_usd") or 0)))
        return {
            "tracking_count": len(tracking),
            "closed_count": len(closed),
            "pipeline_expected_usd": round(expected, 2),
            "factory_cost_usd": round(factory_cost, 2),
            "margin_usd": round(margin_total, 2),
            "margin_percent": round(100 * margin_total / expected, 1) if expected else 0,
            "billed_usd": round(billed, 2),
            "outstanding_usd": round(max(0, expected - billed), 2),
            "closed_revenue_usd": round(closed_rev, 2),
            "total_won_usd": round(closed_rev + billed, 2),
        }

    def create_supplier(self, tenant_id: str, factory_name: str, data: dict[str, Any]) -> str:
        sid, _ = self.upsert_supplier(tenant_id, factory_name, data)
        return sid

    def create_rfq(self, tenant_id: str, deal_id: str, data: dict[str, Any]) -> str:
        rfq_id = str(uuid.uuid4())
        now = _utc_now()
        conn = self._connect()
        conn.execute(
            "INSERT INTO rfqs (id, tenant_id, deal_id, data, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'draft', ?, ?)",
            (rfq_id, tenant_id, deal_id, json.dumps(data), now, now),
        )
        conn.commit()
        self.save_json_entity("rfqs", rfq_id, data)
        self.logger.change("rfq", rfq_id, "created", after={"deal_id": deal_id})
        return rfq_id

    def create_order(self, tenant_id: str, deal_id: str, data: dict[str, Any]) -> str:
        order_id = str(uuid.uuid4())
        now = _utc_now()
        conn = self._connect()
        conn.execute(
            "INSERT INTO orders (id, tenant_id, deal_id, data, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
            (order_id, tenant_id, deal_id, json.dumps(data), now, now),
        )
        conn.commit()
        self.save_json_entity("orders", order_id, data)
        self.logger.change("order", order_id, "created", after={"deal_id": deal_id})
        return order_id

    def get_lead(self, lead_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not row:
            return None
        return self._parse_row(row, "data")

    def get_supplier(self, supplier_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        row = conn.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        if not row:
            return None
        return self._parse_row(row, "data")

    def get_deal(self, deal_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        row = conn.execute(
            """SELECT d.*, l.company_name as lead_company, l.data as lead_data, l.lead_score
               FROM deals d LEFT JOIN leads l ON d.lead_id = l.id WHERE d.id = ?""",
            (deal_id,),
        ).fetchone()
        if not row:
            return None
        d = self._parse_row(row, "buyer_requirements")
        if isinstance(d.get("lead_data"), str):
            try:
                d["lead_data"] = json.loads(d["lead_data"])
            except json.JSONDecodeError:
                d["lead_data"] = {}
        return d

    def get_deals_for_lead(self, lead_id: str) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM deals WHERE lead_id = ? ORDER BY updated_at DESC", (lead_id,)
        ).fetchall()
        return [self._parse_row(r, "buyer_requirements") for r in rows]

    def get_rfqs_for_deal(self, deal_id: str) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute("SELECT * FROM rfqs WHERE deal_id = ? ORDER BY created_at DESC", (deal_id,)).fetchall()
        return [self._parse_row(r, "data") for r in rows]

    def get_order_for_deal(self, deal_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        row = conn.execute("SELECT * FROM orders WHERE deal_id = ? ORDER BY created_at DESC LIMIT 1", (deal_id,)).fetchone()
        if not row:
            return None
        return self._parse_row(row, "data")

    def get_lead_detail(self, lead_id: str) -> dict[str, Any] | None:
        lead = self.get_lead(lead_id)
        if not lead:
            return None
        data = lead.get("data") or {}
        company = self.load_json_entity("companies", lead_id) or {}
        deals = self.get_deals_for_lead(lead_id)
        return {
            "lead": lead,
            "data": data,
            "company_profile": company,
            "deals": deals,
            "sourcing_needs": self._infer_sourcing_needs(data, company, deals),
        }

    def get_deal_detail(self, deal_id: str) -> dict[str, Any] | None:
        deal = self.get_deal(deal_id)
        if not deal:
            return None
        lead_id = deal.get("lead_id")
        return {
            "deal": deal,
            "requirements": deal.get("buyer_requirements") or {},
            "product_spec": self.load_json_entity("products", deal_id) or {},
            "proposal": self.load_json_entity("proposals", deal_id) or {},
            "quotes": self.load_json_entity("quotes", deal_id) or {},
            "rfqs": self.get_rfqs_for_deal(deal_id),
            "order": self.get_order_for_deal(deal_id),
            "outreach": self.load_json_entity("outreach", lead_id) if lead_id else {},
            "personalization": self.load_json_entity("personalization", lead_id) if lead_id else {},
            "company_profile": self.load_json_entity("companies", lead_id) if lead_id else {},
            "supplier_approval": self.load_json_entity("supplier_approvals", deal_id) or {},
            "lead": {
                "id": lead_id,
                "company_name": deal.get("lead_company"),
                "data": deal.get("lead_data") or {},
                "lead_score": deal.get("lead_score"),
            },
        }

    def get_supplier_detail(self, supplier_id: str) -> dict[str, Any] | None:
        supplier = self.get_supplier(supplier_id)
        if not supplier:
            return None
        data = supplier.get("data") or {}
        return {"supplier": supplier, "data": data}

    @staticmethod
    def _infer_sourcing_needs(data: dict, company: dict, deals: list) -> dict[str, Any]:
        products = company.get("products_services") or []
        if deals:
            req = deals[0].get("buyer_requirements") or {}
            if isinstance(req, str):
                try:
                    req = json.loads(req)
                except json.JSONDecodeError:
                    req = {}
            return {
                "product": req.get("product_description") or (products[0] if products else ""),
                "quantity": req.get("quantity"),
                "destination": req.get("shipping_destination"),
                "source": "active_deal",
            }
        text = data.get("website_text_preview", "")
        return {
            "product": products[0] if products else "Promotional products (from catalog)",
            "likely_needs": products,
            "summary": company.get("company_summary", ""),
            "source": "website_analysis",
        }

    def log_agent_run(
        self,
        agent_id: str,
        *,
        tenant_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        input_data: dict | None = None,
        output_data: dict | None = None,
        status: str = "success",
        duration_ms: int | None = None,
        model: str | None = None,
    ) -> str:
        run_id = str(uuid.uuid4())
        now = _utc_now()
        conn = self._connect()
        conn.execute(
            """INSERT INTO agent_runs
               (id, tenant_id, agent_id, entity_type, entity_id, input_data, output_data, status, duration_ms, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                tenant_id,
                agent_id,
                entity_type,
                entity_id,
                json.dumps(input_data or {}),
                json.dumps(output_data or {}),
                status,
                duration_ms,
                model,
                now,
            ),
        )
        conn.commit()
        return run_id

    def stats(self, tenant_id: str) -> dict[str, int]:
        conn = self._connect()
        counts = {}
        for table in ("leads", "deals", "suppliers", "rfqs", "orders", "agent_runs", "pipeline_runs"):
            if table in ("agent_runs", "pipeline_runs"):
                row = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
            else:
                row = conn.execute(
                    f"SELECT COUNT(*) as c FROM {table} WHERE tenant_id = ?", (tenant_id,)
                ).fetchone()
            counts[table] = row["c"] if row else 0
        return counts

    def create_pipeline_run(self, tenant_id: str) -> str:
        run_id = str(uuid.uuid4())
        now = _utc_now()
        stages = {s["id"]: "pending" for s in PIPELINE_STAGES}
        conn = self._connect()
        conn.execute(
            """INSERT INTO pipeline_runs
               (id, tenant_id, status, stage_status, context, created_at, updated_at)
               VALUES (?, ?, 'pending', ?, '{}', ?, ?)""",
            (run_id, tenant_id, json.dumps(stages), now, now),
        )
        conn.commit()
        return run_id

    def get_pipeline_run(self, run_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        row = conn.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["stage_status"] = json.loads(d["stage_status"] or "{}")
        d["context"] = json.loads(d["context"] or "{}")
        d["summary"] = json.loads(d["summary"]) if d.get("summary") else None
        return d

    def list_pipeline_runs(self, tenant_id: str, limit: int = 20) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM pipeline_runs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
            (tenant_id, limit),
        ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["stage_status"] = json.loads(d["stage_status"] or "{}")
            d["context"] = json.loads(d["context"] or "{}")
            d["summary"] = json.loads(d["summary"]) if d.get("summary") else None
            out.append(d)
        return out

    def update_pipeline_run(self, run_id: str, **fields: Any) -> None:
        conn = self._connect()
        now = _utc_now()
        fields["updated_at"] = now
        for key in ("stage_status", "context", "summary"):
            if key in fields and isinstance(fields[key], (dict, list)):
                fields[key] = json.dumps(fields[key])
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE pipeline_runs SET {set_clause} WHERE id = ?", (*fields.values(), run_id))
        conn.commit()

    # --- SaaS tenants ---

    def upsert_tenant(self, tenant_id: str, name: str, *, tenant_type: str = "agency") -> None:
        now = _utc_now()
        conn = self._connect()
        conn.execute(
            "INSERT OR IGNORE INTO tenants (id, name, type, created_at) VALUES (?, ?, ?, ?)",
            (tenant_id, name, tenant_type, now),
        )
        conn.execute("UPDATE tenants SET name = ? WHERE id = ?", (name, tenant_id))
        conn.commit()

    def upsert_tenant_settings(
        self,
        tenant_id: str,
        slug: str,
        *,
        plan: str = "starter",
        branding: dict | None = None,
        margin_percent: float = 15.0,
        store_enabled: bool = True,
        tagline: str | None = None,
    ) -> None:
        now = _utc_now()
        conn = self._connect()
        conn.execute(
            """INSERT INTO tenant_settings
               (tenant_id, slug, plan, branding, margin_percent, store_enabled, tagline, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id) DO UPDATE SET
                 slug=excluded.slug, plan=excluded.plan, branding=excluded.branding,
                 margin_percent=excluded.margin_percent, store_enabled=excluded.store_enabled,
                 tagline=excluded.tagline""",
            (
                tenant_id,
                slug,
                plan,
                json.dumps(branding or {}),
                margin_percent,
                1 if store_enabled else 0,
                tagline,
                now,
            ),
        )
        conn.commit()

    def get_tenant_by_slug(self, slug: str) -> dict[str, Any] | None:
        conn = self._connect()
        row = conn.execute(
            """SELECT t.id, t.name, t.type, t.created_at, ts.slug, ts.plan, ts.branding,
                      ts.margin_percent, ts.store_enabled, ts.tagline
               FROM tenant_settings ts
               JOIN tenants t ON t.id = ts.tenant_id
               WHERE ts.slug = ?""",
            (slug,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("branding"), str):
            try:
                d["branding"] = json.loads(d["branding"])
            except (json.JSONDecodeError, TypeError):
                d["branding"] = {}
        d["store_enabled"] = bool(d.get("store_enabled"))
        return d

    def get_tenant_by_id(self, tenant_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        row = conn.execute(
            """SELECT t.id, t.name, t.type, t.created_at, ts.slug, ts.plan, ts.branding,
                      ts.margin_percent, ts.store_enabled, ts.tagline
               FROM tenants t
               LEFT JOIN tenant_settings ts ON ts.tenant_id = t.id
               WHERE t.id = ?""",
            (tenant_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("branding"), str):
            try:
                d["branding"] = json.loads(d["branding"])
            except (json.JSONDecodeError, TypeError):
                d["branding"] = {}
        if d.get("store_enabled") is not None:
            d["store_enabled"] = bool(d["store_enabled"])
        return d

    def list_tenants(self) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """SELECT t.id, t.name, t.type, t.created_at, ts.slug, ts.plan, ts.branding,
                      ts.margin_percent, ts.store_enabled, ts.tagline,
                      (SELECT COUNT(*) FROM deals d WHERE d.tenant_id = t.id AND d.status != 'closed') as active_deals
               FROM tenants t
               LEFT JOIN tenant_settings ts ON ts.tenant_id = t.id
               ORDER BY t.created_at DESC"""
        ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get("branding"), str):
                try:
                    d["branding"] = json.loads(d["branding"])
                except (json.JSONDecodeError, TypeError):
                    d["branding"] = {}
            if d.get("store_enabled") is not None:
                d["store_enabled"] = bool(d["store_enabled"])
            out.append(d)
        return out

    def count_active_deals(self, tenant_id: str) -> int:
        conn = self._connect()
        row = conn.execute(
            "SELECT COUNT(*) as c FROM deals WHERE tenant_id = ? AND status != 'closed'",
            (tenant_id,),
        ).fetchone()
        return int(row["c"]) if row else 0

    # --- Product Finder Store sessions ---

    def create_store_session(self, tenant_id: str, product_query: str = "") -> str:
        session_id = str(uuid.uuid4())
        now = _utc_now()
        conn = self._connect()
        conn.execute(
            """INSERT INTO store_sessions
               (id, tenant_id, status, product_query, answers, created_at, updated_at)
               VALUES (?, ?, 'intake', ?, '{}', ?, ?)""",
            (session_id, tenant_id, product_query, now, now),
        )
        conn.commit()
        return session_id

    def get_store_session(self, session_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        row = conn.execute("SELECT * FROM store_sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for col in ("answers", "spec", "quote"):
            if isinstance(d.get(col), str):
                try:
                    d[col] = json.loads(d[col])
                except (json.JSONDecodeError, TypeError):
                    d[col] = {} if col != "quote" else None
        return d

    def update_store_session(self, session_id: str, **fields: Any) -> None:
        conn = self._connect()
        fields["updated_at"] = _utc_now()
        for key in ("answers", "spec", "quote"):
            if key in fields and isinstance(fields[key], (dict, list)):
                fields[key] = json.dumps(fields[key])
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE store_sessions SET {set_clause} WHERE id = ?", (*fields.values(), session_id))
        conn.commit()

    def upsert_tenant_user(
        self,
        tenant_id: str,
        email: str,
        password: str,
        *,
        role: str = "admin",
        name: str = "",
    ) -> str:
        import uuid

        conn = self._connect()
        now = _utc_now()
        row = conn.execute(
            "SELECT id FROM tenant_users WHERE tenant_id = ? AND email = ?",
            (tenant_id, email.lower()),
        ).fetchone()
        if row:
            uid = row["id"]
            conn.execute(
                "UPDATE tenant_users SET password=?, role=?, name=?, created_at=? WHERE id=?",
                (password, role, name, now, uid),
            )
        else:
            uid = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO tenant_users (id, tenant_id, email, password, role, name, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (uid, tenant_id, email.lower(), password, role, name, now),
            )
        conn.commit()
        return uid

    def list_tenant_users(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        conn = self._connect()
        if tenant_id:
            rows = conn.execute(
                "SELECT * FROM tenant_users WHERE tenant_id = ? ORDER BY email",
                (tenant_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT u.*, t.name as tenant_name, ts.slug as tenant_slug
                   FROM tenant_users u
                   JOIN tenants t ON t.id = u.tenant_id
                   LEFT JOIN tenant_settings ts ON ts.tenant_id = u.tenant_id
                   ORDER BY t.name, u.email"""
            ).fetchall()
        return [dict(r) for r in rows]

    def verify_tenant_user(self, email: str, password: str) -> dict[str, Any] | None:
        conn = self._connect()
        row = conn.execute(
            """SELECT u.*, t.name as tenant_name, ts.slug as tenant_slug
               FROM tenant_users u
               JOIN tenants t ON t.id = u.tenant_id
               LEFT JOIN tenant_settings ts ON ts.tenant_id = u.tenant_id
               WHERE u.email = ? AND u.password = ?""",
            (email.lower(), password),
        ).fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
