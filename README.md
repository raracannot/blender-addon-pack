# RA 插件打包器 (Blender Addon Pack)

Blender 开发者工具，可快速验证和打包插件，生成符合官方规范的 `blender_manifest.toml`，便于在 [Blender Extensions](https://extensions.blender.org/) 平台分发。

## 功能

- **一键生成 `blender_manifest.toml`** — 自动从 `bl_info` 解析插件信息，支持手动编辑各项字段
- **内置规范校验** — 实时检查 ID 格式、版本号、标签白名单、标语规范等
- **命令行验证与打包** — 调用 Blender 内置 `extension validate` / `extension build` 命令
- **自定义输出路径** — 打包后自动移动到指定目录

## 安装

1. 下载本仓库代码
2. 将整个文件夹放入 Blender 的 `addons` 目录
3. 在 Blender 中启用插件：`编辑 > 偏好设置 > 插件 > RA 插件打包器`

## 使用

1. 在 3D 视图右侧面板中找到 **打包面板**（侧边栏 `测试` 标签页）
2. 设置目标插件的 **插件路径**
3. 点击 **生成 blender_manifest** 填写配置信息
4. 点击 **一键打包** 生成可分发的 `.zip` 文件

## 兼容性

- 最低 Blender 版本：4.0.0（打包功能需要 4.2+）

## 许可证

GPL-3.0-or-later

## 作者

来一点咖啡吗 — [Bilibili](https://space.bilibili.com/27284213)
