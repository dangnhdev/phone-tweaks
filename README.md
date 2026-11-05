# phone-tweaks

Toolkit audit và lập kế hoạch cho Galaxy S23 Ultra `SM-S918B` qua wireless ADB,
và Galaxy Tab S8 `SM-X700` qua USB. Dùng Python 3.9+ stdlib và `adb` có sẵn.

Fork từ [megarohas/megarohas_galaxy_tab_tweaks](https://github.com/megarohas/megarohas_galaxy_tab_tweaks),
giữ [MIT LICENSE](LICENSE). Parsers inventory được giữ lại từ upstream.

## Kiểm tra đúng thiết bị

Tạo binding riêng bằng `cp devices.example.json devices.local.json`, rồi thay
placeholder bằng endpoint hoặc USB serial thực tế. File local được Git ignore.
Có thể truyền `--serial` để ghi đè binding. Không tự chọn thiết bị dù chỉ có một máy.

```bash
python3 phone_tweaks.py --help
python3 phone_tweaks.py status --device tab-s8
python3 phone_tweaks.py status --device s23-ultra
python3 phone_tweaks.py audit --device tab-s8
python3 phone_tweaks.py audit --device s23-ultra
```

Mỗi lệnh xác minh model, transport và hardware identity. Offline/unauthorized
hoặc model sai sẽ dừng. Wireless endpoint phải ở trạng thái `device` trước khi
chạy. Toolkit không pair, reconnect hay restart ADB server.

Audit lưu dữ liệu nhạy cảm trong `backups/<profile>/audit-<UTC>-<random>/`, quyền
thư mục 0700 và file 0600 khi chạy CLI. Mỗi lần có thư mục riêng.
`audit-status.json` cho biết snapshot đầy đủ hay lỗi từng phần.
Không đưa thư mục này lên Git hoặc gửi công khai.

## Review plan trước khi debloat

```bash
python3 phone_tweaks.py refresh
python3 phone_tweaks.py plan --device tab-s8
python3 phone_tweaks.py debloat --device s23-ultra --package com.facebook.system
```

`plan` và `debloat` mặc định chỉ đọc thiết bị. Mỗi lần đều fetch HEAD mới nhất
của [samsungdebloat](https://github.com/itxjobe/samsungdebloat) và
[UAD NG](https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation).
Một nguồn lỗi sẽ chặn toàn bộ plan/apply. Cache nằm trong `.cache/references/`.
Manifest ghi URL, commit và UTC fetch. Plan/journal riêng ghi cả evidence và
trạng thái installed/enabled live của từng package. Không chạy code upstream.

Allowlist gồm năm package. Hai dịch vụ Meta `com.facebook.system` và
`com.facebook.appmanager` dùng nguồn Samsung `community-configs/privacy-focused.txt`.
Chỉ chọn chúng nếu không dùng tích hợp và cập nhật Meta của hãng.

Ba candidate đợt 1 dùng nguồn Samsung `03-safe-system-apps.txt`:

- `com.samsung.android.rubin.app` tắt Customization Service, mất cá nhân hóa theo hành vi.
- `com.samsung.android.mapsagent` tắt dịch vụ đề xuất ứng dụng Samsung và đối tác.
- `com.sec.android.app.chromecustomizations` bỏ tùy biến Chrome của Samsung.

Mỗi candidate phải đồng thời được UAD đánh dấu `Recommended` tại
`resources/assets/uad_lists.json`. CLI đối chiếu đúng tên package hoặc dòng lệnh
ADB trong nguồn Samsung dưới dạng dữ liệu; không thực thi lệnh nguồn.
Nếu nguồn mới đổi đánh giá hoặc bỏ package, CLI dừng.
Package không cài sẽ được đánh dấu và bỏ qua.

Tạo plan riêng cho đợt 1 trên Tab S8:

```bash
python3 phone_tweaks.py plan --device tab-s8 \
  --package com.samsung.android.rubin.app \
  --package com.samsung.android.mapsagent \
  --package com.sec.android.app.chromecustomizations
```

Parser trạng thái chỉ đọc block package đang hoạt động của đúng package và user 0.
Bản system gốc trong `Hidden system packages` và header chẩn đoán không được dùng
làm trạng thái hiện tại. Output thiếu hoặc có nhiều trạng thái hiện tại sẽ bị từ chối.

Sau khi xem journal và nhận authorization RIÊNG cho từng package trên đúng máy,
operator mới thêm `--journal backups/<profile>/PLAN_RUN/journal.json`,
`--apply` và `--authorization 'quyết định cụ thể của user'`
vào lệnh `debloat --device ... --package ...`. Lặp `--package` nếu chọn nhiều.
Apply phải dùng đúng plan đã review, cùng hardware, package, trạng thái gốc và commit nguồn.
Nếu một giá trị đổi, tạo và review plan mới. Không có lựa chọn mặc định apply-all. CLI chỉ dùng `pm disable-user --user 0`;
không uninstall, xóa dữ liệu hoặc đổi appops. `--authorization` là bản ghi quyết định,
không phải cơ chế xác thực người dùng. Agent phải tuân thủ [AGENTS.md](AGENTS.md).

## Khôi phục đúng journal

Chỉ định đường dẫn journal do lần debloat đó in ra. Không dùng backup toàn cục.

```bash
python3 phone_tweaks.py rollback --device tab-s8 --journal backups/tab-s8/DEBLOAT_RUN/journal.json
```

Lệnh trên chỉ hiển thị rollback. Sau authorization riêng mới thêm `--apply` và
`--authorization`. Rollback dùng trạng thái gốc trong journal và không cần mạng.
Chỉ plan/apply debloat phải fetch hai nguồn mới nhất.
Hardware serial, model và profile phải khớp journal, kể cả khi transport IP đổi.

Journal ghi trạng thái gốc trước từng dispatch. CLI read-back sau mỗi lệnh,
dừng ở lỗi đầu tiên và giữ entries `pending`/`uncertain` để xử lý mất kết nối.
Rollback chỉ xử lý entries đã dispatch và khôi phục trạng thái gốc.
Debloat giữ nguyên package vốn đã disabled, disabled-user hoặc disabled-until-used. Trạng thái bị thay đổi ngoài toolkit sẽ
chặn rollback trước lần ghi đầu nếu không còn khớp trạng thái dự kiến.
Dùng `--package <package>` khi chỉ muốn khôi phục entry còn hợp lệ; có thể lặp flag.
Các entry khác giữ nguyên trong journal. Journal đã restored không
được dùng đè lên thay đổi mới. Không chạy hai phiên apply/rollback đồng thời.

## Giữ chức năng và kiểm tra sau thay đổi

Telephony, S Pen, Knox/Secure Folder, DeX, camera, notifications, VPN, automation,
Quick Share, tài khoản và OTA được giữ ngoài allowlist. Sau thay đổi được cho phép,
operator cần kiểm tra các chức năng thực tế. Không có phép đo speedup trong fork này.
Workflow Tab S6 Lite, apply-all, cleanup storage và ép dexopt cũ đã được bỏ.
Android quản lý JIT/AOT và tối ưu theo profile; toolkit không ép compilation hàng loạt.

## Mở UAD NG độc lập

```bash
open -a 'UAD NG'
```

Bản ARM64 UAD NG 1.3.1 được cài ở `/Applications/UAD NG.app`
và SHA-256 đã được đối chiếu với release chính thức. Đây là công cụ độc lập;
không chạy disable/uninstall từ GUI nếu chưa có authorization riêng.
Homebrew cask UAD cũ 0.5.1 đã disabled, không phải UAD NG.

## Chạy regression tests

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q phone_tweaks.py inventory-audit tests
bash -n inventory-audit/audit.sh
git diff --check
```

Tests dùng mocked ADB, gồm hai thiết bị, mismatch, offline/unauthorized, dry-run,
refresh lỗi, partial failure, lỗi stdout, write-ahead journal và rollback trạng thái gốc.
Xem [inventory-audit](inventory-audit/README.md) để phân tích snapshot.
