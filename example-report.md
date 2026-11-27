# Night Shift report

Provider mode: mock

## Assignment

    Find every "TODO" and identify the source file and line for each review item.

## Findings

    Inspected 2 files. The bounded search for 'TODO' returned 2 matching lines.
    checklist.txt:2 — TODO: Compare the final audio level with the opening scene.
    release.md:4 — TODO: Confirm caption timing on the closing frame.

Evidence cited: E2, E3

Static inspection. Text reads sample 20 lines and searches sample 32 KiB per file, up to 20 hits. Excerpts show up to 240 characters per line.

## Evidence

### E1 · inventory

    {
      "id": 1,
      "action": {
        "tool": "inventory"
      },
      "result": [
        {
          "path": "checklist.txt",
          "bytes": 107
        },
        {
          "path": "release.md",
          "bytes": 130
        }
      ]
    }

### E2 · inspect

    {
      "id": 2,
      "action": {
        "tool": "inspect"
      },
      "result": {
        "files": 2,
        "extensions": {
          ".txt": 1,
          ".md": 1
        },
        "manifests": []
      }
    }

### E3 · search

    {
      "id": 3,
      "action": {
        "tool": "search",
        "query": "TODO"
      },
      "result": [
        {
          "path": "checklist.txt",
          "line": 2,
          "text": "TODO: Compare the final audio level with the opening scene."
        },
        {
          "path": "release.md",
          "line": 4,
          "text": "TODO: Confirm caption timing on the closing frame."
        }
      ]
    }

### E4 · read

    {
      "id": 4,
      "action": {
        "tool": "read",
        "path": "checklist.txt"
      },
      "result": [
        {
          "path": "checklist.txt",
          "line": 1,
          "text": "Owner review items"
        },
        {
          "path": "checklist.txt",
          "line": 2,
          "text": "TODO: Compare the final audio level with the opening scene."
        },
        {
          "path": "checklist.txt",
          "line": 3,
          "text": "The title card is approved."
        }
      ]
    }

## Verified input hashes

    {
      "files": [
        {
          "path": "checklist.txt",
          "bytes": 107,
          "sha256": "910da733d8cb24a666068256b427120a471bf100c4d2d91e6cebbbc463fa385a"
        },
        {
          "path": "release.md",
          "bytes": 130,
          "sha256": "96fadae67a1f16278f6d01e82a26926e9db5266f67c4cb466d7b190864dc4c7a"
        }
      ],
      "originals": [
        {
          "name": "demo-project.zip",
          "bytes": 417,
          "sha256": "44cf7dba7a6769daae3788d9aca2e787fcd811859299aa86bf4187eda0acb77b"
        }
      ]
    }
