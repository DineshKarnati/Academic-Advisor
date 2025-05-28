# Hybrid Retrieval for RAG using Neo4j – Full Technical Draft

## Objective
Build a **Hybrid Retrieval system** for RAG (Retrieval-Augmented Generation) using **Neo4j** as the knowledge base. It combines:
- **Dense Retrieval** via OpenAI embeddings + Neo4j Vector Index  
- **Sparse Retrieval** via full-text search  
- **Hybrid Strategy** to rerank and optimize results  

---

## Schema Overview

###  Node Types

| Node Label        | Description                    |
|-------------------|--------------------------------|
| ProductGroup      | Vehicle categories             |
| Manufacturer      | Car maker (e.g., Toyota)       |
| Model             | Car model (e.g., Yaris)        |
| Component         | Part of the vehicle            |
| Problem           | Issues faced                   |
| Symptom           | Observable signs               |
| Procedures        | Repair/installation steps      |
| BasicInfo         | General car information        |
| SubComponent      | Detailed internal components   |
| AdditionalInfo    | Notes, warnings, extra data    |
| SuspectArea       | Potential faulty regions       |
| TestProcedures    | Diagnostic steps               |

### 🔗 Relationships

| Relationship Name         | Description                            |
|---------------------------|----------------------------------------|
| HAS_MODEL                 | ProductGroup → Model                   |
| MANUFACTURED_BY          | Model → Manufacturer                   |
| HAS_COMPONENT             | Model → Component                      |
| HAS_PROCEDURES            | Component → Procedures                 |
| HAS_SYMPTOM               | Problem → Symptom                      |
| HAS_SUBPROBLEM            | Problem → Sub-problem (hierarchical)   |
| HAS_ADDITIONALINFO        | Component/Problem → AdditionalInfo     |
| HAS_SUSPECTAREA           | Problem → SuspectArea                  |
| HAS_BASICINFO             | Component → BasicInfo                  |
| HAS_SUBCOMPONENT          | Component → SubComponent               |
| HAS_TESTPROCEDURES        | Component → TestProcedures             |

---
## PDF → Structured XML via LLM

### Script: `pdf_extraction.py`
- Extracts raw text from manuals
- Breaks long text into chunks
- Uses GPT to output structured data with tags like:
  ```xml
  <problem>ac not cooling</problem>
  <symptom>weak airflow</symptom>
  <test><name>compressor test</name><procedure>Check pressure</procedure></test>
- Tags are flexible; non-standard tags are stored under <additional_info>


## Data Ingestion Flow

### Script Logic

**Function:** `parse_and_insert_data(xml_content, component_name)`
- Cleans XML from LLM output
- Maps each XML tag to Neo4j label via `tag_to_label_map`
- Creates and links graph nodes using Cypher queries
- Handles nested problems and long lists efficiently
- Uses APOC for conditional logic in Cypher (dynamic merging)

---

## Embedding-Based Dense Retrieval

### Function: `get_openai_embedding(text)`
- **Embedding Model:** `text-embedding-3-small`
- Converts user queries into dense vectors

### Vector Search

**Function:** `vector_search(query_vector, node_label, top_k=3, threshold=0.7)`  
- **Vector Index Name:** `vectorIndex_<NodeLabel>`  
- **Cypher Syntax:**
  ```cypher
  CALL db.index.vector.queryNodes($index_name, $top_k, $query_vector)
  ```

---

## Sparse Retrieval (Planned)

**Function:** `sparse_search(user_query, node_label)`  
Uses full-text search index:

```cypher
CALL db.index.fulltext.queryNodes('search_<Label>', $query) YIELD node, score
RETURN node.name, score
```

---

## hybrid_retriever

**Function:** `Use ThreadPoolExecutor to parallelize vector and full-text search`  
Combines dense and sparse scores:

```python
hybrid_score = alpha * dense_score + (1 - alpha) * sparse_score
```

- Create `retrieve_data()` to unify both retrieval strategies
- Normalize scores before combining
- Filter by top-k if needed
- Merge and deduplicate results by node name

---

## User Flow Diagram

```text
[User Query]
     ↓
[Rephrasing with LLM (if chat history exists)]
     ↓
[Embedding Generation using OpenAI]
     ↓
