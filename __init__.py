# https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html
import re
import bpy
import os
import subprocess
import ast
import datetime
import shutil

bl_info = {
    "name": "RA 插件打包器",
    "author": "来一点咖啡吗",
    "version": (0, 0, 2),
    "blender": (4, 0, 0),
    "description": "开发者工具包，可快速打包插件，便于官网分发",
}

class RARA_PT_Addon_Preferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    output_path: bpy.props.StringProperty(
        name="输出路径",
        description="打包后文件保存的位置（自动记录，下次打开无需重复设置）",
        default="",
        subtype='DIR_PATH'
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "output_path")
        
        # layout.prop(context.scene, "rara_plugin_path")
        # layout.prop(self, "output_path")
        
        # layout.operator("rara.pack_blender_addon")
        # layout.operator("rara.generate_blender_manifest")
        
        
class RARA_PT_Addon_Pack_Panel(bpy.types.Panel):
    bl_label = "打包面板"
    bl_idname = "RARA_PT_Addon_Pack_Panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = '测试'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "rara_plugin_path")
        
        try:
            prefs = context.preferences.addons[__name__].preferences
            layout.prop(prefs, "output_path")
        except KeyError:
            layout.label(text="一般你是看不到这条信息的", icon='ERROR')
        
        layout.operator("rara.pack_blender_addon")
        layout.operator("rara.generate_blender_manifest")

class RARA_OT_Addon_Pack_Operator(bpy.types.Operator):
    bl_idname = "rara.pack_blender_addon"
    bl_label = "一键打包"
    bl_description = "一键生成可分发zip"
    
    def execute(self, context):
        plugin_path = context.scene.rara_plugin_path
        blender_path = bpy.app.binary_path

        # 1. 基础检查
        if not os.path.isdir(plugin_path):
            self.report({'ERROR'}, f"插件路径不存在：{plugin_path}")
            return {'CANCELLED'}
        
        init_file = os.path.join(plugin_path, "__init__.py")
        manifest_file = os.path.join(plugin_path, "blender_manifest.toml")
        
        if not os.path.isfile(init_file):
            self.report({'ERROR'}, "__init__.py 文件不存在")
            return {'CANCELLED'}
        if not os.path.isfile(manifest_file):
            self.report({'ERROR'}, "blender_manifest.toml 文件不存在，请先生成")
            return {'CANCELLED'}

        # 2. 执行命令的辅助函数（捕获输出和错误）
        def run_blender_command(cmd_desc, cmd_args):
            self.report({'INFO'}, f"正在执行：{cmd_desc}")
            try:
                result = subprocess.run(
                    cmd_args,
                    cwd=plugin_path,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='ignore'
                )
                
                # 打印输出（用于调试）
                if result.stdout:
                    print(f"[命令输出] {result.stdout}")
                if result.stderr:
                    print(f"[命令错误] {result.stderr}")
                
                if result.returncode != 0:
                    error_msg = result.stderr or result.stdout or "未知错误"
                    self.report({'ERROR'}, f"{cmd_desc}失败：{error_msg[:200]}")
                    return False
                return True
            except Exception as e:
                self.report({'ERROR'}, f"{cmd_desc}异常：{str(e)}")
                return False

        # 3. 执行验证和打包
        validate_cmd = [blender_path, "--factory-startup", "--command", "extension", "validate"]
        if not run_blender_command("验证插件", validate_cmd):
            return {'CANCELLED'}

        build_cmd = [blender_path, "--factory-startup", "--command", "extension", "build"]
        if not run_blender_command("打包插件", build_cmd):
            return {'CANCELLED'}

        # 4. 查找生成的文件（更可靠的逻辑）
        self.report({'INFO'}, "正在查找打包文件...")
        
        # 可能的输出位置
        possible_dirs = [
            plugin_path,
            os.path.join(plugin_path, "dist"),  # 某些版本可能输出到 dist 目录
        ]
        
        generated_zip_path = None
        for check_dir in possible_dirs:
            if not os.path.isdir(check_dir):
                continue
            
            # 查找所有 zip 文件，取最新修改的
            zip_files = []
            for f in os.listdir(check_dir):
                if f.endswith('.zip'):
                    f_path = os.path.join(check_dir, f)
                    zip_files.append((f_path, os.path.getmtime(f_path)))
            
            if zip_files:
                zip_files.sort(key=lambda x: x[1], reverse=True)
                generated_zip_path = zip_files[0][0]
                break
        
        if not generated_zip_path:
            self.report({'ERROR'}, "未找到生成的打包文件！请查看系统控制台（Window > Toggle System Console）了解详细错误")
            return {'CANCELLED'}

        # 5. 处理输出路径
        output_path = ""
        try:
            prefs = context.preferences.addons[__name__].preferences
            output_path = prefs.output_path
        except KeyError:
            pass

        final_path = generated_zip_path
        if output_path and os.path.isdir(output_path):
            target_path = os.path.join(output_path, os.path.basename(generated_zip_path))
            try:
                shutil.move(generated_zip_path, target_path)
                final_path = target_path
                self.report({'INFO'}, f"打包成功！文件已保存到：{final_path}")
            except Exception as e:
                self.report({'WARNING'}, f"打包成功，但移动文件失败（已保存在原位置）：{str(e)}")
                self.report({'INFO'}, f"文件位置：{generated_zip_path}")
        else:
            self.report({'INFO'}, f"打包成功！文件保存在：{final_path}")

        return {'FINISHED'}

