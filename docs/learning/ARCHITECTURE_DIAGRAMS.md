# Visual Architecture Guide: FinCLI

Visual diagrams and concept maps to understand the system architecture and AI engineering concepts.

---

## 🏗️ System Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "User Interface Layer"
        CLI[CLI - Typer]
        API[REST API - FastAPI]
    end
    
    subgraph "Business Logic Layer"
        TE[Transaction Extractor]
        AN[Analytics Engine]
        CH[Chat Handler]
    end
    
    subgraph "AI/ML Layer"
        LR[LLM Router]
        PM[Prompt Manager]
        CA[Cache Layer]
    end
    
    subgraph "Infrastructure Layer"
        GM[Gmail Client]
        DB[(Database)]
        LC1[Ollama Client]
        LC2[Anthropic Client]
        LC3[OpenAI Client]
        LC4[Bedrock Client]
    end
    
    subgraph "Cross-Cutting Concerns"
        OB[Observability]
        LG[Logging]
        CF[Configuration]
    end
    
    CLI --> TE
    CLI --> AN
    CLI --> CH
    API --> TE
    API --> AN
    API --> CH
    
    TE --> LR
    AN --> LR
    CH --> LR
    
    LR --> PM
    LR --> CA
    
    LR --> LC1
    LR --> LC2
    LR --> LC3
    LR --> LC4
    
    TE --> GM
    TE --> DB
    AN --> DB
    
    LR --> OB
    TE --> OB
    
    OB --> LG
    CF --> LR
    CF --> GM
```

---

## 🔄 Data Flow Diagram

### Transaction Extraction Flow

```mermaid
sequenceDiagram
    participant U as User
    participant CLI as CLI
    participant TE as TransactionExtractor
    participant LR as LLM Router
    participant CA as Cache
    participant LC as LLM Client
    participant OB as Observability
    participant DB as Database
    
    U->>CLI: fetch --max 20
    CLI->>TE: extract_batch(emails)
    
    loop For each email
        TE->>LR: extract_json(email_text)
        LR->>CA: check_cache(key)
        
        alt Cache Hit
            CA-->>LR: cached_response
            LR->>OB: record_cache_hit()
        else Cache Miss
            CA-->>LR: None
            LR->>LC: generate_text(prompt)
            LC-->>LR: response
            LR->>CA: store(key, response)
            LR->>OB: record_metrics()
        end
        
        LR-->>TE: extracted_data
        TE->>TE: validate_and_clean()
        TE->>DB: save_transaction()
    end
    
    TE-->>CLI: results
    CLI-->>U: Display summary
```

---

## 🧩 Component Relationships

### LLM Client Architecture

```mermaid
classDiagram
    class BaseLLMClient {
        <<abstract>>
        +generate_text()*
        +extract_json()*
        +health_check()*
    }
    
    class OllamaClient {
        -base_url: str
        -model_name: str
        +generate_text()
        +extract_json()
    }
    
    class AnthropicClient {
        -api_key: str
        -model: str
        +generate_text()
        +extract_json()
    }
    
    class OpenAIClient {
        -api_key: str
        -model: str
        +generate_text()
        +extract_json()
    }
    
    class BedrockClient {
        -region: str
        -model_id: str
        +generate_text()
        +extract_json()
    }
    
    class LLMFactory {
        +create_client(provider)
    }
    
    class LLMRouter {
        -use_case_mapping: dict
        -clients: dict
        +get_client(use_case)
        +generate_text(use_case)
        +extract_json(use_case)
    }
    
    BaseLLMClient <|-- OllamaClient
    BaseLLMClient <|-- AnthropicClient
    BaseLLMClient <|-- OpenAIClient
    BaseLLMClient <|-- BedrockClient
    
    LLMFactory ..> BaseLLMClient : creates
    LLMRouter o-- BaseLLMClient : uses
