# photo-harbor

[![Built with AIKit](https://img.shields.io/badge/built%20with-AIKit-6f42c1)](https://github.com/Aegean-E/AIKit)

Self-hosted photo server for Windows: an iPhone sends new photos over home Wi-Fi through Apple Shortcuts, no app needed, with a verified-hash cleanup and a gallery.

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: <FILL: each runtime this project needs and its minimum version>
- **Canonical Regression Shield Gate**:
  ```bash
  <FILL: the command that runs the whole test suite from this project root>
  ```

### 🛠️ AIKit Commands (run from the AIKit folder)
| Role | Command |
|---|---|
| Status, task and gates | `python aikit.py status photo-harbor` |
| Phase 4: every gate | `python aikit.py check photo-harbor` |
| Repair memory and map, then check | `python aikit.py fix photo-harbor` |
| Resume an interrupted task | `python aikit.py resume photo-harbor` |

## 📦 What's Inside

```text
photo-harbor/
├── .gitignore                <- transient AIKit state excluded
├── LICENSE                   <- GNU AGPL-3.0
├── README.md
└── .aikit/                   <- this project's memory: record, ledger, decisions
```

## 📜 License

GNU Affero General Public License v3.0; see [LICENSE](LICENSE).
