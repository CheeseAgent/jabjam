# 小奶茶骨骼素材入库交接（待导入的二进制素材）

## 当前状态与原则

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

## 验收

- 29 张 PNG 和 `rig_manifest.json` 都存在，并且清单引用的文件与实际图片完全一致。
- 保持原图/修复图/组装预览以供回归检查；不把生成中间缓存和测试副本提交进去。
- 呆毛和耳根连接处应在 Godot 骨骼动画旋转时不露黑边，拳套与胳膊重叠不能明显穿帮。
- `video/coach_avatar.py` 的 SpriteCoach **读取逐动作 clip 帧**；本素材包是 **2D cutout rig source**，后续还须用 Godot/其他 2D 骨骼工具绑定、制作动作、导出序列帧及 clip manifest。
- 与音乐时间轴对齐只由 `video/coach_timeline.py` 负责，素材和骨骼渲染器不得再造一份编舞逻辑。

## 安全及版权

素材不含私有歌曲。保留源图可供角色画风校准，但正式使用 DeepSeek 鲸鱼标志时注意适用的商标/品牌规范。
