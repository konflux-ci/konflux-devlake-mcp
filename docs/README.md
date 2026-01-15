# Konflux DevLake MCP Server - Documentation

Welcome to the comprehensive documentation for the Konflux DevLake MCP Server.

## Documentation Index

### Core Documentation

- **[Architecture Documentation](./ARCHITECTURE.md)** - Complete system architecture, components, and design patterns
- **[Main README](../README.md)** - Quick start guide and usage instructions

### Architecture Diagrams

All diagrams are in Mermaid format and can be viewed in any Mermaid-compatible viewer (GitHub, GitLab, VS Code extensions, etc.)

#### Visual Diagrams:

1. **[System Architecture](./architecture-diagram.mmd)**
   - Complete system overview
   - Component relationships
   - Data flow between layers

2. **[Natural Language Flow](./natural-language-flow.mmd)**
   - Natural language to SQL transformation process
   - User query to result flow
   - Query generation steps

3. **[Data Flow Sequence](./data-flow-diagram.mmd)**
   - Detailed request/response sequence
   - Component interactions
   - Error handling flow

4. **[Security Architecture](./security-architecture.mmd)**
   - OIDC authentication layer
   - Security layers and checks
   - SQL injection prevention
   - Data masking pipeline

5. **[Deployment Architecture](./deployment-architecture.mmd)**
   - Kubernetes deployment structure
   - Network configuration
   - External service integration

6. **[Tools Architecture](./tools-architecture.mmd)**
   - Tool system organization
   - Module relationships
   - Available tools

### Quality Reports

- **[Retest Analysis Prompt](./.prompts/quality_reports/retest_average.md)** - Prompt template for analyzing PR retest patterns
- **PR Retest Analysis Tool**: Comprehensive tool for analyzing pull requests that required manual retest commands, with project/repository filtering, pattern analysis, and actionable recommendations

## Viewing Diagrams

### Option 1: GitHub/GitLab
- Mermaid diagrams are automatically rendered in README files
- Just commit these `.mmd` files and view on GitHub

### Option 2: VS Code Extension
- Install "Markdown Preview Mermaid Support" extension
- Open any `.mmd` file or documentation

### Option 3: Online Viewer
- Visit [Mermaid Live Editor](https://mermaid.live/)
- Copy/paste the diagram content
- View and export as image

### Option 4: Command Line
```bash
# Install mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# Generate PNG images
mmdc -i docs/architecture-diagram.mmd -o docs/images/architecture-diagram.png
mmdc -i docs/natural-language-flow.mmd -o docs/images/natural-language-flow.png
mmdc -i docs/data-flow-diagram.mmd -o docs/images/data-flow-diagram.png
```

## Diagram Catalog

### System Architecture
- **Purpose**: Overall system design
- **Audience**: Architects, Developers
- **File**: `architecture-diagram.mmd`

### Natural Language Processing
- **Purpose**: Query transformation flow
- **Audience**: End users, AI developers
- **File**: `natural-language-flow.mmd`

### Request/Response Flow
- **Purpose**: Detailed component interactions
- **Audience**: Developers, DevOps
- **File**: `data-flow-diagram.mmd`

### Security Model
- **Purpose**: OIDC authentication and security validation layers
- **Audience**: Security team, Developers
- **File**: `security-architecture.mmd`

### Deployment Topology
- **Purpose**: Kubernetes deployment structure
- **Audience**: DevOps, SRE
- **File**: `deployment-architecture.mmd`

### Tools System
- **Purpose**: Tool module organization
- **Audience**: Developers
- **File**: `tools-architecture.mmd`

## Quick Start

1. **New to the project?** Start with the [Main README](../README.md)
2. **Want to understand the architecture?** Read [ARCHITECTURE.md](./ARCHITECTURE.md)
3. **Need visual reference?** View the diagrams above
4. **Want to extend functionality?** See "Extension Points" in ARCHITECTURE.md
5. **Deploying to production?** Check the deployment diagrams

## Contributing

When adding new documentation:

1. **Architecture changes**: Update diagrams in `docs/`
2. **New features**: Add diagram to visualize
3. **API changes**: Update architecture docs
4. **Security updates**: Update security diagrams

## Diagram Format

All diagrams use [Mermaid](https://mermaid.js.org/) syntax, which provides:
- Text-based diagram definitions (version control friendly)
- Automatic rendering on GitHub/GitLab
- Multiple export formats (PNG, SVG, PDF)
- Interactive diagrams in web viewers

## External Links

- [Mermaid Documentation](https://mermaid.js.org/intro/)
- [Mermaid Live Editor](https://mermaid.live/)
- [Main Project Repository](../)

---

**Last Updated**: January 2026
**Maintained By**: Konflux DevLake MCP Team
