# Snapshot nguồn tham khảo

Snapshot để review implementation, không thay thế fetch mới trước plan/apply.

- [samsungdebloat](https://github.com/itxjobe/samsungdebloat/tree/7dff732a6b4eac7171caefbfe22aef6181925893) commit `7dff732a6b4eac7171caefbfe22aef6181925893`, fetch UTC `2026-11-05T02:11:46.882206+00:00`.
- [uad-ng](https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation/tree/e1fff1efa87c54611b52771a31a03f408712deec) commit `e1fff1efa87c54611b52771a31a03f408712deec`, fetch UTC `2026-11-05T02:11:47.918163+00:00`.

Hai package được đối chiếu tại snapshot này là `com.facebook.system` và
`com.facebook.appmanager`. Samsung liệt kê tại `community-configs/privacy-focused.txt`.
UAD đánh dấu `Recommended` tại `resources/assets/uad_lists.json`.
Không nhập scripts hoặc dữ liệu nguồn vào fork.

Audit live Tab S8 `SM-X700`, Android 16, One UI 80000 ngày 2026-11-05 ghi nhận
cả hai package không cài cho user 0. Plan riêng lưu trong `backups/tab-s8/`.
Không thay đổi package hoặc trạng thái thiết bị trong implementation này.

Ba candidate đợt 1 `com.samsung.android.rubin.app`, `com.samsung.android.mapsagent`
và `com.sec.android.app.chromecustomizations` được đối chiếu lại ngày 2026-11-05.
Nguồn Samsung là `03-safe-system-apps.txt`, cùng commit trên. Nguồn UAD cùng
commit trên đánh dấu cả ba là `Recommended`. Plan live lưu trạng thái gốc riêng;
việc thêm allowlist không tự cho phép apply.
