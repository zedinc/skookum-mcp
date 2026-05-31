# Skookum MCP

> Because AI agents shouldn't fabricobble physics.

**Skookum MCP** (`skookum-mcp`) is an RCE-secure (AST-sandboxed), mathematically precise, and self-contained physical unit conversion server and algebraic dimensional calculator. Built from the ground up for LLM agent pipelines, it acts as a headless, deterministic physical units co-processor (MCP server) equipped with an interactive companion playground for developer validation.

---

## Why Skookum MCP?

When building AI agent tools or web-based scientific calculators, standard libraries and LLMs suffer from severe security, mathematical, and dimensional shortcomings.

| Physical Challenge | Traditional Engines / LLM Reasoning | Skookum MCP |
| :--- | :--- | :--- |
| **Algebraic Expressions** | Require complex manual parsing or unsafe `eval()` executions. LLMs frequently hallucinate intermediate units during multi-step derivations. | **Safe AST-Based Sandbox**: Safely parses and evaluates natural physical expressions (e.g., `10m/s * 5s` or `(30degC - 10degC) + 5delta_degC`) with whitelisted nodes and zero `eval()`. |
| **Mathematical Precision** | Floating-point conversion factors introduce rounding errors and accumulation drift, especially in division or reciprocal conversions. | **Exact SymPy Rational Engine**: Computes all calculations internally using exact rational fractions, preserving perfect mathematical identity. |
| **Dimensional Violations** | Standard math engines allow physically impossible additions (e.g., `10 kg + 5 m`) or invalid temperature scaling without warning. | **Algebraic Exponent Vectors**: Strict compile-time generics and run-time cardinalities block dimensional mismatches and enforce strict physical bounds. |
| **Agent Integration** | AI agents must construct custom tools, struggle to format inputs, and have no standard protocol to check formula consistency in technical texts. | **First-Class MCP Support**: Exposes standardized tools, dynamic unit resources, and engineering validation prompts out-of-the-box. |

---

## Key Features

1. **AST-Based Parser Sandbox (`src/parser.py`)**:
   * **Why**: To prevent Remote Code Execution (RCE) and code injection when evaluating user-provided expressions in agent workflows, Skookum MCP completely avoids dangerous `eval()` blocks.
   * **How**: It parses input strings into an Abstract Syntax Tree (AST), runs them through a strict, whitelisted `NodeVisitor` that blocks unauthorized operations and private attribute access (`_`), and safely processes natural engineering shorthand (e.g., implicit multiplications like `10m`, division synonyms like `per`, and percentage signs like `%`).

2. **Static Type-Checking & Physical Safety Guards (`src/types.py`)**:
   * **Why**: To ensure physical operations are dimensionally sound at both development time (static checking) and runtime (dynamic computation).
   * **How**: Pairs semantic generic type tags (e.g., `Length`, `Mass`, `Force`, `Energy`) with Python generic type hints for IDE-level verification. At runtime, strict coordinate algebra automatically prevents nonsense computations (like adding two incompatible dimensions or scaling absolute values), while allowing physical coordinate differences to work invisibly in the background.

3. **Generalized Reciprocal Inversions (`src/engine.py`)**:
   * **Why**: To cleanly translate inversely related units without requiring manual mathematical transformations.
   * **How**: Algebraically detects and routes reciprocal physics relationships (e.g., fuel efficiency in Miles Per Gallon vs. fuel consumption in Liters per 100 Kilometers) through an inverse dimensional solver.

4. **Premium Interactive Playground (`src/dashboard/`)**:
   * **Why**: To provide an outstanding visual sandbox for testing computations and inspecting fractional steps.
   * **How**: A neon glassmorphic dark-mode web interface served by standard library `http.server`. Includes a live unit injector palette, fractional/decimal step viewer, and local-storage computation history.

---

## Core Computational Examples

Skookum MCP evaluates physical equations algebraically across common physical units and derived dimensions:

### 1. Mechanics & Kinematics
*   **Expression**: `10 m/s * 5 s`
*   **Target Unit**: `ft`
*   **Result**: `164.04199 ft` (Exact rational: `16404199/100000`)

### 2. Energy & Power
*   **Expression**: `500 W * 2 hr`
*   **Target Unit**: `MJ`
*   **Result**: `3.6 MJ` (Exact rational: `18/5`)

### 3. Reciprocal Fuel Consumption
*   **Expression**: `30 mpg`
*   **Target Unit**: `l/100km`
*   **Result**: `7.840487 l/100km` (Exact rational: `2352145833/300000000`)