class RARA_OT_Addon_Manifest_Operator(bpy.types.Operator):
    bl_idname = "rara.generate_blender_manifest"
    bl_label = "生成blender_manifest"
    bl_options = {'REGISTER'}
    bl_description = "一键生成必要配置文件"
    addons_blender_version_min: bpy.props.StringProperty(name="最低版本", default="4.2.0",
        description = "【按需修改】插件所支持的最低blender版本号")
    
    addons_id: bpy.props.StringProperty(name="插件ID", default="rara_test_tools",
        description = "【适当修改】插件所用的ID，建议使用英文+下划线")
    
    addons_license: bpy.props.StringProperty(name="插件许可", default='["SPDX:GPL-3.0-or-later"]',
        description = "【建议保持】插件所使用的开源许可证，如果上传官库，建议保持默认")
    
    addons_maintainer: bpy.props.StringProperty(name="维护人员", default="rara",
        description = "【建议修改】在这里签署你的大名")
        
    addons_name: bpy.props.StringProperty(name="插件名称", default="Rara Test Tools",
        description = "【建议修改】给插件取一个朗朗上口的名称吧")
    
    addons_schema_version: bpy.props.StringProperty(name="格式版本",default="1.0.0",
        description = "【切勿修改】使用 1.0.0即可，否则可能影响打包")
    
    addons_tagline: bpy.props.StringProperty(name="插件标语",default="插件简述",
        description = "【建议修改】建议修改为简短的插件介绍")
    
    addons_type: bpy.props.EnumProperty(
        name="插件类型",
        items=[('add-on', "插件", "附加组件类型"),('theme', "主题", "附加主题类型")],
        default='add-on',
        description = "【不建议修改】一般使用默认【插件】类型即可")
    
    addons_version: bpy.props.StringProperty(name="插件版本", default="0.0.1",
        description = "【适当修改】插件当前的版本号，一般保留即可")
        
    addons_blender_version_max: bpy.props.StringProperty(name="最高版本", default="",
        description = "【按需修改】插件所支持的最高blender版本号")
        
    addons_website: bpy.props.StringProperty(name="插件网站", default="https://space.bilibili.com/27284213",
        description = "【按需修改】填写可以与你进行联系的网址吧")
    
    addons_copyright: bpy.props.StringProperty(name="版权所有",
        default=f'["{datetime.datetime.now().year} RARA"]',
        description = "【按需修改】插件的版权信息")
    
    addons_tags: bpy.props.StringProperty(name="插件标签", default="['Object','3D View','Scene']",
        description = "【按需修改】插件的类型标签，你可以前往blenderAPI说明页查询支持哪些标签")
    
    addons_platforms: bpy.props.StringProperty(name="系统平台", default="",
        description = "【按需修改】留空表示全平台支持，如果需要限制平台，可以['windows-arm64','windows-x64']")
    
    addons_wheels: bpy.props.StringProperty(name="插件轮子", default="",
        description = "【按需修改】")
    
    permission_files: bpy.props.StringProperty(name="文件", default="",
        description = "解释为何需要文件系统访问权限（≤64字，不以标点结尾）")
    permission_network: bpy.props.StringProperty(name="网络", default="",
        description = "解释为何需要网络访问权限（≤64字，不以标点结尾）")
    permission_clipboard: bpy.props.StringProperty(name="剪贴板", default="",
        description = "解释为何需要剪贴板访问权限（≤64字，不以标点结尾）")
    permission_camera: bpy.props.StringProperty(name="摄像头", default="",
        description = "解释为何需要摄像头访问权限（≤64字，不以标点结尾）")
    permission_microphone: bpy.props.StringProperty(name="麦克风", default="",
        description = "解释为何需要麦克风访问权限（≤64字，不以标点结尾）")
    
    build_paths_exclude_pattern: bpy.props.StringProperty(
        name="排除模式",
        default='["__pycache__/", ".git", "*.zip"]',
        description = "打包时排除的文件模式（gitignore格式）")
    build_paths: bpy.props.StringProperty(
        name="包含路径",
        default="",
        description = "打包时包含的相对路径列表（与排除模式互斥，设置后排除模式无效）")
    
    show_optional: bpy.props.BoolProperty(name="显示附加项", default=False,
        description = "展开完整（非必要的）注册信息设置项")
    
    manifest_data = [
        ("schema_version", "addons_schema_version", "REQUIRED"),
        ("blender_version_min", "addons_blender_version_min", "REQUIRED"),
        ("blender_version_max", "addons_blender_version_max", "OPTIONAL"),
        ("version", "addons_version", "REQUIRED"),
        ("id", "addons_id", "REQUIRED"),
        ("name", "addons_name", "REQUIRED"),
        ("tagline", "addons_tagline", "REQUIRED"),
        ("license", "addons_license", "REQUIRED"),
        ("maintainer", "addons_maintainer", "REQUIRED"),
        ("type", "addons_type", "REQUIRED"),
        ("website", "addons_website", "OPTIONAL"),
        ("copyright", "addons_copyright", "OPTIONAL"),
        ("tags", "addons_tags", "OPTIONAL"),
        ("platforms", "addons_platforms", "OPTIONAL"),
        ("wheels", "addons_wheels", "OPTIONAL"),
    ]
    manifest_list = ["tags", "license", "platforms", "wheels", "copyright"]
    
    def _parse_manifest_toml(self, plugin_path):
        """尝试从插件路径解析已有的 blender_manifest.toml"""
        manifest_path = os.path.join(plugin_path, "blender_manifest.toml")
        if not os.path.exists(manifest_path):
            return None
            
        data = {}
        try:
            # 优先尝试使用 Python 3.11+ 内置的 tomllib
            import tomllib
            with open(manifest_path, "rb") as f:
                data = tomllib.load(f)
        except ImportError:
            # 如果是低版本 Python，使用基础正则提取
            import re
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    content = f.read()
                for match in re.finditer(r'^([a-zA-Z0-9_]+)\s*=\s*(.+)$', content, re.MULTILINE):
                    key = match.group(1).strip()
                    val = match.group(2).strip()
                    # 简单去除首尾双引号
                    if val.startswith('"') and val.endswith('"'):
                        val = val[1:-1]
                    data[key] = val
            except Exception as e:
                self.report({'WARNING'}, f"正则解析 TOML 失败: {str(e)}")
                return None
        except Exception as e:
            self.report({'WARNING'}, f"读取 TOML 失败: {str(e)}")
            return None
            
        return data
    
    
    def _parse_bl_info(self, plugin_path):
        """从插件路径的__init__.py中解析bl_info字典（兼容BOM和多编码）"""
        init_path = os.path.join(plugin_path, "__init__.py")
        if not os.path.exists(init_path):
            self.report({'WARNING'}, f"未找到插件文件：{init_path}")
            return None
        
        # 尝试多种编码读取文件
        encodings = ['utf-8-sig', 'utf-8', 'gbk', 'latin-1']
        content = None
        
        for enc in encodings:
            try:
                with open(init_path, 'r', encoding=enc) as f:
                    content = f.read()
                break  # 读取成功则跳出
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.report({'WARNING'}, f"读取文件失败（{enc}）：{str(e)}")
                return None
        
        if content is None:
            self.report({'WARNING'}, "无法解析文件编码，请确保__init__.py为UTF-8或GBK编码")
            return None
        
        try:
            # 提取bl_info字典的AST节点
            tree = ast.parse(content)
            bl_info_dict = None
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "bl_info":
                            if isinstance(node.value, ast.Dict):
                                bl_info_dict = ast.literal_eval(node.value)
                                break
            return bl_info_dict
        
        except SyntaxError as e:
            self.report({'WARNING'}, f"解析代码语法错误：第{e.lineno}行 - {e.msg}")
            return None
        except Exception as e:
            self.report({'WARNING'}, f"解析bl_info失败：{str(e)}")
            return None
    
    def _auto_fill_props(self, context):
        plugin_path = context.scene.rara_plugin_path
        
        # ================= 第一步：优先尝试解析 blender_manifest.toml =================
        manifest_data_dict = self._parse_manifest_toml(plugin_path)
        if manifest_data_dict:
            self.report({'INFO'}, "检测到 blender_manifest.toml，优先使用其配置")
            import json
            
            # 遍历我们定义的字段映射，将 toml 中的值填入 UI 属性
            for key, name, type_ in self.manifest_data:
                if key in manifest_data_dict:
                    val = manifest_data_dict[key]
                    
                    # 如果解析出来的是列表或字典（比如 tags, platforms），将其转回字符串以便在 UI 中显示
                    if isinstance(val, (list, dict)):
                        val_str = json.dumps(val, ensure_ascii=False)
                        setattr(self, name, val_str)
                    else:
                        setattr(self, name, str(val))

            # 解析 [permissions] section
            if "permissions" in manifest_data_dict and isinstance(manifest_data_dict["permissions"], dict):
                perms = manifest_data_dict["permissions"]
                for key in ["files", "network", "clipboard", "camera", "microphone"]:
                    if key in perms:
                        setattr(self, f"permission_{key}", str(perms[key]))

            # 解析 [build] section
            if "build" in manifest_data_dict and isinstance(manifest_data_dict["build"], dict):
                build = manifest_data_dict["build"]
                if "paths_exclude_pattern" in build:
                    val = build["paths_exclude_pattern"]
                    if isinstance(val, list):
                        setattr(self, "build_paths_exclude_pattern", json.dumps(val, ensure_ascii=False))
                    else:
                        setattr(self, "build_paths_exclude_pattern", str(val))
                if "paths" in build:
                    val = build["paths"]
                    if isinstance(val, list):
                        setattr(self, "build_paths", json.dumps(val, ensure_ascii=False))
                    else:
                        setattr(self, "build_paths", str(val))

            return  # 成功读取 toml 后直接返回，不再解析 bl_info

        # ================= 第二步：如果没有 toml，则降级解析 bl_info =================        
        bl_info = self._parse_bl_info(plugin_path)
        if not bl_info:
            self.report({'INFO'}, "未检测到bl_info，使用默认值（可手动修改）")
            return

        # 插件名称（直接取bl_info的name）
        if bl_info.get("name"):
            self.addons_name = bl_info["name"]

        
        # 获取插件根目录的文件夹名称（normpath用于处理路径末尾可能带斜杠的情况）
        folder_name = os.path.basename(os.path.normpath(plugin_path))
        # 先转小写，空格替换为下划线
        clean_id = folder_name.lower().replace(" ", "_")
        # 使用正则移除非法字符（^a-z0-9_ 表示匹配所有不是小写字母、数字和下划线的字符，将其替换为空）
        clean_id = re.sub(r'[^a-z0-9_]', '', clean_id)
        if clean_id:
            self.addons_id = clean_id
        
        
        # 插件版本（元组转字符串，如(0,0,1) → "0.0.1"）
        if bl_info.get("version") and isinstance(bl_info["version"], tuple):
            self.addons_version = ".".join(map(str, bl_info["version"]))
        
        # 维护人员（取bl_info的author）
        if bl_info.get("author"):
            self.addons_maintainer = bl_info["author"]
        
        # 最低Blender版本（元组转字符串）
        if bl_info.get("blender") and isinstance(bl_info["blender"], tuple):
            self.addons_blender_version_min = ".".join(map(str, bl_info["blender"]))
        
        # 版权信息（自动填充当前年份+作者）
        author = bl_info.get("author", "Unknown")
        current_year = datetime.datetime.now().year
        self.addons_copyright = f'["{current_year} {author}"]'
        
        # 插件标语（默认取名称缩写，用户可自行修改）
        if bl_info.get("description"):
            self.addons_tagline = bl_info["description"]
        elif bl_info.get("name"):
            self.addons_tagline = f"{bl_info['name']} - Blender插件"
    
    def execute(self, context):
        plugin_path = context.scene.rara_plugin_path
        manifest_path = os.path.join(plugin_path, "blender_manifest.toml")

        try:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                for manifest in self.manifest_data:
                    key, name, type_ = manifest
                    value = getattr(self, name, "")
                    if type_ == "OPTIONAL" and value == "":
                        continue
                    if key in self.manifest_list:
                        f.write(f'{key} = {value}\n')
                    else:
                        f.write(f'{key} = "{value}"\n')

                # ===== [permissions] section =====
                perm_data = [
                    ("files", "permission_files"),
                    ("network", "permission_network"),
                    ("clipboard", "permission_clipboard"),
                    ("camera", "permission_camera"),
                    ("microphone", "permission_microphone"),
                ]
                perm_lines = []
                for perm_key, prop_name in perm_data:
                    val = getattr(self, prop_name, "").strip()
                    if val:
                        perm_lines.append(f'{perm_key} = "{val}"')
                if perm_lines:
                    f.write("\n[permissions]\n")
                    for line in perm_lines:
                        f.write(line + "\n")

                # ===== [build] section =====
                build_exclude = getattr(self, "build_paths_exclude_pattern", "").strip()
                build_paths_val = getattr(self, "build_paths", "").strip()
                if build_paths_val or build_exclude:
                    f.write("\n[build]\n")
                    if build_paths_val:
                        f.write(f'paths = {build_paths_val}\n')
                    elif build_exclude:
                        f.write(f'paths_exclude_pattern = {build_exclude}\n')

            self.report({'INFO'}, f"blender_manifest已生成到 {manifest_path}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"生成blender_manifest失败: {str(e)}")
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        # 第一步：自动填充插件信息
        self._auto_fill_props(context)
        # 第二步：弹出可编辑的属性窗口
        return context.window_manager.invoke_props_dialog(self, width=600)
        
    def draw(self, context):
        layout = self.layout
        row=layout.row()
        row.prop(self, "show_optional")        
        op = row.operator("wm.url_open", text="", icon='QUESTION')
        op.url = "https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html"
        
        layout.separator()        
        # ================= 新增：硬性规范实时警告 =================
        errors = []

        # 插件ID (id) 检查
        # 使用正则匹配：^ 表示开头，$ 表示结尾，[a-zA-Z0-9_]+ 表示只允许大小写英文、数字和下划线
        if not re.match(r'^[a-zA-Z0-9_]+$', self.addons_id):
            errors.append("插件ID仅限英文大小写、数字和下划线 (请修改多语言或空格)")
            
        # 标语 (tagline) 检查
        tagline = self.addons_tagline.strip()
        if len(tagline) > 64:
            errors.append(f"标语过长 ({len(tagline)}/64)")
        if tagline and tagline[-1] in ".,;:!?。，；：！？":
            errors.append("标语绝对不能以标点符号结尾")

        # 格式版本 (schema_version) 检查
        if self.addons_schema_version != "1.0.0":
            errors.append("格式版本(schema_version)必须为 1.0.0")

        # 插件版本 (version) 检查：语义化版本
        ver_parts = self.addons_version.split('.')
        if len(ver_parts) < 3 or not all(p.isdigit() for p in ver_parts):
            errors.append("插件版本必须遵循语义化(如 0.0.1)")

        # 最低版本 (blender_version_min) 检查
        min_v_str = self.addons_blender_version_min.split('.')
        current_version = bpy.app.version  # 获取当前Blender版本，例如 (4, 2, 0)
        try:
            # 将用户输入的字符串转换为整数元组
            user_v_tuple = tuple(int(x) for x in min_v_str if x.isdigit())
            # 补齐到3位以便比较，例如输入 "4.2" 会被补齐为 (4, 2, 0)
            while len(user_v_tuple) < 3:
                user_v_tuple += (0,)
            # 比较版本：不能低于当前Blender版本
            if user_v_tuple > current_version:
                current_v_str = ".".join(map(str, current_version))
                errors.append(f"最低支持版本不能高于当前环境版本 ({current_v_str})")
        except Exception:
            errors.append("最低支持版本格式错误 (应为如 5.2.0)")

        # 版权 (copyright) 检查
        if self.addons_copyright and self.show_optional:
            if not re.search(r'\d{4}', self.addons_copyright):
                errors.append("版权(copyright)必须包含年份(如 2024 Name)")

        # 标签 (tags) 检查
        if self.addons_tags and self.show_optional:
            # 官方允许的标签白名单
            allowed_tags = {
                "3D View", "Add Curve", "Add Mesh", "All", "Animation", "Bake", 
                "Camera", "Compositing", "Development", "Game Engine", "Geometry Nodes", 
                "Grease Pencil", "Import-Export", "Lighting", "Material", "Mesh", 
                "Modeling", "Node", "Object", "Paint", "Physics", "Pipeline", 
                "Render", "Rigging", "Scene", "Sculpt", "Sequencer", "System", 
                "Text Editor", "Tracking", "UV", "User Interface"
            }
            # 使用正则提取引号内的所有字符串，例如从 ["Object", "3D Vie99w"] 中提取出 Object 和 3D Vie99w
            input_tags = re.findall(r'["\']([^"\']+)["\']', self.addons_tags)
            # 找出不在白名单中的非法标签
            invalid_tags = [tag for tag in input_tags if tag not in allowed_tags]
            if invalid_tags:
                errors.append(f"包含非法标签: {', '.join(invalid_tags)}")


        # 轮子 (wheels) 检查
        if getattr(self, "addons_wheels", "") and self.show_optional:
            wheels_str = self.addons_wheels.strip()
            # 检查是否是列表格式
            if not (wheels_str.startswith('[') and wheels_str.endswith(']')):
                errors.append("wheels 必须是列表格式 (例如 [\"./xxx.whl\"])")
            else:
                # 提取引号内的路径，检查后缀
                wheel_items = re.findall(r'["\']([^"\']+)["\']', wheels_str)
                invalid_wheels = [w for w in wheel_items if not w.endswith('.whl')]
                if invalid_wheels:
                    errors.append(f"wheel 文件必须以 .whl 结尾: {', '.join(invalid_wheels)}")
                    
        # 各权限说明校验（≤64字，不以标点结尾）
        if self.show_optional:
            perm_props = [
                ("permission_files", "文件权限"),
                ("permission_network", "网络权限"),
                ("permission_clipboard", "剪贴板权限"),
                ("permission_camera", "摄像头权限"),
                ("permission_microphone", "麦克风权限"),
            ]
            for prop_name, label in perm_props:
                val = getattr(self, prop_name, "").strip()
                if val:
                    if len(val) > 64:
                        errors.append(f"{label}说明过长 ({len(val)}/64)")
                    if val[-1] in ".,;:!?。，；：！？":
                        errors.append(f"{label}说明不能以标点结尾")

        # build 路径互斥检查
        if self.show_optional:
            build_paths_val = getattr(self, "build_paths", "").strip()
            build_exclude_val = getattr(self, "build_paths_exclude_pattern", "").strip()
            if build_paths_val and build_exclude_val:
                errors.append("包含路径(paths)与排除模式(paths_exclude_pattern)互斥，只能设置其一")
        
        # 插件类型 (type) 检查
        if self.addons_type != 'add-on':
            errors.append("本工具暂时仅支持打包插件")
      
        # 渲染错误提示框
        if errors:
            box = layout.box()
            box.alert = True
            for err in errors:
                box.label(text=f"错误：{err}！", icon='ERROR')
        # ====================================================
        
        layout.separator()

        # 分栏显示：必填项 + 可选项（按需显示）
        for manifest in self.manifest_data:
            key, name, type_ = manifest
            if self.show_optional:
                layout.prop(self, name)
            elif type_ == "REQUIRED":
                layout.prop(self, name)

        # 权限（[permissions] section）
        if self.show_optional:
            layout.separator()
            layout.label(text="[permissions] 插件权限声明:", icon='LOCKED')
            layout.prop(self, "permission_files")
            layout.prop(self, "permission_network")
            layout.prop(self, "permission_clipboard")
            layout.prop(self, "permission_camera")
            layout.prop(self, "permission_microphone")

            layout.separator()
            layout.label(text="[build] 打包高级选项:", icon='PACKAGE')
            layout.prop(self, "build_paths_exclude_pattern")
            layout.prop(self, "build_paths")

def register():
    bpy.utils.register_class(RARA_PT_Addon_Preferences)
    bpy.utils.register_class(RARA_PT_Addon_Pack_Panel)
    bpy.utils.register_class(RARA_OT_Addon_Pack_Operator)
    bpy.utils.register_class(RARA_OT_Addon_Manifest_Operator)
    bpy.types.Scene.rara_plugin_path = bpy.props.StringProperty(
        name="插件路径",
        default=os.path.dirname(__file__),
        subtype='DIR_PATH'
    )

def unregister():
    bpy.utils.unregister_class(RARA_PT_Addon_Preferences)
    bpy.utils.unregister_class(RARA_PT_Addon_Pack_Panel)
    bpy.utils.unregister_class(RARA_OT_Addon_Pack_Operator)
    bpy.utils.unregister_class(RARA_OT_Addon_Manifest_Operator)
    del bpy.types.Scene.rara_plugin_path

if __name__ == "__main__":
    register()
    
    
    
    
    
    
 