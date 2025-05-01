# Local Knowledge Programmer's Manual

## Introduction

This manual provides comprehensive documentation for developers working with the Local Knowledge system. It covers all major modules, their functionality, and how to maintain and extend them.

## Table of Contents

### Core Modules

1. [Database Module](database.md)
2. [AI Module](ai.md)
3. [Text Processing Module](textprocessing.md)
4. [UI Module](ui.md)

### Data Sources

1. [MedRxiv Module](medrxiv.md)
2. [PubMed Module](pubmed.md)

### Advanced Features

1. [Embeddings](embeddings.md)
2. [Multi-Embeddings](multiembeddings.md)
3. [QA Embeddings](qaembeddings.md)
4. [Keywords Extraction](keywords.md)
5. [Chunking](chunking.md)
6. [Bookmarking System](bookmarks.md)
7. [Project Management](project_management.md)
8. [Hypotheses and Research Questions](hypotheses_and_questions.md)

### Development

1. [Setting Up Development Environment](development-setup.md)
2. [Testing](testing.md)
3. [Contributing Guidelines](contributing.md)

## Getting Started

If you're new to the Local Knowledge system, we recommend starting with the [Database Module](database.md) documentation to understand the core data structures, followed by the [AI Module](ai.md) to learn about the AI capabilities of the system.

For those interested in extending the system with new data sources, the [MedRxiv Module](medrxiv.md) and [PubMed Module](pubmed.md) provide good examples of how to integrate external data sources.

## System Architecture

The Local Knowledge system is designed with a modular architecture:

- **Database Layer**: Handles data storage and retrieval
- **AI Layer**: Provides AI capabilities like embeddings and QA generation
- **Text Processing Layer**: Processes text for analysis and search
- **UI Layer**: Provides user interfaces for interacting with the system
- **Data Source Layers**: Integrate with external data sources

Each module is designed to be independent but interoperable, allowing for easy extension and maintenance.