### 4. Infeasible/Error Example (Safety Guards)
When asked to perform physically impossible calculations, the engine elegantly blocks execution and returns clear, educational errors:
*   **Expression**: `10 kg + 5 m` (Dimensional Mismatch)
    *   *Result*: `Type Error: Dimensional Mismatch: Cannot add incompatible dimensions`
*   **Expression**: `30 degC + 10 degC` (Physical violation: coordinate addition is invalid)
    *   *Result*: `Type Error: Nonsense: Cannot add two absolute temperatures`

---

## Agentic Interface (MCP)

Skookum MCP exposes three first-class capabilities to AI agents under the Model Context Protocol:

### 1. The Tool: `dimensional_compute`
Let the agent safely evaluate physics formulas and target conversions.
*   **Request**:
    ```json
    {
      "method": "tools/call",
      "params": {
        "name": "dimensional_compute",
        "arguments": {
          "expression": "(100 kg * 9.8 m/s**2) * 5 m",
          "target_unit": "kJ"
        }
      }
    }
    ```
*   **Response**:
    ```json
    {
      "content": [
        {
          "type": "text",
          "text": "Result: 49/10 kJ (approx. 4.9 kJ)"
        }
      ]
    }
    ```

### 2. The Resource: `units://supported`
Exposes the physical dimension catalog to guide the LLM's inputs dynamically and prevent formatting hallucinations.
*   **URI**: `units://supported`
*   **Returns**: A structured JSON mapping categories (length, force, energy, power, pressure, absolute/delta temperatures) to their canonical names.

### 3. The Prompt: `verify_dimensional_consistency`
A workflow template instructing the LLM to scan technical reports, extract physical formulas, and call the computational tool to verify their mathematical correctness.

---

## Documentation Directory

To navigate the technical specifications and architecture of Skookum MCP:

*   **[CONTEXT.md](./CONTEXT.md)**: The core **Domain Glossary** defining key semantic concepts (Dimension, Cardinality, Unit, Quantity, Converter, Co-processor, AST Sandbox).
*   **[docs/architecture.md](./docs/architecture.md)**: The **System Design Reference** mapping the step-by-step pipeline execution, AST sandbox whitelists, preprocessor translation grammar, and conversion logic calculations.
*   **[docs/issues.md](./docs/issues.md)**: The **Active Issues Log & Roadmap** detailing planned transitions, caret bitwise operator compatibilities, long-term Pint decoupling plans, and linking active product specifications.
*   **[docs/adr/](./docs/adr/)**: The **Architectural Decision Records (ADRs)** cataloging foundational engineering decisions and trade-offs (e.g. [ADR 0001](./docs/adr/0001-decouple-quantity-value-from-conversion-engine.md), [ADR 0002](./docs/adr/0002-represent-dimensions-statically-and-cardinalities-algebraically.md), and [ADR 0003](./docs/adr/0003-use-preprocessor-normalization-for-unicode-symbol-support.md)).

---

## Installation & Setup

Manage project dependencies easily with `uv`:

```bash
# Sync dependencies and build the editable package
uv sync
```

### Adding to Google Antigravity SDK

To integrate `skookum-mcp` as an external local Stdio tool within a Google Antigravity agent configuration:

```python
from google.antigravity import Agent, LocalAgentConfig, types

# Register the local MCP server process in Stdio mode
mcp_servers = [
    types.McpStdioServer(
        command="uv",
        args=[
            "--directory",
            "/absolute/path/to/skookum-mcp",
            "run",
            "skookum-mcp"
        ]
    )
]

config = LocalAgentConfig(mcp_servers=mcp_servers)

async with Agent(config) as agent:
    response = await agent.chat("Evaluate (100 kg * 9.8 m/s**2) * 5 m to kJ")
    print(await response.text())
```

### Adding to Claude Desktop

Add the server to your Claude Desktop configuration file (typically `~/.config/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "skookum-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/skookum-mcp",
        "run",
        "skookum-mcp"
      ]
    }
  }
}
```

### Adding to Cursor

1. Go to **Settings** -> **Features** -> **MCP**.
2. Click **+ Add New MCP Server**.
3. Fill in:
   * **Name**: `skookum-mcp`
   * **Type**: `command`
   * **Command**: `uv --directory /absolute/path/to/skookum-mcp run skookum-mcp`

---

## Running the Web Dashboard

Launch the responsive glassmorphic mathematical dashboard served by standard library `http.server`:

```bash
uv run skookum-dashboard
```
*The server automatically resolves occupied ports, defaulting to port `8000` (or the next available socket port).*

---

## Running the Test Suite

We maintain a strict **100% statement and branch coverage** across all modules with **147 tests**:

```bash
# Run the complete test suite with coverage report
.venv/bin/pytest
```
