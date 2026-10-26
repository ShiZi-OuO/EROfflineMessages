# Private static login-code research

Reads the exact local EXE into a non-executable byte buffer. Uses dearxan 0.5.2
with **default features disabled** and only its static analysis feature path.
Does not load/execute the game, open processes, patch memory, alter EAC/Arxan
configuration, or connect to servers. The runtime disabler is not compiled.

Only a bounded 3,840-byte code window and analysis metadata are retained under
build/research/protocol-private. These local game-code bytes are private research
and must not be shipped. Analysis results do not prove authentication success.

Dependencies are fixed by Cargo.toml and Cargo.lock. MIT licences for dearxan and
pelite are included in licenses/. This optional research tool is not a replay-DLL
or end-user installation dependency.

On this host Rust uses GNU tooling, whose linker failed on Chinese target paths.
Use an ASCII build-output directory:

```text
C:\Users\Lenovo\.cargo\bin\cargo.exe build --release --locked --manifest-path tools/static-code-analysis/Cargo.toml --target-dir D:/codex/er-static-login-analysis-build
```

Verify the original EXE SHA-256 before running. Pass its file path and a **new**
immediate child of build/research/protocol-private as output. The input EXE is
never written. Output is refused if it already exists.
