# QueryML

**Agentic analytics powered by semantic models.**

QueryML combines a YAML-based semantic modeling language (`.qml` files) with an AI agent that autonomously investigates data. Define your data model → AI reasons through it → users ask questions in chat → agent investigates and returns insights.

## Why QueryML?

Traditional BI dashboards answer questions you've already thought to ask. QueryML's agent *investigates* — it queries, interprets results against benchmarks, drills deeper into anomalies, and synthesizes findings like a senior analyst would.

The key insight: **a semantic layer designed for AI agents enables autonomous data investigation that raw SQL agents cannot achieve.** The agent never writes SQL. It requests data through a governed semantic model that provides the vocabulary, guardrails, and context the agent needs to reason effectively.

## How It Works

```
┌─────────────────────────────────────────────────┐
│                  CHAINLIT UI                     │
│        (Project selector → Chat interface)       │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│                AGENT LAYER                       │
│  (Multi-step investigation, tool orchestration)  │
│  LLM: Amazon Nova Pro via AWS Bedrock            │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│             SEMANTIC LAYER                       │
│  (.qml YAML files → parsed into Python objects)  │
│  Generates governed SQL from semantic model      │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│               DATABASE                           │
│           DuckDB (local .db file)                │
└─────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Clone and install
git clone <repo-url>
cd queryml
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Set up AWS credentials
cp .env.example .env
# Edit .env with your AWS Bedrock credentials

# Seed the example database
python projects/ecommerce/seed_data.py

# Run the app
chainlit run app.py
```

## The .qml Format

`.qml` files are YAML that define your semantic model — sources, dimensions, measures, datasets, and projects:

```yaml
version: "1.0"
connection: duckdb:///data/analytics.db

sources:
  orders:
    table: orders
    description: Customer orders
    dimensions:
      region:
        type: string
        hint: Compare geographic performance
    measures:
      total_revenue:
        type: sum
        column: revenue
        context: "Monthly benchmark is ~$50K"
      return_rate:
        type: ratio
        numerator: is_returned
        denominator: order_count_raw
        context: "Healthy is below 8%"

datasets:
  sales_overview:
    source: orders
    joins:
      products:
        on: "orders.product_id = products.product_id"

projects:
  my_project:
    label: Sales Analytics
    datasets: [sales_overview]
    system_context: |
      You are an expert analyst...
```

**Key features:**
- `hint` tells the agent *when* to use a field
- `context` tells the agent *how to interpret* results (benchmarks, thresholds)
- `ratio` measures automatically return numerator + denominator for explainability
- The agent never writes SQL — it requests dimensions and measures, and the engine generates governed queries

## Example Interaction

```
User: Why is our return rate high?

[Step 1: 🔍 Listing available datasets...]
[Step 2: 🔍 Describing sales_overview — 10 dimensions, 4 measures]
[Step 3: 📊 Querying return_rate by region]
[Step 4: 🔍 Getting context for return_rate benchmark]
[Step 5: 📊 Drilling into South region by category]
[Step 6: 💡 Synthesizing findings...]

Agent: Here's what I found:

**The South region is driving the high return rate.**
- Overall return rate is 11.2%, above the 8% healthy benchmark
- South region: 16.3% return rate (vs 8-9% in other regions)
- Within South, Electronics has a 22% return rate
- Recommendation: Investigate Electronics fulfillment in the South region
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| Database | DuckDB |
| LLM | Amazon Nova Pro (AWS Bedrock) |
| UI | Chainlit |
| Semantic Model | Custom YAML parser (PyYAML + Pydantic) |

## Project Structure

```
queryml/
├── app.py                    # Chainlit entry point
├── queryml/
│   ├── semantic/
│   │   ├── models.py         # Pydantic models
│   │   ├── parser.py         # .qml YAML parser
│   │   └── sql_generator.py  # Governed SQL generation
│   ├── agent/
│   │   ├── bedrock.py        # Amazon Nova client
│   │   ├── tools.py          # Agent tool definitions
│   │   └── orchestrator.py   # Investigation loop
│   └── engine/
│       └── duckdb_engine.py  # DuckDB connection
├── projects/
│   └── ecommerce/            # Example project
│       ├── schema.qml
│       └── data/
└── tests/
```

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

## License

MIT
