# Base AI Coding — Simple & Flexible Agentic Harness

Bộ khung điều phối AI Agent tối giản, thực dụng và linh hoạt (kết hợp tinh hoa từ **OpenSpec**, **GSD Core**, **Ponytail**, và **Parallel Worktree**), dùng chung cho mọi nền tảng (**Antigravity, Claude Code, Cursor, OpenCode, Codex**) và áp dụng được cho cả **dự án mới tinh (Greenfield)** lẫn **dự án đang chạy (Brownfield)**.

## Điểm nổi bật

1. **Chạy song song với `AGENTS.md` / `CLAUDE.md` sẵn có (Additive Coexistence):**
   - Nếu dự án đã có `AGENTS.md` hoặc `CLAUDE.md`, `inject.sh` tuyệt đối không ghi đè mà tự động cài vào `.agents/rules/coding-base.md`, `.claude/rules/coding-base.md`, `.cursor/rules/coding-base.mdc`.
2. **Tàng hình với Git (Stealth Mode mặc định):**
   - Tự động ẩn toàn bộ file harness qua `.git/info/exclude` (hỗ trợ cả git worktree) — `git status` sạch 100%, không làm bẩn PR của team.
3. **Đa phiên song song không đá nhau (Multi-Session Safe):**
   - Bảng `Active In-Flight Sessions` trong `.context/state.md` khóa file theo từng row (`Locked / Touched Files`) và hỗ trợ kiểm tra theo phạm vi (`VERIFY_FILES`, `VERIFY_SPEC`).
4. **Rule 2 Đầu (2-End Session Lifecycle):**
   - **Đầu phiên (Start-of-Session):** Tự động dọn các task `READY` mà user đã nghiệm thu sang `Recently Completed`, hoặc nối tiếp đúng phiên đang dở.
   - **Cuối lượt (End-of-Turn):** Chạy Gatekeeper cơ học + kiểm thử E2E thực tế (DB/API/Browser) rồi chuyển trạng thái sang `READY` (giữ nguyên row phòng khi user muốn tinh chỉnh tiếp).
5. **Chốt chặn cơ học chống AI gian lận test (`verify-gate.sh` & `check-blast-radius.py`):**
   - Chặn `.skip`, `.only`, `@Disabled`, `catch {}` rỗng, xóa assertion.
   - Tự động truy vết Blast Radius qua `.code-review-graph/graph.db` (hoặc fallback `git diff` + `git grep`) và kiểm tra đồng bộ Cross-Repo.

---

## Cấu trúc (Zero External Dependencies)

```text
base-ai-coding-simple-flexible/
├── AGENTS.md                      # Bộ định tuyến 2 làn (Fast Lane vs Spec Lane) + Rule 2 Đầu + 5 Luật Test
├── CLAUDE.md -> AGENTS.md         # Symlink tương thích Claude Code
├── inject.sh                      # Script 1 lệnh gắn Base vào bất kỳ repo nào (Stealth / Track / Force)
└── .context/
    ├── project.md                 # Bản đồ dự án: Stack, VERIFY_CMD, Runtime Sandbox, Error Memory
    ├── state.md                   # Bảng trạng thái đa phiên (< 30 dòng)
    ├── verify-gate.sh             # Gatekeeper cơ học 4 bước (Anti-cheat diff, Blast-radius, TC-xx, VERIFY_CMD)
    ├── check-blast-radius.py      # Engine phân tích độ lan tỏa (SQLite Call Graph + Git Grep fallback)
    └── changes/
        └── _TEMPLATE.md           # Mẫu Delta Spec + Spec-to-Test Contract + Cross-Repo Impact Matrix
```

---

## Cách cài đặt vào dự án bất kỳ

```bash
# 1. Clone bộ base về máy
git clone https://github.com/hkien2310/base-ai-coding-simple-flexible.git

# 2. Inject vào dự án mục tiêu (Mặc định: Stealth Mode + Không ghi đè AGENTS.md gốc)
./base-ai-coding-simple-flexible/inject.sh /path/to/your-project

# Tuỳ chọn:
# ./inject.sh /path/to/your-project --track   # Cho phép track vào Git nếu là repo cá nhân muốn commit luôn
# ./inject.sh /path/to/your-project --force   # Ghi đè cập nhật toàn bộ file harness mới nhất
```

---

## Cách vận hành sau khi gắn

1. **Khởi tạo 1 lần duy nhất (`Mode 0`):**
   - **Dự án đang có code (Brownfield):** Mở dự án và gõ `"onboard"`. Agent tự quét codebase, lập chỉ mục call graph (nếu có) và điền đầy đủ lệnh build/test/lint vào `.context/project.md`.
   - **Dự án mới tinh (Greenfield):** Mở dự án và gõ `"bootstrap"`. Agent hỏi ngắn gọn các chốt chặn kiến trúc rồi khởi tạo MVP spec.
2. **Làm việc hàng ngày (`Mode 1` — Tự động phân 2 làn):**
   - **⚡ Fast Lane (≤ 3 files, không đổi API/DTO contract):** Sửa trực tiếp → viết/cập nhật test → chạy `./.context/verify-gate.sh` → báo cáo (0 sinh file markdown thừa).
   - **🏗️ Spec Lane (> 3 files hoặc có thay đổi API/DTO/Cross-repo):** Lập `.context/changes/<slug>.md` kèm bảng `TC-xx` → chờ duyệt `"ok"` → chia Wave chạy song song → Adversarial Review → chạy `./.context/verify-gate.sh`.
