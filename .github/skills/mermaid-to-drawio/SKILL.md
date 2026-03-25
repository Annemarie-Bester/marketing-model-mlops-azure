---
name: mermaid-to-drawio
description: "Convert Mermaid diagrams to draw.io (diagrams.net) XML. Use when: user has a Mermaid diagram to convert, needs architecture diagrams for documentation, wants draw.io XML output, needs version-controlled diagrams, asks to convert flowchart/sequence/architecture/class/ER/state/gantt from Mermaid to drawio format."
argument-hint: "Paste or reference a Mermaid diagram to convert to draw.io XML"
---

# Mermaid → draw.io Converter

Convert Mermaid diagrams into clean, structured draw.io XML files suitable for professional architecture documentation and GitHub version control.

## When to Use

- Converting **any** Mermaid diagram type to draw.io format, including:
  - Flowchart / Graph
  - Sequence diagram
  - Class diagram
  - Entity-Relationship (ER) diagram
  - State diagram
  - Gantt chart
  - Architecture / deployment diagrams
- Producing `.drawio` files for project documentation
- Replacing Mermaid code blocks with editable, visual diagrams
- Creating version-controlled architecture diagrams

## Conversion Principles

### Preserve Meaning, Not Syntax

Do NOT perform a direct 1:1 syntax translation. Instead:

1. **Interpret** the architecture and relationships in the Mermaid source
2. **Identify** components, data flows, and logical groupings
3. **Reconstruct** using proper draw.io diagram structure with improved layout

### Improve Layout and Readability

- Use logical flow direction: Left → Right OR Top → Bottom
- Group related components into containers/swimlanes:
  - CI/CD pipeline stages
  - Training / Inference paths
  - Storage / Data layer
  - Monitoring / Governance
- Avoid crossing lines, clutter, and unstructured placement
- Space elements consistently (use grid-aligned coordinates)

### Colour Palette

Apply a consistent colour scheme across all diagrams. Assign fill colours by component category:

| Category | Fill Colour | Hex | Border Hex | Usage |
|---|---|---|---|---|
| Compute / Services | Light blue | `#dae8fc` | `#6c8ebf` | AKS, VMs, APIs, containers |
| Storage / Data | Light orange | `#fff2cc` | `#d6b656` | Blob Storage, databases, data lakes |
| CI/CD / DevOps | Light green | `#d5e8d4` | `#82b366` | Pipelines, DevOps, GitHub Actions |
| Monitoring / Governance | Light purple | `#e1d5e7` | `#9673a6` | Logging, alerts, model registry |
| External / User | Light grey | `#f5f5f5` | `#666666` | Users, external systems, triggers |
| Decision / Gate | Light red | `#f8cecc` | `#b85450` | Approvals, quality gates, decisions |

Apply colours via the `fillColor` and `strokeColor` style properties. Example:
```
style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
```

### Service Icons

When a node represents a known service or technology, place a **small icon in the top-right corner** of the shape using draw.io's built-in icon libraries:

- Use `image=` in the style to overlay an icon, or place a small `mxCell` image anchored to the parent node
- Prefer draw.io's bundled shape libraries: **Azure** (`shape=mxgraph.azure.*`), **AWS** (`shape=mxgraph.aws4.*`), **GCP**, **Kubernetes**, **Docker**
- Icon should be 24×24 px, positioned at top-right (offset `x=width-28, y=4`)
- If no matching built-in icon exists, omit the icon — do NOT use external URLs

Example icon overlay inside a node:
```xml
<mxCell id="icon_1" value="" style="shape=mxgraph.azure.kubernetes_services;aspect=fixed;" vertex="1" parent="NODE_ID">
  <mxGeometry x="128" y="4" width="24" height="24" as="geometry" />
</mxCell>
```

### Map Elements to draw.io Shapes

| Mermaid Element | draw.io Shape | Style Hint |
|---|---|---|
| Process / Task | Rectangle | `rounded=1` for services |
| Storage / Database | Cylinder | `shape=cylinder3` |
| Pipeline / Flow | Directed arrow | `edgeStyle=orthogonalEdgeStyle` |
| External system | Bordered container | `dashed=1` |
| Grouping / Subgraph | Swimlane or container | `swimlane` or `container=1` |
| Decision | Diamond | `rhombus` |
| Start / End | Rounded rectangle | `ellipse` for terminals |
| Class (UML) | UML class box | `shape=mxgraph.uml25.class` |
| Entity (ER) | Rectangle with divider | `shape=table` or header row |
| State | Rounded rectangle | `rounded=1;arcSize=40` |
| Gantt task | Horizontal bar | Rectangle with proportional width |

