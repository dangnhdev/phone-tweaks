# Phân tích inventory riêng tư

```bash
./inventory-audit/audit.sh --device tab-s8
python3 inventory-audit/parse_packages.py backups/tab-s8/AUDIT_RUN/dumpsys-package.txt backups/tab-s8/AUDIT_RUN/packages.tsv
python3 inventory-audit/parse_diskstats.py backups/tab-s8/AUDIT_RUN/diskstats.txt
python3 inventory-audit/parse_usage.py backups/tab-s8/AUDIT_RUN/usagestats-plain.txt
```

Thay `AUDIT_RUN` bằng thư mục vừa được CLI in ra. Audit luôn yêu cầu profile
và serial rõ ràng hoặc binding local. Snapshot không đổi trạng thái thiết bị.

Diskstats có thể dùng cache cũ; không coi kích thước package là đo trực tiếp
hay bằng chứng nên gỡ ứng dụng. Parser packages chỉ mô tả user 0 từ dumpsys.
Parser usage phụ thuộc định dạng firmware; output rỗng không có nghĩa không dùng app.
Giữ TSV và mọi output phân tích trong `backups/`, không đăng dữ liệu công khai.
