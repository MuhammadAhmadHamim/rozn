# rozn — روزن

> *روزن* — Urdu for a crack of light through a dark wall.  
> A developer buried in errors is in darkness. Rozn is the single shaft of light that finds exactly what is wrong.

Rozn is a local, offline, free coding assistant that runs entirely on your machine. No API keys, no cloud, no subscriptions. It reads your files, runs your commands, diagnoses your errors, and remembers your projects — across every session, across every language.

Built on a CPU-only 5th generation i7 with 8GB RAM and no GPU, in Shabqadar.

---

## Requirements

- Python 3.9 or higher
- [Ollama](https://ollama.com) installed and running
- The recommended model: `qwen2.5-coder:3b`

```powershell
ollama pull qwen2.5-coder:3b
```

---

## Installation

```powershell
git clone https://github.com/YOURUSERNAME/rozn.git
cd rozn
pip install -e .
```

That's it. Rozn installs as a system command. No environment variables, no build scripts, no GPU required.

---

## Usage

```powershell
rozn chat                          # start an interactive coding session
rozn index                         # scan and index your project
rozn index --find dispatch_tool    # locate any function instantly
rozn trace src/main.py             # visualise import dependencies
rozn detect                        # identify project language
rozn explain src/auth.py           # plain language explanation of a file
rozn document src/auth.py          # generate documentation for a file
rozn document --project            # generate a README for the whole project
rozn document --project --write    # write it to README.md
rozn docstring src/auth.py login   # generate a docstring for a function
```

Inside `rozn chat`:
remember: this project uses Django 4.2
memories                            # see everything rozn remembers
forget 0                            # forget memory at index 0
forget all                          # clear all memories
save                                # persist current session
usage                               # show token usage
help                                # show all commands
exit                                # quit

---

## What Rozn can do

**Reads and edits files** — mention a file by name and Rozn reads it before answering. Ask it to fix something and it makes the exact change with a diff.

**Runs commands** — Rozn uses your terminal to run tests, check versions, execute scripts, and see real output rather than guessing.

**Diagnoses errors** — paste a traceback and Rozn reads the exact file and line it points to before saying anything.

**Remembers your projects** — tell Rozn something once and it remembers it in every future session for that project. Per-project memory stored in `rozn.memory`.

**Indexes your codebase** — `rozn index` scans your entire project using AST parsing, stores every class and function with real line numbers, and gives you instant symbol lookup without touching the model.

**Follows import graphs** — `rozn trace` shows you exactly what a file depends on, one level deep.

**Detects languages** — works across 25 languages including Python, C++, Java, SQL, JavaScript, Rust, Go, and more. Detects SQL dialect from your dependencies. Extracts Python from Jupyter notebooks.

**Generates documentation** — explains files, generates language-appropriate docstrings (Google style for Python, Javadoc for Java, Doxygen for C/C++, JSDoc for JavaScript), and writes full project READMEs.

---

## How it works

Rozn is powered by [Ollama](https://ollama.com) running locally. The default model is `qwen2.5-coder:3b` — a 2GB quantized coding model that runs comfortably on CPU with 8GB RAM.

The agent loop in `query_engine.py` sends your message to the model, detects tool calls in the response, executes them, feeds results back, and loops up to 4 times per turn before returning a final answer. All tool execution — file reads, shell commands, edits — happens on your machine with no data leaving it.

---

## Project structure

The active core of Rozn:
src/
main.py              — CLI entrypoint, REPL, all subcommands
query_engine.py      — Ollama integration, tool loop, session management
real_tools.py        — FileReadTool, BashTool, FileEditTool, ListDirTool
indexer.py           — AST-based project scanner, import graph
memory.py            — persistent cross-session project memory
language_detector.py — 25-language detection, SQL dialect, Jupyter support
documenter.py        — file explanation, docstring generation, README generation
models.py            — shared dataclasses
permissions.py       — tool permission system
session_store.py     — session persistence
transcript.py        — conversation transcript management

The `src/` directory also contains scaffold infrastructure inherited from the original Python porting workspace — command and tool snapshot registries, runtime routing, bootstrap graphs, and subsystem placeholders. These power the diagnostic subcommands (`route`, `bootstrap`, `tool-pool`, `command-graph`) and are kept intact.

---

## Origin

Rozn began as a study of an open-source agent scaffold. The Python workspace was rebuilt and personalised into a local offline coding assistant over a series of development sessions.

The name comes from the Urdu word **روزن** — a crack of light through a dark wall. It was chosen after considering more than fifty names across Urdu, Persian, and invented vocabularies. Ghalib was considered and correctly rejected. Rozn was found by being quiet and precise — which is exactly what the tool is supposed to be.

Runs everywhere.

---

## Notes

- Sessions are saved in `.port_sessions/` — excluded from git
- Project memory lives in `rozn.memory` — excluded from git  
- Project index lives in `rozn.index` — excluded from git, regenerate with `rozn index`
- The timeout is set to 300 seconds — large files on CPU take time, this is expected
- Token budget warnings are normal in long sessions — start fresh with `rozn chat`

---

## License

MIT