```

---

## 🎯 AI Engineering Concepts Map

### Core Concepts and Their Relationships

```mermaid
mindmap
  root((AI Engineering<br/>in FinCLI))
    LLM Integration
      Multi-Provider Support
        Ollama - Free/Local
        Anthropic - Best Quality
        OpenAI - Best Chat
        AWS Bedrock - Enterprise
      Abstraction Layer
        Base Client Interface
        Factory Pattern
        Strategy Pattern
      Use-Case Routing
        Extraction → Claude
        Chat → GPT-4
        Summary → Ollama
    
    Cost Optimization
      Response Caching
        LRU Eviction
        TTL Expiration
        Disk Persistence
        30-90% Savings
      Smart Routing
        Free for Dev
        Paid for Production
        Task-Specific Models
      Observability
        Token Tracking
        Cost Calculation
        Latency Metrics
    
    Prompt Engineering
      Versioning
        YAML Files
        Git History
        Rollback Support
      A/B Testing
        Compare Versions
        Metrics Collection
        Data-Driven Decisions
      Template System
        Variable Substitution
        Reusable Prompts
        Parameter Management
    
    Production Ready
      Testing
        106 Unit Tests
        Integration Tests
        Mocking LLMs
      Error Handling
        Retry Logic
        Fallbacks
        Graceful Degradation
      Monitoring
        Metrics Export
        Health Checks
        Alerting
```

---

## 📊 Caching Architecture

### Cache Flow and Eviction

```mermaid
graph LR
    subgraph "Cache Request Flow"
        A[LLM Request] --> B{Cache Check}
        B -->|Hit| C[Return Cached]
        B -->|Miss| D[Call LLM]
        D --> E[Store in Cache]
        E --> F[Return Response]
    end
    
    subgraph "Cache Management"
        G[Cache Entry] --> H{TTL Expired?}
        H -->|Yes| I[Evict]
        H -->|No| J{Cache Full?}
        J -->|Yes| K[LRU Eviction]
        J -->|No| L[Keep]
    end
    
    subgraph "Persistence"
        M[Memory Cache] --> N{Persist?}
        N -->|Yes| O[Disk Storage]
        N -->|No| P[Memory Only]
        O --> Q[Load on Restart]
    end
```

---

## 🎨 Design Patterns Used

### Pattern Catalog

```mermaid
graph TB
    subgraph "Creational Patterns"
        F[Factory Pattern<br/>LLM Client Creation]
        S[Singleton Pattern<br/>Global Instances]
    end
    
    subgraph "Structural Patterns"
        D[Decorator Pattern<br/>Cache Wrapper]
        A[Adapter Pattern<br/>LLM Abstraction]
    end
    
    subgraph "Behavioral Patterns"
        ST[Strategy Pattern<br/>Interchangeable LLMs]
        T[Template Method<br/>Prompt Rendering]
        O[Observer Pattern<br/>Metrics Tracking]
    end
    
    F -.->|Creates| LC[LLM Clients]
    S -.->|Manages| GI[Global Router/Cache]
    D -.->|Wraps| LLM[LLM Calls]
    A -.->|Unifies| API[Different APIs]
    ST -.->|Switches| IMPL[Implementations]
    T -.->|Renders| PR[Prompts]
    O -.->|Tracks| ME[Metrics]
```

---

## 🔍 Observability Architecture

### Metrics Collection Flow

```mermaid
graph TB
    subgraph "Metric Sources"
        L1[LLM Calls]
        L2[Cache Operations]
        L3[Database Queries]
        L4[API Requests]
    end
    
    subgraph "Metrics Tracker"
        MT[Metrics Tracker]
        MT --> TC[Token Counter]
        MT --> CC[Cost Calculator]
        MT --> LC[Latency Tracker]
        MT --> SC[Success Counter]
    end
    
    subgraph "Storage"
        JL[JSON Lines File]
        MEM[In-Memory Buffer]
    end
    
    subgraph "Analysis"
        R[Reports]
        D[Dashboards]
        A[Alerts]
    end
    
    L1 --> MT
    L2 --> MT
    L3 --> MT
    L4 --> MT
    
    MT --> MEM
    MEM --> JL
    
    JL --> R
    JL --> D
    JL --> A
