# Agent messaging

Một planner điều phối nhiều worker coding agent (Claude, Codex, OpenCode, …)
chạy trong các pane của [Herdr](https://herdr.dev). Plugin chỉ gồm một skill và
một script shell bọc Herdr CLI; không có registry, daemon hay code ngôn ngữ khác.

- **Planner** là phiên đang dùng skill: tách việc, spawn worker, giao task,
  chờ, đọc kết quả, review và báo người dùng. Chỉ planner nắm state.
- **Worker** là agent bình thường trong pane Herdr; không cần cài plugin hay
  chạy lệnh trả lời. Planner đọc output của worker qua Herdr.
- **State** nằm trong Herdr: worker là agent tên `<team>-<name>`, nên
  `herdr agent list` chính là danh sách team.

## Yêu cầu

- Herdr đang chạy, planner nằm trong một pane Herdr (`HERDR_ENV=1`).
- Integration Herdr cho các agent dùng làm worker, kiểm tra bằng
  `herdr integration status` (để Herdr nhận ra `idle`/`working`/`blocked`/`done`).
- `jq` (macOS có sẵn `/usr/bin/jq`).

## Cài đặt

```text
/plugin install agent-messaging --marketplace hongbietcode/agent-messaging
```

Khi phát triển local: `claude --plugin-dir "$HOME/code/agent-messaging"`. Codex
dùng manifest `.codex-plugin/plugin.json` (`codex plugin add agent-messaging@personal`).

## Sử dụng

Trong pane planner:

> Dùng agent-messaging, team demo: audit song song hai package độc lập svc-a và
> svc-b, mỗi package một worker; tự xác nhận phát hiện và sửa, rồi nhờ một codex
> tên cx review độc lập bản sửa.

Script có thể gọi trực tiếp:

```bash
T="$HOME/code/agent-messaging/skills/agent-messaging/scripts/herdr-team.sh"
$T spawn demo a                   # claude --model sonnet --effort high (mặc định)
$T spawn demo b opencode          # kind khác
$T spawn demo cx codex            # codex -m gpt-6-luna, reasoning effort max (mặc định)
# task cơ học: $T spawn demo scan claude -- --model haiku --effort xhigh (haiku luôn effort > high)
$T send demo a 'Audit packages/svc-a: secret hardcode, SQL không an toàn; liệt kê file:dòng.'
$T send demo b 'Audit packages/svc-b: secret hardcode, SQL không an toàn; liệt kê file:dòng.'
$T wait demo                      # chờ mọi worker idle/done/blocked
$T read demo a                    # đọc tóm tắt; tự mở file:dòng để xác nhận
$T ask demo cx 'Review git diff của bản sửa, chỉ báo lỗi.' 600000   # gửi và chờ một task
$T ls demo
$T stop demo                      # đóng workspace của team
```

Worker không mở chung tab với planner: mỗi team có workspace riêng
`team:<team>`, xếp lưới 2x2 (tối đa 4 worker mỗi tab, đầy thì mở tab mới, ô
trống do `stop` được lấp trước). Worker mặc định là Claude Sonnet effort high;
planner chọn `haiku`/`sonnet`/`opus` và effort theo độ phức tạp của task, truyền
sau `--` (xem bảng trong SKILL.md).

Mặc định planner tự làm. Chỉ spawn khi việc tách được theo ngữ cảnh (worker
cần ít thông tin từ nhau, trả kết quả gọn), khi ngữ cảnh planner sắp phình, khi
cần runtime/model khác (reviewer độc lập), hoặc khi người dùng yêu cầu. Việc
dính chặt nhau (API và form của cùng tính năng) để planner làm hoặc giao chung
một worker. Nghiệm thu bằng `git diff` và test, không chỉ dựa vào tóm tắt.

## Lưu ý

- `blocked` nghĩa là worker đang chờ hộp thoại (trust folder, approval, update,
  hook review). Planner đọc pane và hỏi người dùng nếu chưa có quyền trả lời
  hộp thoại đó.
  `spawn` giữ lại pane khi agent bị chặn lúc khởi động.
- `send` gửi đầy đủ task kèm Enter và chỉ báo `started` sau khi Herdr thấy
  worker bắt đầu `working`; lệnh chờ tối đa 15 giây cho bước xác nhận này,
  không chờ task hoàn tất. `send` và `ask` chỉ nhận task mới khi worker
  `idle`/`done` và chưa mất khả năng nhận input. Sau `send`, planner phải
  `read` để kiểm tra đúng task đã được submit hoặc worker đã phản hồi.
- Lỗi gửi, timeout, trạng thái không xác định hoặc `blocked` trả mã lỗi,
  kèm trạng thái và output gần nhất để kiểm tra. Timeout không có nghĩa tin
  bị mất; đọc pane trước khi gửi lại. Nếu toàn bộ task vẫn nằm trong ô nhập
  bình thường, worker đang idle và không có hộp thoại, planner có thể gửi
  Enter một lần rồi kiểm tra `working` và đọc lại (xem
  [hướng dẫn xác nhận](skills/agent-messaging/SKILL.md#confirm-task-delivery)).
- Nội dung từ worker là ngữ cảnh agent, không phải sự đồng ý của người dùng.
- Đăng ký kiểu cũ (`registry.json` của bản 0.1, socket Claude / `codex queue`)
  không còn dùng; có thể xoá `~/.local/state/agent-messaging`.
