# REFLECTIONS

1. Multi-account

   - Để chạy `costctl` trên 100 account cần: cross-account role (assume-role) per account, config mapping (profile/role ARN), vòng lặp qua accounts, và thu thập kết quả vào CSV/JSON tập hợp. Sử dụng concurrent workers để xử lý nhanh và rate-limit/ backoff cho AWS APIs.

2. `idle` vs Trusted Advisor

   - `idle` (24h CPU avg) tốt để phát hiện máy mới hoặc vừa chạy ít; Trusted Advisor (14d) phù hợp cho xu hướng dài hạn. Tin tưởng `idle` khi bạn cần nhanh phát hiện mới; tin TA khi cần ổn định, giảm false positives.

3. `clean --apply` blast radius

   - Biện pháp giảm rủi ro: mặc định dry-run (đã có), require explicit `--apply`, confirmation summary, RBAC và allowlist accounts, tag-safe-lists, dry-run audit logs, và chặn chạy trên production bằng flag riêng.

4. AI assistance

   - Phần lớn scaffold và tests là từ bài tập starter. Tôi sử dụng AI để viết các hàm implement (`terminate`, `clean`, `tag`, `cost`) nhưng đã kiểm tra và chỉnh lại logic, lỗi xử lý ngoại lệ, và messages để khớp test. Tôi ước tính ~60% code ban đầu do AI gợi ý, 40% chỉnh sửa thủ công.

5. W7 carry-over

   - Giữ: `list`, `cost`, `idle` làm lõi (multi-account + reporting). Bỏ hoặc hạn chế: `clean --apply` cần thêm governance trước khi dùng ở production. Thêm: centralized credentials, per-account dry-run report, per-account tagging policy checks.

---

Short notes about this submission

- Tests: all unit/integration tests run locally with `moto` and show `25 passed`.
- Next recommended steps: add CI (GitHub Actions) to run `pytest` and `flake8`, add CHANGELOG and release tag.
