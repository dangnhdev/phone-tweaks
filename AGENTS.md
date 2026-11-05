# phone-tweaks trên hdstudio

Chỉ dùng checkout hiện tại. Không tạo worktree. Một implementation owner ghi file;
không chạy đồng thời nhiều agent sửa scripts liên quan.

## Gate trước mọi đề xuất hoặc thay đổi debloat

1. Chạy `python3 phone_tweaks.py refresh` để fetch HEAD mới nhất của CẢ HAI nguồn.
   - https://github.com/itxjobe/samsungdebloat
   - https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation
2. Nếu một fetch lỗi, dừng plan/apply. Không dùng cache cũ để âm thầm tiếp tục.
3. Đối chiếu inventory live của đúng profile, model, user 0 và hardware serial.
   Trích URL, commit, đường dẫn và package cụ thể từ nguồn, cùng trạng thái cài đặt live.
4. Review từng candidate. Danh sách S25/S26 không áp dụng mặc định cho S23 Ultra hay Tab S8.
   Không chạy scripts upstream, không nhập nguyên danh sách lớn.
5. Audit và plan mặc định chỉ đọc thiết bị. Trước apply, xin authorization RIÊNG
   cho đúng thiết bị và từng package sau khi user đã xem plan. Yêu cầu xây toolkit
   không phải authorization debloat. Apply phải dùng `--journal` của plan đã review,
   cùng hardware, package, trạng thái gốc và commit nguồn. Không tự điền `--authorization` để vượt gate.

Luôn bảo toàn telephony, S Pen, Knox/Secure Folder, DeX, camera, notifications,
VPN, automation, Quick Share, tài khoản, OTA, launcher, SystemUI, Settings,
GMS/Play và WebView. Chỉ disable-user candidate có mặt được user chọn rõ ràng.
Không uninstall, xóa dữ liệu, đổi appops hay ép compilation.

Mọi ADB shell phải có `-s` rõ ràng và qua helper validation chung.
Offline, unauthorized, model mismatch hoặc hardware identity thay đổi phải fail closed.
Không restart ADB server. Không tự reconnect/pair khi chỉ được phép read-only.

Journal phải ghi bền vững trạng thái gốc trước dispatch, giữ cả pending/uncertain
khi thất bại. Rollback chỉ dùng journal được chỉ định và cùng hardware serial/model.
Khôi phục đúng trạng thái gốc. Giữ nguyên package vốn đã bị disable.
Rollback không cần fetch nguồn; chỉ khôi phục journal cùng thiết bị.
Preflight toàn bộ entries được chọn trước ghi, dùng --package để giới hạn khôi phục.
Không tìm "backup mới nhất" toàn cục. Read-back sau từng lệnh và dừng khi lỗi.

Dữ liệu thiết bị chỉ đặt trong `backups/`; cache trong `.cache/`;
serial/IP chỉ trong `devices.local.json`. Các đường dẫn này phải được Git ignore.
Không đăng dump, journal, tài khoản hoặc device identifiers lên Git/PR/chat.
Giữ LICENSE và attribution upstream. Viết docs tiếng Việt có dấu.

## Kiểm tra trước bàn giao

Chạy `python3 -m unittest discover -s tests -v`, `python3 -m compileall -q phone_tweaks.py inventory-audit tests`,
`bash -n inventory-audit/audit.sh`, `git diff --check` và CLI help/status thật.
Audit live chỉ khi đã được cho phép. Tests phải mock ADB, không ghi thiết bị thật.
UAD NG là công cụ độc lập; không chạy GUI debloat trong quá trình kiểm tra toolkit.
