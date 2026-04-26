# Task 2: Architecture Framework

This document outlines the architecture framework for the **Intelligent Bug Report Management System**, following the IEEE 42010 standard for stakeholder identification and documenting major design decisions via ADRs.

## 1. Stakeholder Identification (IEEE 42010)

Following the IEEE 42010 standard, we have identified the key stakeholders, their concerns, and the viewpoints that address these concerns.

### 1.1 Stakeholders and Concerns

| Stakeholder | Concerns |
| :--- | :--- |
| **Project Lead / Maintainer** | System reliability, accuracy of bug assignments, ease of monitoring project health. |
| **Development Team** | Code maintainability, ease of integration with new AI models, clear separation of concerns. |
| **GitHub Contributors** | Fairness in issue assignment, visibility of their contributions, ease of finding relevant bugs. |
| **DevOps / System Admin** | Scalability of the data pipeline, security of GitHub API tokens, database performance. |
| **End Users (Report Filers)** | Speed of bug categorization, clarity on issue status, response time of the dashboard. |

### 1.2 Viewpoints and Views

*   **Logical Viewpoint**: Addresses the functional requirements and system structure.
    *   *View*: [Container Diagram (C2)](file:///home/jahnavi/Desktop/SEM8/se/mp/mp3/Intelligent-Bug-Report-Management-System/docs/c2__container_diagram.png) and [Component Diagram (C3)](file:///home/jahnavi/Desktop/SEM8/se/mp/mp3/Intelligent-Bug-Report-Management-System/docs/c3__component_diagram.png) showing how modules interact.
*   **Development Viewpoint**: Addresses the software development process and environment.
    *   *View*: Choice of FastAPI (Web), Python (Services), and MongoDB (Storage) as documented in ADR-001, ADR-003, and ADR-005.
*   **Physical Viewpoint**: Addresses the deployment and infrastructure.
    *   *View*: Deployment on Cloud infrastructure with MongoDB Atlas and Google Gemini API integration.
*   **Context Viewpoint**: Addresses how the system fits into the broader environment.
    *   *View*: [System Context Diagram (C1)](file:///home/jahnavi/Desktop/SEM8/se/mp/mp3/Intelligent-Bug-Report-Management-System/docs/c1__system_context_diagram.png) showing external integrations with GitHub and Gemini.

---

## 2. Major Design Decisions (ADRs)

The following Architecture Decision Records (ADRs) document the rationale behind significant design choices.

### ADR-001: Use of FastAPI and Uvicorn
*   **Context**: The system requires a high-performance web application framework to handle concurrent requests and provide a responsive interface.
*   **Decision**: Adopted FastAPI for rapid development and Uvicorn as the ASGI server.
*   **Rationale**: FastAPI offers automatic OpenAPI documentation, high performance, and excellent async support.
*   **Consequences**: Ensures fast response times and efficient handling of multiple requests, enhancing the user experience and system performance.
*   **Status**: Accepted

### ADR-002: Integration with GitHub API
*   **Context**: Need to fetch real-time repository data for bug tracking.
*   **Decision**: Direct integration with GitHub's REST/GraphQL API.
*   **Rationale**: Ensures data accuracy and leverages existing GitHub infrastructure for authentication and event management.
*   **Consequences**: Allows the system to provide up-to-date information, improving the accuracy and efficiency of bug tracking and issue assignment.
*   **Status**: Accepted

### ADR-003: Use of MongoDB Atlas
*   **Context**: Bug reports and contributor data are often unstructured and dynamic.
*   **Decision**: Use MongoDB Atlas as the primary document store.
*   **Rationale**: Provides the flexibility needed for evolving schemas and scales easily as data grows.
*   **Consequences**: Supports the system's need to efficiently manage large volumes of data and scale as the amount of repository information grows.
*   **Status**: Accepted

### ADR-004: Strategy Pattern for AI/ML Integration
*   **Context**: AI/ML requirements may change, or new providers (e.g., OpenAI, Anthropic) may be used in the future.
*   **Decision**: Implemented the Strategy Pattern for the `GeminiService`.
*   **Rationale**: Decouples the core logic from specific API implementations, allowing for easy hot-swapping of AI providers.
*   **Consequences**: This pattern provides flexibility and adaptability, enabling the system to integrate with various AI/ML providers as needed without major refactors.
*   **Status**: Accepted

### ADR-005: Layered Architecture Pattern
*   **Context**: Maintaining a monolithic script would hinder scalability and testing.
*   **Decision**: Organized the system into logical layers: Web UI, Service Layer, and External Integration Layer.
*   **Rationale**: Improves maintainability, testability, and allows developers to work on features independently.
*   **Consequences**: Enhances maintainability and scalability, allowing for easier updates and modifications to the system components.
*   **Status**: Accepted

### ADR-006: Event-Driven Synchronization
*   **Context**: Data fetching from GitHub is time-consuming; the UI shouldn't block.
*   **Decision**: Use an event-driven mechanism to notify the system when sync completes.
*   **Rationale**: Ensures a responsive user experience by decoupling data ingestion from UI rendering.
*   **Consequences**: Ensures timely updates and seamless integration with other system components, improving overall system responsiveness.
*   **Status**: Accepted