### Azure-Aware Visual Language

When the diagram references Azure services:

- Label services clearly (e.g., "AKS Cluster", "Blob Storage", "Azure DevOps")
- Use the draw.io built-in Azure shape library for service icons (top-right corner of node)
- Apply the compute/blue palette for Azure services by default
- Keep diagrams portable — icons are optional decoration, labels carry the meaning

### Single-Page Default

Always produce a **single-page diagram** unless the user explicitly requests multiple pages. If the diagram is large, increase the `pageWidth` / `pageHeight` in the `mxGraphModel` rather than splitting across pages.

## Procedure

### Step 1 — Analyse the Mermaid Source

Parse the Mermaid diagram to extract:

- **Nodes**: id, label, shape type
- **Edges**: source, target, label, direction
- **Subgraphs**: grouping name, contained nodes
- **Flow direction**: TB, LR, RL, BT
- **Diagram type**: flowchart, sequence, class, ER, state, gantt, or architecture

### Step 2 — Plan the Layout

1. Identify logical groupings (subgraphs, related nodes)
2. Choose primary flow direction (prefer LR for pipelines, TB for hierarchies)
3. Assign grid positions — use 200px spacing horizontally, 100px vertically
4. Place containers first, then nodes within them

### Step 3 — Generate draw.io XML

Produce valid `.drawio` XML using this skeleton:

```xml
<mxfile host="app.diagrams.net" modified="YYYY-MM-DDTHH:MM:SS.000Z" agent="" version="24.0.0" type="device">
  <diagram id="DIAGRAM_ID" name="Page-1">
    <mxGraphModel dx="1422" dy="762" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1169" pageHeight="827" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <!-- Containers, nodes, and edges here -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

**Node template:**
```xml
<mxCell id="NODE_ID" value="Label" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="1">
  <mxGeometry x="X" y="Y" width="160" height="60" as="geometry" />
</mxCell>
```

**Edge template:**
```xml
<mxCell id="EDGE_ID" value="label" style="edgeStyle=orthogonalEdgeStyle;rounded=0;" edge="1" source="SOURCE_ID" target="TARGET_ID" parent="1">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

**Container template:**
```xml
<mxCell id="CONTAINER_ID" value="Group Name" style="swimlane;startSize=30;container=1;" vertex="1" parent="1">
  <mxGeometry x="X" y="Y" width="W" height="H" as="geometry" />
</mxCell>
```

### Step 4 — Validate

- Confirm all Mermaid nodes appear in the output
- Confirm all edges are preserved with correct source/target
- Check that no `id` values are duplicated
- Verify XML is well-formed (no unclosed tags)

### Step 5 — Save and Describe

1. Save the file to `docs/diagrams/<diagram_name>.drawio`
2. Create the `docs/diagrams/` directory if it does not exist
3. Provide a brief description of what the diagram represents and its key flows

## Output Checklist

- [ ] Valid `.drawio` XML — opens without error in diagrams.net
- [ ] All nodes and edges from Mermaid source are represented
- [ ] Logical grouping via containers or swimlanes
- [ ] Clean layout with no crossing lines where avoidable
- [ ] Grid-aligned coordinates for consistent spacing
- [ ] Consistent colour palette applied (see Colour Palette table)
- [ ] Service icons placed top-right where applicable
- [ ] Single page (unless user requested multi-page)
- [ ] File saved as XML (not binary) for Git diff-friendliness
- [ ] File placed in `docs/diagrams/` with descriptive name

## What NOT to Do

- Do NOT output Mermaid syntax in the result
- Do NOT produce auto-converted low-quality layouts — redesign for clarity
- Do NOT create cluttered diagrams with overlapping elements
- Do NOT ignore subgraph groupings from the source
- Do NOT use binary export formats — always XML
- Do NOT hardcode external icon URLs — only use draw.io built-in shape libraries
- Do NOT split into multiple pages unless explicitly asked
- Do NOT use inconsistent colours — always follow the palette table