```

---

## 🗄️ Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    TRANSACTIONS ||--o{ EMAILS : "extracted_from"
    TRANSACTIONS {
        int id PK
        string email_id FK
        float amount
        string transaction_type
        string merchant
        datetime transaction_date
        string currency
        datetime created_at
        datetime updated_at
    }
    
    EMAILS {
        string message_id PK
        string subject
        text body
        string sender
        datetime date
        boolean processed
        datetime created_at
    }
    
    USERS ||--o{ TRANSACTIONS : "owns"
    USERS {
        int id PK
        string email
        string name
        datetime created_at
    }
    
    BUDGETS ||--|| USERS : "belongs_to"
    BUDGETS {
        int id PK
        int user_id FK
        string category
        float amount
        string period
        datetime created_at
    }
```

---

## 🔐 Authentication Flow (Future Extension)

### OAuth2 + JWT Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant A as API
    participant G as Gmail OAuth
    participant DB as Database
    
    U->>F: Login
    F->>A: POST /auth/login
    A->>G: Redirect to Google
    G->>U: Consent Screen
    U->>G: Approve
    G->>A: Authorization Code
    A->>G: Exchange for Tokens
    G->>A: Access + Refresh Tokens
    A->>DB: Store Tokens
    A->>A: Generate JWT
    A->>F: Return JWT
    F->>F: Store JWT
    
    Note over F,A: Subsequent Requests
    
    F->>A: Request + JWT
    A->>A: Validate JWT
    A->>DB: Fetch User Data
    A->>F: Response
```

---

## 🚀 Deployment Architecture (Production)

### Cloud Deployment

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[AWS ALB]
    end
    
    subgraph "Application Tier"
        A1[API Instance 1]
        A2[API Instance 2]
        A3[API Instance 3]
    end
    
    subgraph "Background Workers"
        W1[Worker 1 - Email Fetch]
        W2[Worker 2 - Extraction]
        W3[Worker 3 - Analytics]
    end
    
    subgraph "Data Tier"
        RDS[(PostgreSQL RDS)]
        REDIS[(Redis Cache)]
        S3[(S3 Storage)]
    end
    
    subgraph "Monitoring"
        CW[CloudWatch]
        PR[Prometheus]
        GR[Grafana]
    end
    
    subgraph "Message Queue"
        SQS[AWS SQS]
    end
    
    LB --> A1
    LB --> A2
    LB --> A3
    
    A1 --> RDS
    A2 --> RDS
    A3 --> RDS
    
    A1 --> REDIS
    A2 --> REDIS
    A3 --> REDIS
    
    A1 --> SQS
    A2 --> SQS
    A3 --> SQS
    
    SQS --> W1
    SQS --> W2
    SQS --> W3
    
    W1 --> RDS
    W2 --> RDS
    W3 --> RDS
    
    A1 --> S3
    W2 --> S3
    
    A1 --> CW
    A2 --> CW
    A3 --> CW
    W1 --> CW
    W2 --> CW
    W3 --> CW
    
    CW --> PR
    PR --> GR
```

---

## 🧠 LLM Request Lifecycle

### Complete Request Flow

```mermaid
stateDiagram-v2
    [*] --> RequestReceived
    
    RequestReceived --> CheckCache
    
    CheckCache --> CacheHit : Found
    CheckCache --> CacheMiss : Not Found
    
    CacheHit --> RecordMetrics
    CacheMiss --> SelectProvider
    
    SelectProvider --> LoadPrompt
    LoadPrompt --> RenderPrompt
    RenderPrompt --> CallLLM
    
    CallLLM --> Success : 200 OK
    CallLLM --> Retry : Timeout/Error
    CallLLM --> Failed : Max Retries
    
    Retry --> CallLLM : Attempt < 3
    
    Success --> ParseResponse
    ParseResponse --> ValidateOutput
    
    ValidateOutput --> StoreCache : Valid
    ValidateOutput --> Failed : Invalid
    
    StoreCache --> RecordMetrics
    Failed --> RecordMetrics
    
    RecordMetrics --> [*]
```

---

## 📈 Scaling Strategy

### Horizontal Scaling

```mermaid
graph LR
    subgraph "Traffic Growth"
        T1[100 req/min] --> T2[1000 req/min] --> T3[10000 req/min]
    end
    
    subgraph "Scaling Response"
        S1[1 Instance] --> S2[5 Instances] --> S3[20 Instances]
    end
    
    subgraph "Optimizations"
        O1[Add Caching]
        O2[Add CDN]
        O3[Database Sharding]
        O4[Read Replicas]
    end
    
    T1 --> S1
    T2 --> S2
    T3 --> S3
    
    S1 --> O1
    S2 --> O2
    S3 --> O3
    S3 --> O4
```

