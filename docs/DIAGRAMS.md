# Architecture Diagrams

This document describes all the visual diagrams available for the Konflux DevLake MCP Server.

## Available Diagrams

### 1. System Architecture Diagram
**File**: `architecture-diagram.mmd`
**Purpose**: Complete system overview showing all components and their relationships

**Shows**:
- Client layer (Users/AI Assistants)
- Transport layer (HTTP and STDIO)
- Core MCP server components
- Tools system with all modules
- Security layer components
- Database connection layer
- DevLake MySQL database

**Best For**: Understanding the overall system architecture

---

### 2. Natural Language Processing Flow
**File**: `natural-language-flow.mmd`
**Purpose**: Visualize how natural language queries transform into SQL

**Shows**:
- User query input
- AI agent analysis
- Intent extraction
- SQL query generation
- Security validation
- Query execution
- Data masking
- Result formatting

**Best For**: Understanding the NL-to-SQL transformation process

---

### 3. Data Flow Sequence Diagram
**File**: `data-flow-diagram.mmd`
**Purpose**: Detailed sequence of request/response interactions

**Shows**:
- Request flow through all layers
- Component interactions in sequence
- Security validation steps
- Error handling paths
- Response flow back to user

**Best For**: Understanding the exact execution flow and debugging

---

### 4. Security Architecture
**File**: `security-architecture.mmd`
**Purpose**: Security validation layers and checks

**Shows**:
- Multiple security layers
- SQL injection detection
- Query validation logic
- Blocking mechanisms
- Data masking pipeline

**Best For**: Security reviews and understanding protection mechanisms

---

### 5. Deployment Architecture
**File**: `deployment-architecture.mmd`
**Purpose**: Kubernetes deployment structure

**Shows**:
- Kubernetes cluster structure
- Pod, Service, Route configuration
- ConfigMap and Secret integration
- ServiceAccount and RBAC
- External database connection
- Client access patterns

**Best For**: Deployment planning and infrastructure understanding

---

### 6. Tools Architecture
**File**: `tools-architecture.mmd`
**Purpose**: Tool system organization and module relationships

**Shows**:
- Tools Manager central coordinator
- Database, Incident, and Deployment tool modules
- Base tool interface hierarchy
- Individual tool capabilities

**Best For**: Understanding extensibility and tool development

---

## How to View Diagrams

### In GitHub/GitLab
These diagrams automatically render in README files when you commit them. Just view the `.mmd` files on GitHub/GitLab.

### In VS Code
1. Install "Markdown Preview Mermaid Support" extension
2. Open any `.mmd` file
3. Press `Cmd+Shift+V` (Mac) or `Ctrl+Shift+V` (Windows/Linux) to preview

### Online
1. Visit [Mermaid Live Editor](https://mermaid.live/)
2. Copy the content of any `.mmd` file
3. Paste into the editor
4. View, edit, or export as PNG/SVG

### Generate PNG Images
```bash
# Install mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# Generate all diagrams
cd docs
for file in *.mmd; do
  mmdc -i "$file" -o "images/${file%.mmd}.png"
done
```

## Diagram Formats

All diagrams use [Mermaid](https://mermaid.js.org/) format:
- **Text-based**: Easy to version control
- **Self-describing**: Readable in plain text
- **Multiple outputs**: PNG, SVG, PDF exports
- **Interactive**: View in web-based tools

## Contributing New Diagrams

When adding new diagrams:

1. Create `.mmd` file in `docs/` directory
2. Use descriptive filename
3. Add to this index
4. Update `docs/README.md`
5. Consider generating PNG for documentation

## Legend / Color Codes

Diagrams use consistent color coding:
- 🔵 Blue: User-facing components
- 🟡 Yellow: Core application logic
- 🟢 Green: Tools and modules
- 🔴 Red: Security and blocking
- 🟣 Purple: External services/databases

---

**Last Updated**: October 2025