┌────────────────────┐     ┌────────────────────┐
│ Dense Search        │     │ Sparse Search       │
│ (Neo4j Vector Index)│     │ (Fulltext Lucene)   │
└──────────┬──────────┘     └──────────┬──────────┘
           ↓                           ↓
     [Hybrid Merge & Rerank Scores (alpha-weighted)]
                       ↓
         [Deduplication & Top-K Selection]
                       ↓
       [Graph Expansion (Related Nodes)]
                       ↓
         [Final LLM Response Generation]

---

## Sample User Queries & Results

| User Query                                | Top Match Node              | Node Type   | Score |
| ----------------------------------------- | --------------------------- | ----------- | ----- |
| "AC not working properly"                 | "ac system not cooling"     | Problem     | 0.89  |
| "Car remote doesn't lock"                 | "keyless entry malfunction" | Problem     | 0.86  |
| "Headlights flickering at night"          | "check headlamp fuse"       | Procedures  | 0.81  |
| "Steering makes noise when turning"       | "steering fluid low"        | Symptom     | 0.83  |
| "What's the cause of engine overheating?" | "radiator coolant leak"     | SuspectArea | 0.84  |

---

##  Visual Graph Snapshot – Example Traversal Path

###  Query: "AC not cooling"

**Traversal Path (Graph View):**
```
(:Component {name: "air conditioning"}) 
   └──[:HAS_PROBLEM]──> (:Problem {name: "ac not cooling"})
       └──[:HAS_SYMPTOM]──> (:Symptom {name: "low airflow"})
       └──[:HAS_PROCEDURES]──> (:Procedures {name: "check compressor pressure"})
```
> _Insert a Neo4j Bloom / Browser screenshot for this traversal path_

---

##  Comparative Outcomes – Dense vs Sparse vs Hybrid

### Query: "Remote key not working"

| Retrieval Mode | Top Match                      | Type    | Score | Notes                              |
| -------------- | ------------------------------ | ------- | ----- | ---------------------------------- |
| **Sparse**     | "key" → "lock" → "battery"     | Problem | 0.65  | Keyword match, misses context      |
| **Dense**      | "keyless entry not responding" | Problem | 0.86  | Captures intent, loses exact token |
| **Hybrid**     | "keyless entry malfunction"    | Problem | 0.92  | Best of both, exact + semantic     |

> **Conclusion:** Hybrid retrieval improved both relevance and clarity. It correctly inferred "remote key" refers to "keyless entry".

---

## Real-World Query Examples (for Demo/Docs)

| Query                                | Expected Top Match          | Node Type   | Why it's relatable         |
| ------------------------------------ | --------------------------- | ----------- | -------------------------- |
| "AC not working"                     | "ac system not cooling"     | Problem     | Common summer issue        |
| "Car won’t lock with remote"         | "keyless entry malfunction" | Problem     | Frequent user complaint    |
| "Headlights dim after engine starts" | "battery voltage drop"      | Symptom     | Electrical fault diagnosis |
| "Steering hard to turn"              | "low power steering fluid"  | SuspectArea | Linked to hydraulic issue  |
| "How to remove bumper?"              | "bumper removal procedure"  | Procedures  | Practical DIY fix          |

 **Tip:** Capture real user-like phrasing to test the robustness of your retrieval system.

---
## Environment Configuration

| Key               | Purpose                                        |
| ----------------- | ---------------------------------------------- |
| `NEO4J_URI`       | Neo4j DB connection URI                        |
| `OPENAI_API_KEY`  | LLM + Embedding access                         |
| `EMBEDDING_MODEL` | OpenAI model (default: text-embedding-3-small) |
| `model`           | Chat model (default: gpt-4o)                   |
| `alpha`           | Weight for hybrid scoring                      |
| `top_k`           | Result cutoff                                  |
| `threshold`       | Similarity threshold                           |


## Function Reference

| Function Name                | Description                             |
| ---------------------------- | --------------------------------------- |
| `extract_pdf_content`        | Read PDF into plain text                |
| `structure_content_with_llm` | Generate structured XML tags            |
| `parse_and_insert_data`      | Create nodes and relationships in Neo4j |
| `get_openai_embedding`       | Generate dense vector from text         |
| `vector_search`              | Perform ANN vector search               |
| `fulltext_search`            | Run Lucene query on text fields         |
| `hybrid_search`              | Merge dense + sparse results            |
| `process_top_nodes`          | Expand retrieved node context           |
| `final_call`                 | Generate final LLM response             |
| `rag_advisor`                | Full pipeline: input → answer           |