---

## 🎯 Key Architectural Decisions

### Decision Log

| Decision | Rationale | Trade-offs |
|----------|-----------|------------|
| **Multi-Provider LLM** | Flexibility, cost optimization, resilience | Increased complexity |
| **SQLite for Dev** | Simple setup, no external dependencies | Not suitable for production scale |
| **LRU + TTL Cache** | Balance freshness and hit rate | Memory usage |
| **YAML Prompts** | Version control, easy updates | Extra file I/O |
| **JSON Lines Metrics** | Simple, append-only, easy to parse | No built-in aggregation |
| **Typer CLI** | Type-safe, auto-generated help | Learning curve |
| **FastAPI** | Modern, async, auto-docs | Python 3.7+ required |
| **Pydantic Config** | Type validation, IDE support | Verbose for simple configs |

---

## 🔄 Extension Points

### Where to Add New Features

```mermaid
graph TB
    subgraph "New LLM Provider"
        A[Implement BaseLLMClient]
        B[Add to Factory]
        C[Update Config]
        D[Add Tests]
    end
    
    subgraph "New Extraction Type"
        E[Create Extractor Class]
        F[Design Prompt]
        G[Add Validation]
        H[Update Database]
    end
    
    subgraph "New Analytics"
        I[Query Database]
        J[Process Data]
        K[Add Endpoint]
        L[Create Visualization]
    end
    
    subgraph "New Integration"
        M[Create Client]
        N[Add Auth]
        O[Implement Sync]
        P[Handle Errors]
    end
```

---

## 📚 Learning Path Through Architecture

### Recommended Study Order

```mermaid
graph TD
    Start[Start Here] --> L1[Layer 1: Config & Logging]
    L1 --> L2[Layer 2: LLM Clients]
    L2 --> L3[Layer 3: Router & Factory]
    L3 --> L4[Layer 4: Caching]
    L4 --> L5[Layer 5: Observability]
    L5 --> L6[Layer 6: Extractors]
    L6 --> L7[Layer 7: Database]
    L7 --> L8[Layer 8: CLI & API]
    L8 --> L9[Layer 9: Testing]
    L9 --> End[Complete Understanding]
    
    style Start fill:#90EE90
    style End fill:#FFD700
```

---

## 🎓 Concept Difficulty Levels

### Learning Progression

| Concept | Difficulty | Prerequisites | Time to Learn |
|---------|-----------|---------------|---------------|
| Configuration Management | ⭐ Beginner | Python basics | 1-2 hours |
| Logging | ⭐ Beginner | Python basics | 1-2 hours |
| LLM Client Interface | ⭐⭐ Intermediate | OOP, APIs | 3-4 hours |
| Factory Pattern | ⭐⭐ Intermediate | Design patterns | 2-3 hours |
| Strategy Pattern | ⭐⭐ Intermediate | Design patterns | 2-3 hours |
| Caching (LRU + TTL) | ⭐⭐⭐ Advanced | Data structures | 4-5 hours |
| Observability | ⭐⭐⭐ Advanced | Metrics, monitoring | 5-6 hours |
| Prompt Engineering | ⭐⭐ Intermediate | LLM basics | 3-4 hours |
| Database Design | ⭐⭐ Intermediate | SQL, ORMs | 3-4 hours |
| Testing | ⭐⭐ Intermediate | Pytest, mocking | 4-5 hours |
| API Design | ⭐⭐⭐ Advanced | REST, FastAPI | 5-6 hours |
| Production Deployment | ⭐⭐⭐⭐ Expert | DevOps, cloud | 10+ hours |

---

## 🚀 Next Steps

1. **Study the diagrams** - Understand how components interact
2. **Trace a request** - Follow a transaction extraction end-to-end
3. **Identify patterns** - Recognize design patterns in the code
4. **Map concepts** - Connect diagrams to actual code files
5. **Extend the system** - Add new features using the extension points

---

**Pro Tip:** Print these diagrams and keep them as reference while coding. Understanding the architecture visually makes implementation much easier!
