# 小奶茶素材导入历史

当前分支已经从用户上传的透明分解图重新生成独立 PNG、绑定和动作。素材在 `assets/coaches/milktea/rig/`，Godot 和 MP4 共用。新接手从[教练交接文档](coach-avatar.md)开始。

下面保留早期 v0.1 离线包与补丁的校验信息，仅用于辨认旧资产。该包使用 `parts/` 和 `rig_manifest.json`，与当前工程使用的路径及绑定协议不同。

## v0.1 归档记录

- 此分支已提交**经过本地验证的安装程序** `tools/install_coach_assets.py`，但图像二进制文件**尚未推送到 GitHub**。不要把安装器已提交误认为素材已入库。
- 原始离线素材包为 `小奶茶_2D骨骼素材_接缝修正版_v0.1.zip`，SHA-256 为 `9d280b993b8656c5993c6677923266ad2b7841168bd6192ea65dba2603959380`，大小 3,045,515 字节。
- 包内共 35 个文件，其中 29 个独立透明 PNG，在 `parts/` 下；另外有 `rig_manifest.json`、README、原始和修复预览。
- 包是骨骼绑定前的栅格素材，不是已可直接播放的 Spine/Godot 骨架项目，也不等于自动生成了 JabJam 所需的逐动作帧。

## 让小奶茶 / DSH 完成二进制素材 Git 提交

把用户提供的上述 ZIP 文件传到**个人设备或个人服务器允许处理的目录**。仓库工作区务必检出 `feat/coach-avatar-stage1` 分支；不要误操作 `main` 或私有音乐仓库 `jabjam-render`。

```bash
git fetch origin
git switch feat/coach-avatar-stage1
python3 tools/install_coach_assets.py /path/to/小奶茶_2D骨骼素材_接缝修正版_v0.1.zip --check
python3 tools/install_coach_assets.py /path/to/小奶茶_2D骨骼素材_接缝修正版_v0.1.zip
git add assets/coaches/milktea/
git diff --cached --stat
git commit -m "assets(coach): add milktea whale-outfit cutout rig parts v0.1"
git push origin feat/coach-avatar-stage1
```

如果已经有同名素材目录，安装器会拒绝覆盖，先人工核对版本而不是强制清空。请将推送后 commit SHA 记录在 PR #11。

## 无 ZIP 方案：直接导入独立 PNG 的 Git 二进制补丁

如果通过 ChatGPT 获取到 `JabJam-小奶茶-29部件-独立PNG-Git补丁.patch`，**不需要解压任何 ZIP**。
该补丁是通过 `git format-patch --binary` 导出的真实提交，包含 `assets/coaches/milktea/parts/` 下 29 个 PNG、`rig_manifest.json`、素材 README、修复对照图。它不会在仓库中创建 ZIP 文件。

补丁 SHA-256：`a6ab22d832039e413735b3baf781233ae06a1672d9cc7cb780550aaca543834d`（3,949,592 字节）。
本地以另一独立 Git 仓库执行 `git am` 验证通过，并逐字节比较 29 张 PNG。

```bash
git fetch origin
git switch feat/coach-avatar-stage1
git pull --ff-only
sha256sum /path/to/JabJam-小奶茶-29部件-独立PNG-Git补丁.patch
git am /path/to/JabJam-小奶茶-29部件-独立PNG-Git补丁.patch
git status --short
git push origin feat/coach-avatar-stage1
```

如果 `git am` 失败，不要执行强推。先用 `git am --abort` 回到原状，再核对是否已存在同名素材。上传并推送完以后，GitHub 显示的是可独立修改的图片，而非补丁或 ZIP。**截至旧版交接时，图片仍尚未远程入库。**

## 验收

- 29 张 PNG 和 `rig_manifest.json` 都存在，并且清单引用的文件与实际图片完全一致。
- 保持原图/修复图/组装预览以供回归检查；不把生成中间缓存和测试副本提交进去。
- 呆毛和耳根连接处应在 Godot 骨骼动画旋转时不露黑边，拳套与胳膊重叠不能明显穿帮。
- `video/coach_avatar.py` 的 SpriteCoach **读取逐动作 clip 帧**；本素材包是 **2D cutout rig source**，后续还须用 Godot/其他 2D 骨骼工具绑定、制作动作、导出序列帧及 clip manifest。
- 与音乐时间轴对齐只由 `video/coach_timeline.py` 负责，素材和骨骼渲染器不得再造一份编舞逻辑。

## 安全及版权

素材不含私有歌曲。保留源图可供角色画风校准，但正式使用 DeepSeek 鲸鱼标志时注意适用的商标/品牌规范。
