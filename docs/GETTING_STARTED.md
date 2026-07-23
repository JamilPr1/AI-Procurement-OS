# Getting Started

## 1. Install Ollama

Download from [ollama.com](https://ollama.com). Then:

```bash
ollama pull llama3.2
```

Edit `brain/config.yaml` if you use a different model:

```yaml
llm:
  model: "your-model-name"
```

## 2. Python Environment

```powershell
cd d:\Trading
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 3. First Run

```powershell
python -m src.main status
```

Expected output:
- 14 agents loaded
- 1 workflow loaded
- LLM health (ok if Ollama is running)
- Empty data stats (fresh install)

## 4. Explore the Pipeline

```powershell
python -m src.main pipeline
```

This shows the full buyer-to-delivery flow with human gates marked.

## 5. Test an Agent

Qualification example:

```powershell
python -m src.main run qualification -i "Hi, we need 5000 insulated tumblers, 304 stainless, black with laser logo, individual boxes, delivered to Chicago by end of August"
```

Check logs after run:

```
logs/agents/agents.log
logs/changes/changes.log
```

## 6. Customize the Brain

| Want to change... | Edit this file |
|-------------------|----------------|
| Target vertical / buyers | `brain/config.yaml` |
| Agent behavior | `brain/prompts/<agent>.md` |
| When humans must approve | `brain/policies/human_gate.yaml` |
| Pipeline order | `brain/workflows/buyer_to_delivery.yaml` |
| Margin % | `brain/config.yaml` → `agency.default_margin_percent` |

## 7. Data Layout

Runtime data lives in `data/` (gitignored):

```
data/
  platform.db      SQLite — leads, deals, orders, agent_runs
  leads/           JSON snapshots per lead
  suppliers/       JSON per supplier
  rfqs/            JSON per RFQ
  proposals/       JSON per proposal
  orders/          JSON per order
```

## 8. Phase 1 Workflow (Manual + AI)

1. Add leads manually or via CSV → run `lead_discovery` agent to score
2. Run `company_research` + `personalization` for top leads
3. Review outreach drafts (human sends in Phase 1)
4. When buyer replies → run `qualification` agent
5. Continue pipeline: product_research → supplier_discovery → ...

## Troubleshooting

**Ollama connection error**
- Ensure Ollama is running: `ollama serve`
- Check `brain/config.yaml` → `llm.base_url`

**Model not found**
- Run `ollama list` and update `llm.model` in config

**Agent returns parse error**
- Some models struggle with JSON; try a larger model or lower temperature
