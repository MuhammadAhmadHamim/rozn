<div align="center">

<img width="100%" src="https://capsule-render.vercel.app/api?type=waving&color=0:0a0704,40:1a1208,100:0a0704&height=240&section=header&text=rozn%20%E2%80%94%20%D8%B1%D9%88%D8%B2%D9%86&fontSize=52&fontColor=f5f0e8&fontAlignY=40&desc=A%20crack%20of%20light%20through%20a%20dark%20wall&descAlignY=62&descColor=c9a84c&animation=fadeIn&fontFamily=Georgia" alt="rozn banner"/>

<br/>

![Python](https://img.shields.io/badge/Python-3.9%2B-f5f0e8?style=for-the-badge&logo=python&logoColor=0a0704)
![Ollama](https://img.shields.io/badge/Ollama-qwen2.5--coder%3A3b-1a1208?style=for-the-badge&logoColor=f5f0e8)
![Hardware](https://img.shields.io/badge/Hardware-CPU%20Only-c9a84c?style=for-the-badge&logoColor=0a0704)
![Cloud](https://img.shields.io/badge/Cloud%20Calls-Zero-f5f0e8?style=for-the-badge&logoColor=0a0704)
![Cost](https://img.shields.io/badge/Cost%20Per%20Use-%240-1a1208?style=for-the-badge&logoColor=c9a84c)
![Tests](https://img.shields.io/badge/Tests-28%20Passing-c9a84c?style=for-the-badge&logoColor=0a0704)

<br/><br/>

<div align="center">
<i>روزن — Urdu for a crack of light through a dark wall</i><br/>
<i>A developer buried in errors is in darkness. Rozn is the single shaft of light that finds exactly what is wrong</i>
</div>

<br/>

</div>

---

## ◈ What Rozn Is

A fully **offline, locally-run coding assistant** that installs as a system command and works across any programming language or project. No API keys. No cloud. No subscriptions. No GPU required.

It reads your files, runs your commands, diagnoses your errors, and remembers your projects — across every session, across every language. Built on a **5th generation Intel Core i7 with 8GB RAM and no GPU**, in Punjab, Pakistan.

This is not a wrapper around ChatGPT. This is not a demo. This is a production-grade local AI tool built from the ground up across nine development phases — with real agent tools, AST indexing, cross-session memory, 25-language detection, and 28 passing tests.

---

## ◈ At a Glance

<div align="center">

```
        9   CLI commands           25+  languages detected
   4   real agent tools       28   tests passing
  0   cloud calls             0   cost per use
    0   GPU required            1   shaft of light
```

</div>

---

## ◈ What Rozn Can Do

<details>
<summary><b>📂 Reads and Edits Files</b></summary>
<br/>

Mention a file by name and Rozn reads it before answering. Ask it to fix something and it makes the exact change with a diff — not a suggestion, an actual edit.

Three-tier file loading based on size: full content under 5KB, partial load 5–8KB, symbols-only above 8KB. Designed around the 8GB RAM constraint so the context window never floods.

</details>

<details>
<summary><b>⚡ Runs Commands</b></summary>
<br/>

Rozn uses your actual terminal to run tests, check versions, execute scripts, and see real output. It doesn't guess what your environment looks like — it looks.

</details>

<details>
<summary><b>🔍 Diagnoses Errors</b></summary>
<br/>

Paste a traceback and Rozn reads the exact file and line it points to before saying anything. No hallucinated explanations from incomplete context. It reads first, then speaks.

</details>

<details>
<summary><b>🧠 Remembers Your Projects</b></summary>
<br/>

Tell Rozn something once and it remembers it in every future session for that project. Per-project memory stored in `rozn.memory` — persistent, local, yours.

```
remember:       this project uses Django 4.2
memories        # see everything rozn remembers
forget 0        # forget memory at index 0
forget all      # clear everything
```

</details>

<details>
<summary><b>🗂️ Indexes Your Codebase</b></summary>
<br/>

`rozn index` scans your entire project using AST parsing — stores every class and function with real line numbers. Instant symbol lookup without touching the model.

```powershell
rozn index                         # full project scan
rozn index --find dispatch_tool    # locate any function instantly
```

</details>

<details>
<summary><b>🔗 Follows Import Graphs</b></summary>
<br/>

`rozn trace` shows exactly what a file depends on — relative imports resolved, one level deep, visualised cleanly.

```powershell
rozn trace src/main.py
```

</details>

<details>
<summary><b>📝 Generates Documentation</b></summary>
<br/>

Explains files in plain language. Generates language-appropriate docstrings — Google style for Python, Javadoc for Java, Doxygen for C/C++, JSDoc for JavaScript. Writes full project READMEs from codebase and memory.

```powershell
rozn explain src/auth.py
rozn document src/auth.py
rozn document --project --write
rozn docstring src/auth.py login
```

</details>

---

## ◈ The Command Surface

<div align="center">

| Command | What It Does |
|:---:|:---|
| `rozn chat` | Interactive REPL — tool calling, memory, full project context |
| `rozn index` | AST scan of entire codebase — instant symbol lookup |
| `rozn index --find SYMBOL` | Locate any class or function with exact file and line number |
| `rozn trace FILE` | Visualise import dependency graph of any file |
| `rozn detect` | Identify primary language, SQL dialect, Jupyter presence |
| `rozn explain FILE` | Plain English explanation of any file |
| `rozn document FILE` | Generate structured documentation for a file |
| `rozn document --project` | Generate a full README from codebase and memory |
| `rozn document --project --write` | Write it directly to README.md |
| `rozn docstring FILE FN` | Generate a language-appropriate docstring for any function |

</div>

---

## ◈ Architecture

```
rozn/
│
├── tests/
|   └── testing_porting_workspace.py ← All 29 tests for Rozn described    
|
├── src/
│   ├── main.py              ← CLI entrypoint, REPL, all subcommands
│   ├── query_engine.py      ← Ollama integration, tool loop, session management
│   ├── real_tools.py        ← FileReadTool, BashTool, FileEditTool, ListDirTool
│   ├── indexer.py           ← AST project scanner, import graph resolution
│   ├── memory.py            ← persistent cross-session project memory
│   ├── language_detector.py ← 25-language detection, SQL dialect, Jupyter support
│   ├── documenter.py        ← explanation, docstring generation, README generation
│   ├── models.py            ← shared dataclasses
│   ├── permissions.py       ← tool permission system
│   ├── session_store.py     ← session persistence
│   └── transcript.py        ← conversation transcript management
│
├── Rozn_Technical_Report.pdf ← A detailed techincal description of Rozn
├── pyproject.toml           ← Toml file to make Rozn a Python script
├── rozn.memory              ← per-project memory (git ignored)
├── rozn.index               ← project index (git ignored)
├── .port_sessions/          ← saved sessions (git ignored)
└── README.md
```

<div align="center">

| Component | Technology | Purpose |
|:---:|:---:|:---|
| **Inference engine** | Ollama + qwen2.5-coder:3b | Local model serving over HTTP on port 11434 |
| **Agent loop** | query_engine.py | Tool calling, message history, token tracking |
| **Tool layer** | real_tools.py | File read, bash, file edit with diff, list dir |
| **Project indexer** | indexer.py | AST scanning, symbol extraction, import graphs |
| **Language detector** | language_detector.py | 25 languages, SQL dialect, Jupyter extraction |
| **Memory system** | memory.py | Per-project persistent JSON across sessions |
| **Documenter** | documenter.py | Explain, docstring, README generation |
| **CLI interface** | main.py + Rich | REPL, subcommands, amber terminal identity |

</div>

---

## ◈ The Nine Phases

```
Phase 1  →  Ollama installation, model pull, HTTP API verification on CPU-only Windows

Phase 2  →  Query engine wired to Ollama — real model calls, streaming, Rich terminal

Phase 3  →  Four real agent tools — file read, bash, file edit with diff, dir listing

Phase 4  →  System prompt refinement — traceback handling, syntax error classification

Phase 5  →  AST project indexer, keyword detection, lazy context, compressed memory

Phase 6  →  Cross-session persistent memory — per-project rozn.memory, remember/forget

Phase 7  →  Import graph resolution, relative import scanning, rozn trace command

Phase 8  →  25-language detection, SQL dialect sniffing, Jupyter extraction

Phase 9  →  Language-aware documentation — explain, docstring, project README
```

---

## ◈ Built Under Constraint

Everything about Rozn was shaped by one hard rule — **8GB RAM, no GPU**.

```
Model loaded          →  ~2GB    (qwen2.5-coder:3b quantized)
OS + overhead         →  ~0.5GB
Agent headroom        →  ~5.5GB remaining

Context window        →  ~4096 tokens — every token deliberate
```

<div align="center">

| Resource | Token Budget |
|:---:|:---:|
| System prompt | ~500 tokens |
| Session memory (compressed) | ~100 tokens |
| File content (lazy loaded) | ~300 tokens |
| User message | ~50 tokens |
| Model response headroom | ~3000 tokens |

</div>

These aren't arbitrary limits. They are the architecture. Three-tier file loading, compressed session memory, lazy context injection, a 2-message history window — every decision traces back to the constraint. Constraint didn't limit Rozn. It shaped it.

---

## ◈ Language Support

<div align="center">

![](https://img.shields.io/badge/Python-f5f0e8?style=flat-square&logo=python&logoColor=0a0704)
![](https://img.shields.io/badge/Jupyter-c9a84c?style=flat-square&logo=jupyter&logoColor=0a0704)
![](https://img.shields.io/badge/C%2B%2B-1a1208?style=flat-square&logo=cplusplus&logoColor=f5f0e8)
![](https://img.shields.io/badge/C-0a0704?style=flat-square&logo=c&logoColor=f5f0e8)
![](https://img.shields.io/badge/Java-f5f0e8?style=flat-square&logo=openjdk&logoColor=0a0704)
![](https://img.shields.io/badge/C%23-c9a84c?style=flat-square&logo=sharp&logoColor=0a0704)
![](https://img.shields.io/badge/JavaScript-1a1208?style=flat-square&logo=javascript&logoColor=f5f0e8)
![](https://img.shields.io/badge/TypeScript-0a0704?style=flat-square&logo=typescript&logoColor=f5f0e8)

![](https://img.shields.io/badge/SQL-c9a84c?style=flat-square&logo=postgresql&logoColor=0a0704)
![](https://img.shields.io/badge/Rust-1a1208?style=flat-square&logo=rust&logoColor=f5f0e8)
![](https://img.shields.io/badge/Go-0a0704?style=flat-square&logo=go&logoColor=f5f0e8)
![](https://img.shields.io/badge/Kotlin-f5f0e8?style=flat-square&logo=kotlin&logoColor=0a0704)
![](https://img.shields.io/badge/Swift-c9a84c?style=flat-square&logo=swift&logoColor=0a0704)
![](https://img.shields.io/badge/Ruby-1a1208?style=flat-square&logo=ruby&logoColor=f5f0e8)
![](https://img.shields.io/badge/PHP-0a0704?style=flat-square&logo=php&logoColor=f5f0e8)
![](https://img.shields.io/badge/Scala-f5f0e8?style=flat-square&logo=scala&logoColor=0a0704)

![](https://img.shields.io/badge/Dart-c9a84c?style=flat-square&logo=dart&logoColor=0a0704)
![](https://img.shields.io/badge/R-1a1208?style=flat-square&logo=r&logoColor=f5f0e8)
![](https://img.shields.io/badge/MATLAB-0a0704?style=flat-square&logo=mathworks&logoColor=f5f0e8)
![](https://img.shields.io/badge/Shell-f5f0e8?style=flat-square&logo=gnu-bash&logoColor=0a0704)
![](https://img.shields.io/badge/PowerShell-c9a84c?style=flat-square&logo=powershell&logoColor=0a0704)
![](https://img.shields.io/badge/Batch-1a1208?style=flat-square&logo=windows-terminal&logoColor=f5f0e8)

![](https://img.shields.io/badge/Haskell-0a0704?style=flat-square&logo=haskell&logoColor=f5f0e8)
![](https://img.shields.io/badge/OCaml-f5f0e8?style=flat-square&logo=ocaml&logoColor=0a0704)
![](https://img.shields.io/badge/Julia-c9a84c?style=flat-square&logo=julia&logoColor=0a0704)
![](https://img.shields.io/badge/Elixir-1a1208?style=flat-square&logo=elixir&logoColor=f5f0e8)
![](https://img.shields.io/badge/Erlang-0a0704?style=flat-square&logo=erlang&logoColor=f5f0e8)

</div>

---

## ◈ How Rozn Compares

<div align="center">

| Capability | Rozn | Typical hobbyist Ollama project |
|:---:|:---:|:---:|
| Tool calling | 4 real tools, agent loop, diff output | None — chat only |
| Project awareness | AST index, import graph, symbol lookup | None |
| Cross-session memory | Per-project persistent JSON | None |
| Language detection | 25 languages, SQL dialect, Jupyter | None |
| Documentation | Explain, docstring, README generation | None |
| Test suite | 28 passing, 1 cleanly skipped | None |
| Installation | System command via `pip install -e .` | Run from directory only |
| Token management | Tiered loading, compressed memory | Unlimited context assumption |

</div>

---

## ◈ Installation

**Requirements:** Python 3.9+ · [Ollama](https://ollama.com) installed and running

```powershell
# Pull the model
ollama pull qwen2.5-coder:3b

# Clone and install
git clone https://github.com/MuhammadAhmadHamim/rozn.git
cd rozn
pip install -e .
```

Rozn installs as a system command. No environment variables. No build scripts. No GPU required.

---

## ◈ Usage

```powershell
rozn chat                          # start an interactive coding session
rozn index                         # scan and index your project
rozn index --find dispatch_tool    # locate any function instantly
rozn trace src/main.py             # visualise import dependencies
rozn detect                        # identify project language
rozn explain src/auth.py           # plain language explanation of a file
rozn document src/auth.py          # generate documentation for a file
rozn document --project --write    # write a README for the whole project
rozn docstring src/auth.py login   # generate a docstring for a function
```

Inside `rozn chat`:
```
remember: this project uses Django 4.2
memories        # see everything rozn remembers
forget 0        # forget memory at index 0
forget all      # clear all memories
save            # persist current session
usage           # show token usage
help            # show all commands
exit            # quit
```

---

## ◈ Notes

```
Sessions     →  saved in .port_sessions/  — excluded from git
Memory       →  lives in rozn.memory      — excluded from git
Index        →  lives in rozn.index       — excluded from git, regenerate with rozn index
Timeout      →  300 seconds               — large files on CPU take time, expected
Token budget →  warnings normal in long sessions — start fresh with rozn chat
```

---

## ◈ Skills This Project Demonstrates

<div align="center">

![](https://img.shields.io/badge/Python-Agent%20Architecture-1a1208?style=flat-square&logo=python&logoColor=f5f0e8)
![](https://img.shields.io/badge/Ollama-Local%20LLM%20Integration-f5f0e8?style=flat-square&logoColor=0a0704)
![](https://img.shields.io/badge/AST-Codebase%20Indexing-c9a84c?style=flat-square&logo=python&logoColor=0a0704)
![](https://img.shields.io/badge/CLI-Rich%20Terminal%20Design-1a1208?style=flat-square&logo=python&logoColor=f5f0e8)
![](https://img.shields.io/badge/Tool%20Calling-Agent%20Loop%20Design-f5f0e8?style=flat-square&logoColor=0a0704)
![](https://img.shields.io/badge/Memory%20Systems-Persistent%20JSON-c9a84c?style=flat-square&logo=python&logoColor=0a0704)
![](https://img.shields.io/badge/Token%20Management-Context%20Budgeting-1a1208?style=flat-square&logo=python&logoColor=f5f0e8)
![](https://img.shields.io/badge/Language%20Detection-25%20Languages-f5f0e8?style=flat-square&logoColor=0a0704)
![](https://img.shields.io/badge/Documentation%20Generation-Multi%20Language-c9a84c?style=flat-square&logo=python&logoColor=0a0704)
![](https://img.shields.io/badge/System%20Design-Constrained%20Hardware-1a1208?style=flat-square&logo=python&logoColor=f5f0e8)
![](https://img.shields.io/badge/Testing-28%20Tests%20Passing-f5f0e8?style=flat-square&logoColor=0a0704)

</div>

---

## ◈ Origin

Rozn began as a study of an open-source agent scaffold. The Python workspace was rebuilt and personalised into a local offline coding assistant across nine development phases.

The name was chosen after evaluating over 50 candidates across Urdu, Persian, Arabic, Pashto, and invented vocabularies. Ghalib was considered and correctly rejected. **Rozn** was found by being quiet and precise — which is exactly what the tool is supposed to be.

*Built with dedication. Punjab, Pakistan.*

---

<div align="center">

<img width="100%" src="https://capsule-render.vercel.app/api?type=waving&color=0:1a1208,50:0a0704,100:1a1208&height=120&section=footer&animation=fadeIn" alt="footer"/>

*روزن — the crack of light. Everything else is darkness*

</div>
